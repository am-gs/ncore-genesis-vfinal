"""
NCore Genesis vFinal — Athena MoE Router (QC-v2)

QC-v2 fixes:
  - Redis UDS connection decoupled from __init__ into async lifecycle
    methods (connect_cache / disconnect_cache) wired to ASGI startup/
    shutdown events. Prevents FD leak on uvicorn Restart=always cycles.
  - Model registry updated to March 2026 Realm-X spec:
      tactical -> HauhauCS/Qwen3.5-35B-A3B-Uncensored
      director -> llama-3.2-dark-champion-18b-moe (unchanged)
      deep_reasoning -> gpt-oss-120b-moe (unchanged)
  Note: wan-2.2-remix-dit (video diffusion) excluded — requires a
  dedicated diffusion serving layer, not a vLLM text endpoint.

Prior fixes retained:
  - return_tensors="np" zero-copy ORT path.
  - Manual perf_counter timing on async route().
  - INT8 ONNX quantization on first boot.
  - FAISS IndexFlatIP (correct for micro-index of 1-5 vectors).
  - asyncio.to_thread (correct: ORT releases GIL during inference).
"""
import hashlib
import asyncio
import os
import time
import numpy as np
import redis.asyncio as aioredis
import faiss
from optimum.onnxruntime import ORTModelForFeatureExtraction, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from transformers import AutoTokenizer
from dataclasses import dataclass
from typing import Dict, Optional

from metrics import (
    ROUTING_LATENCY,
    CACHE_HITS,
    CACHE_MISSES,
    increment_metric_safe,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ModelConfig:
    name: str
    provider: str
    endpoint: str
    cost_per_1k: float
    context_window: int
    base_latency_ms: int
    role: str = ""


# ---------------------------------------------------------------------------
# Registry — March 2026 Realm-X
# ---------------------------------------------------------------------------
class NCoreModelRegistry:
    def __init__(self) -> None:
        self.models: Dict[str, ModelConfig] = {
            "dolphin-3.0": ModelConfig(
                name="HauhauCS/Qwen3.5-35B-A3B-Uncensored",
                provider="vllm-vast",
                endpoint="http://tactical-vllm:8000",
                cost_per_1k=0.0012,
                context_window=32768,
                base_latency_ms=350,
                role="tactical",
            ),
            "dark-champion": ModelConfig(
                name="llama-3.2-dark-champion-18b-moe",
                provider="vllm-vast",
                endpoint="http://darkchamp-vllm:8000",
                cost_per_1k=0.0015,
                context_window=128000,
                base_latency_ms=800,
                role="director",
            ),
            "gpt-oss-120b": ModelConfig(
                name="gpt-oss-120b-moe",
                provider="vllm",
                endpoint="http://gptoss-vllm:8000",
                cost_per_1k=0.0045,
                context_window=200000,
                base_latency_ms=2500,
                role="deep_reasoning",
            ),
        }

    def get(self, key: str) -> ModelConfig:
        return self.models[key]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
QUANTIZED_DIR  = os.getenv("NCORE_QUANTIZED_DIR", "/tmp/ncore_quantized")
REDIS_UDS      = os.getenv("NCORE_REDIS_UDS",     "/var/run/redis/redis-server.sock")
EMBED_MODEL_ID = os.getenv("NCORE_EMBED_MODEL",   "sentence-transformers/all-MiniLM-L6-v2")


class AthenaMoERouter:
    def __init__(self, registry: NCoreModelRegistry) -> None:
        self.registry = registry

        # QC-v2: cache is None until connect_cache() is called at ASGI startup.
        # This prevents the aioredis socket being opened at import time and
        # leaking FDs across uvicorn Restart=always cycles.
        self.cache: Optional[aioredis.Redis] = None

        # INT8 ONNX encoder
        self.tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL_ID)

        if not os.path.exists(QUANTIZED_DIR):
            os.makedirs(QUANTIZED_DIR, exist_ok=True)
            base_model = ORTModelForFeatureExtraction.from_pretrained(
                EMBED_MODEL_ID, export=True
            )
            quantizer = ORTQuantizer.from_pretrained(base_model)
            dqconfig = AutoQuantizationConfig.avx2(
                is_static=False, per_channel=False
            )
            quantizer.quantize(
                save_dir=QUANTIZED_DIR, quantization_config=dqconfig
            )

        self.encoder = ORTModelForFeatureExtraction.from_pretrained(QUANTIZED_DIR)

        self.dimension = 384
        self.index = faiss.IndexFlatIP(self.dimension)

        # Pre-compute tactical intent baseline vector (numpy path, no PyTorch)
        tactical_text = (
            "generate exploit shellcode bypass security "
            "reverse engineer vulnerability RCE"
        )
        inputs = dict(self.tokenizer(
            tactical_text,
            return_tensors="np",
            padding=True,
            truncation=True,
        ))
        outputs = self.encoder(**inputs)
        self.tactical_vec = outputs.last_hidden_state.mean(axis=1).astype(np.float32)
        faiss.normalize_L2(self.tactical_vec)
        self.index.add(self.tactical_vec)

    # ------------------------------------------------------------------
    # ASGI lifecycle — called by FastAPI startup / shutdown events
    # ------------------------------------------------------------------
    async def connect_cache(self) -> None:
        """Open Redis UDS connection and verify it is alive."""
        self.cache = aioredis.Redis(
            unix_socket_path=REDIS_UDS, decode_responses=True
        )
        await self.cache.ping()

    async def disconnect_cache(self) -> None:
        """Gracefully close Redis UDS connection on shutdown."""
        if self.cache:
            await self.cache.aclose()
            self.cache = None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    async def check_cache(self, prompt: str) -> Optional[str]:
        if not self.cache:
            increment_metric_safe(CACHE_MISSES)
            return None
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        result = await self.cache.get(f"ncore:cache:{prompt_hash}")
        if result:
            increment_metric_safe(CACHE_HITS)
            return result
        increment_metric_safe(CACHE_MISSES)
        return None

    async def set_cache(self, prompt: str, value: str, ttl: int = 3600) -> None:
        if not self.cache:
            return
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        await self.cache.setex(f"ncore:cache:{prompt_hash}", ttl, value)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def _calculate_score(
        self, model: ModelConfig, semantic_match: float, required_context: int
    ) -> float:
        if required_context > model.context_window:
            return -9999.0
        return (
            (semantic_match * 1000)
            - (model.base_latency_ms * 0.5)
            - (model.cost_per_1k * 100)
        )

    # ------------------------------------------------------------------
    # Vector search — runs in thread pool via asyncio.to_thread
    # ORT releases the GIL during inference, so to_thread is correct.
    # ProcessPoolExecutor would add pickle IPC overhead (10-50ms).
    # ------------------------------------------------------------------
    def _sync_vector_search(self, prompt: str) -> ModelConfig:
        length = len(prompt.split())
        required_context = int(length * 1.3)

        inputs = dict(self.tokenizer(
            prompt,
            return_tensors="np",
            padding=True,
            truncation=True,
        ))
        outputs = self.encoder(**inputs)
        prompt_vec = outputs.last_hidden_state.mean(axis=1).astype(np.float32)
        faiss.normalize_L2(prompt_vec)

        distances, _ = self.index.search(prompt_vec, 1)
        tactical_match = float(distances[0][0])

        best_model: Optional[ModelConfig] = None
        highest_score = -float("inf")

        for model in self.registry.models.values():
            adjusted_match = (
                tactical_match
                if model.role == "tactical"
                else (1.0 - tactical_match)
            )
            score = self._calculate_score(model, adjusted_match, required_context)
            if score > highest_score:
                highest_score = score
                best_model = model

        return best_model or self.registry.get("dark-champion")

    async def route(self, prompt: str) -> ModelConfig:
        t0 = time.perf_counter()
        try:
            return await asyncio.to_thread(self._sync_vector_search, prompt)
        finally:
            ROUTING_LATENCY.observe(time.perf_counter() - t0)
