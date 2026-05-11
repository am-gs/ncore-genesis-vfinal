"""Multi-provider LLM inference router for NCore Genesis.

Routes requests across 10+ external GPU providers with intelligent
fallback, latency tracking, and cost optimization.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from typing import Any, Dict, List, Optional

import httpx
import structlog

log = structlog.get_logger()

# Provider configurations with environment variable API keys
PROVIDERS: dict[str, dict[str, Any]] = {
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key_env": "CEREBRAS_API_KEY",
        "default_model": "llama-3.3-70b",
        "priority": 1,  # highest speed
        "timeout": 30,
        "supports_streaming": True,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "priority": 2,
        "timeout": 30,
        "supports_streaming": True,
    },
    "sambanova": {
        "base_url": "https://api.sambanova.ai/v1",
        "api_key_env": "SAMBANOVA_API_KEY",
        "default_model": "Meta-Llama-3.3-70B-Instruct",
        "priority": 3,
        "timeout": 45,
        "supports_streaming": True,
    },
    "fireworks": {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "api_key_env": "FIREWORKS_API_KEY",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "priority": 4,
        "timeout": 60,
        "supports_streaming": True,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": "openrouter/free",  # free models router
        "priority": 5,
        "timeout": 60,
        "supports_streaming": True,
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "priority": 6,
        "timeout": 60,
        "supports_streaming": True,
    },
    "deepinfra": {
        "base_url": "https://api.deepinfra.com/v1/openai",
        "api_key_env": "DEEPINFRA_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "priority": 7,
        "timeout": 60,
        "supports_streaming": True,
    },
    "hyperbolic": {
        "base_url": "https://api.hyperbolic.xyz/v1",
        "api_key_env": "HYPERBOLIC_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "priority": 8,
        "timeout": 60,
        "supports_streaming": True,
    },
    "nebius": {
        "base_url": "https://api.studio.nebius.ai/v1",
        "api_key_env": "NEBIUS_API_KEY",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "priority": 9,
        "timeout": 60,
        "supports_streaming": True,
    },
    "modal": {
        "base_url": "",  # user-configured per-deployment
        "api_key_env": "MODAL_API_KEY",
        "default_model": "",  # user-configured
        "priority": 10,
        "timeout": 120,
        "supports_streaming": False,
    },
}

# Default fallback chain when no specific provider is requested
DEFAULT_FALLBACK_CHAIN = ["cerebras", "groq", "sambanova", "fireworks", "openrouter", "together"]

# Free-tier fallback chain (zero cost)
FREE_FALLBACK_CHAIN = ["openrouter", "groq"]

# Per-provider cost estimates (USD per 1M tokens)
# fmt: off
PRICING: dict[str, dict[str, float]] = {
    "cerebras":    {"input": 0.10, "output": 0.60},
    "groq":        {"input": 0.59, "output": 0.79},
    "sambanova":   {"input": 0.10, "output": 0.20},
    "fireworks":   {"input": 0.90, "output": 0.90},
    "openrouter":  {"input": 0.00, "output": 0.00},
    "together":    {"input": 0.88, "output": 0.88},
    "deepinfra":   {"input": 0.20, "output": 0.40},  # approximate
    "hyperbolic":  {"input": 0.50, "output": 0.50},  # approximate
    "nebius":      {"input": 0.30, "output": 0.60},  # approximate
    "modal":       {"input": 0.00, "output": 0.00},  # user-billed
}
# fmt: on

# Static model catalog per provider (seed data; can be extended)
PROVIDER_MODELS: dict[str, list[dict[str, str]]] = {
    "cerebras": [
        {"id": "llama-3.3-70b", "object": "model", "owned_by": "cerebras"},
        {"id": "llama-4-scout-17b-16e", "object": "model", "owned_by": "cerebras"},
    ],
    "groq": [
        {"id": "llama-3.3-70b-versatile", "object": "model", "owned_by": "groq"},
        {"id": "llama-3.1-8b-instant", "object": "model", "owned_by": "groq"},
        {"id": "mixtral-8x7b-32768", "object": "model", "owned_by": "groq"},
    ],
    "sambanova": [
        {"id": "Meta-Llama-3.3-70B-Instruct", "object": "model", "owned_by": "sambanova"},
        {"id": "DeepSeek-R1", "object": "model", "owned_by": "sambanova"},
        {"id": "Qwen-QwQ-32B", "object": "model", "owned_by": "sambanova"},
    ],
    "fireworks": [
        {"id": "accounts/fireworks/models/llama-v3p3-70b-instruct", "object": "model", "owned_by": "fireworks"},
        {"id": "accounts/fireworks/models/deepseek-r1", "object": "model", "owned_by": "fireworks"},
    ],
    "openrouter": [
        {"id": "openrouter/free", "object": "model", "owned_by": "openrouter"},
        {"id": "deepseek/deepseek-r1:free", "object": "model", "owned_by": "openrouter"},
        {"id": "qwen/qwen3-coder-480b:free", "object": "model", "owned_by": "openrouter"},
        {"id": "anthropic/claude-opus-4.6", "object": "model", "owned_by": "openrouter"},
    ],
    "together": [
        {"id": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "object": "model", "owned_by": "together"},
        {"id": "deepseek-ai/DeepSeek-R1", "object": "model", "owned_by": "together"},
    ],
    "deepinfra": [
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "object": "model", "owned_by": "deepinfra"},
        {"id": "deepseek-ai/DeepSeek-R1", "object": "model", "owned_by": "deepinfra"},
    ],
    "hyperbolic": [
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "object": "model", "owned_by": "hyperbolic"},
    ],
    "nebius": [
        {"id": "meta-llama/Llama-3.3-70B-Instruct", "object": "model", "owned_by": "nebius"},
    ],
    "modal": [],
}


def _api_key(provider: str) -> str | None:
    env = PROVIDERS[provider]["api_key_env"]
    val = os.environ.get(env)
    return val if val and val.strip() else None


def _has_api_key(provider: str) -> bool:
    return _api_key(provider) is not None


def _headers(provider: str) -> dict[str, str]:
    key = _api_key(provider)
    if not key:
        raise RuntimeError(f"No API key configured for {provider}")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://nllm.ing"
        headers["X-Title"] = "NLLM.ING"
    return headers


def _cost_estimate(provider: str, tokens_in: int, tokens_out: int) -> float:
    p = PRICING.get(provider, {"input": 0.0, "output": 0.0})
    return (tokens_in * p["input"] + tokens_out * p["output"]) / 1_000_000


class ProviderLatencyTracker:
    """Tracks per-provider latency stats (P50, P95, error rate) in-memory with automatic decay."""

    _MAX_SAMPLES = 200
    _DECAY_INTERVAL_SEC = 300  # decay old samples every 5 minutes

    def __init__(self) -> None:
        self._samples: dict[str, deque[tuple[float, float, bool]]] = {
            p: deque(maxlen=self._MAX_SAMPLES) for p in PROVIDERS
        }
        self._last_decay = time.time()
        self._lock = asyncio.Lock()

    def record(self, provider: str, latency_ms: float, success: bool) -> None:
        if provider not in self._samples:
            return
        self._samples[provider].append((time.time(), latency_ms, success))

    def get_stats(self, provider: str) -> dict[str, float]:
        samples = list(self._samples.get(provider, []))
        if not samples:
            return {"p50_ms": 0.0, "p95_ms": 0.0, "error_rate": 0.0, "count": 0.0}
        latencies = [s[1] for s in samples if s[2]]
        total = len(samples)
        errors = sum(1 for s in samples if not s[2])
        if not latencies:
            return {"p50_ms": 0.0, "p95_ms": 0.0, "error_rate": errors / total, "count": float(total)}
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.5)]
        p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)]
        return {"p50_ms": p50, "p95_ms": p95, "error_rate": errors / total, "count": float(total)}

    def get_ranked(self) -> list[str]:
        """Return providers sorted by best performance (lowest P95, lowest error rate)."""
        scored: list[tuple[float, float, str]] = []
        for provider in PROVIDERS:
            stats = self.get_stats(provider)
            if stats["count"] == 0:
                # Unseen providers get a neutral score based on static priority
                scored.append((float(PROVIDERS[provider]["priority"]), 0.0, provider))
            else:
                # Lower is better: P95 * (1 + error_rate * 5)
                score = stats["p95_ms"] * (1.0 + stats["error_rate"] * 5.0)
                scored.append((score, stats["error_rate"], provider))
        scored.sort(key=lambda t: (t[0], t[1], PROVIDERS[t[2]]["priority"]))
        return [p for _, _, p in scored]

    async def maybe_decay(self) -> None:
        async with self._lock:
            now = time.time()
            if now - self._last_decay < self._DECAY_INTERVAL_SEC:
                return
            cutoff = now - 3600  # keep last hour
            for provider in self._samples:
                old = list(self._samples[provider])
                self._samples[provider].clear()
                for ts, lat, ok in old:
                    if ts >= cutoff:
                        self._samples[provider].append((ts, lat, ok))
            self._last_decay = now


class ProviderRouter:
    """Routes chat-completion requests across external LLM providers."""

    def __init__(
        self,
        fallback_chain: list[str] | None = None,
        free_mode: bool = False,
        max_retries: int = 2,
    ) -> None:
        self.fallback_chain = fallback_chain or (FREE_FALLBACK_CHAIN if free_mode else DEFAULT_FALLBACK_CHAIN)
        self.free_mode = free_mode
        self.max_retries = max_retries
        self.latency = ProviderLatencyTracker()
        self._client: httpx.AsyncClient | None = None
        log.info("provider_router.init", fallback_chain=self.fallback_chain, free_mode=free_mode)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0), limits=limits)
        return self._client

    # ── Provider selection ─────────────────────────────────────────────

    def get_available_providers(self) -> list[str]:
        """Return list of providers with valid API keys."""
        return [p for p in PROVIDERS if _has_api_key(p)]

    def _select_provider(
        self,
        preferred: str | None,
        model: str | None,
    ) -> str | None:
        available = self.get_available_providers()
        if not available:
            log.error("provider_router.no_keys")
            return None
        if preferred and preferred in available:
            return preferred
        # Respect latency ranking but only for available providers
        ranked = [p for p in self.latency.get_ranked() if p in available]
        # Merge with fallback chain order for providers without latency data
        seen = set(ranked)
        for p in self.fallback_chain:
            if p in available and p not in seen:
                ranked.append(p)
        for p in PROVIDERS:
            if p in available and p not in seen:
                ranked.append(p)
        if ranked:
            return ranked[0]
        return available[0]

    # ── Core call ──────────────────────────────────────────────────────

    async def _try_provider(
        self,
        provider_name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Make the actual HTTP call with proper headers and error handling."""
        cfg = PROVIDERS.get(provider_name)
        if not cfg:
            raise ValueError(f"Unknown provider: {provider_name}")
        base_url = cfg["base_url"].rstrip("/")
        if not base_url:
            raise RuntimeError(f"Provider {provider_name} has no base_url configured")
        url = f"{base_url}/chat/completions"
        headers = _headers(provider_name)
        timeout = cfg["timeout"]
        start = time.perf_counter()
        try:
            r = await self.client.post(url, headers=headers, json=payload, timeout=timeout)
            latency_ms = (time.perf_counter() - start) * 1000
            if r.status_code == 429:
                log.warning("provider_router.rate_limited", provider=provider_name, status=r.status_code)
                self.latency.record(provider_name, latency_ms, False)
                raise ProviderRateLimit(provider_name)
            if r.status_code >= 500:
                log.warning("provider_router.server_error", provider=provider_name, status=r.status_code, body=r.text[:200])
                self.latency.record(provider_name, latency_ms, False)
                raise ProviderServerError(provider_name, r.status_code)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            cost = _cost_estimate(provider_name, tokens_in, tokens_out)
            self.latency.record(provider_name, latency_ms, True)
            return {
                "content": data["choices"][0]["message"]["content"],
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "model": data.get("model", payload.get("model", "")),
                "provider": provider_name,
                "latency_ms": round(latency_ms, 2),
                "cost_usd": round(cost, 8),
                "raw": data,
            }
        except (httpx.TimeoutException, asyncio.TimeoutError):
            latency_ms = (time.perf_counter() - start) * 1000
            log.warning("provider_router.timeout", provider=provider_name, latency_ms=int(latency_ms))
            self.latency.record(provider_name, latency_ms, False)
            raise ProviderTimeout(provider_name)
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            log.warning("provider_router.network_error", provider=provider_name, error=str(exc))
            self.latency.record(provider_name, latency_ms, False)
            raise ProviderNetworkError(provider_name, str(exc))

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        preferred_provider: str | None = None,
    ) -> dict[str, Any]:
        """Route a chat-completion request to the best available provider with fallback."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream"] = True
        provider = self._select_provider(preferred_provider, model)
        if not provider:
            raise RuntimeError("No providers available — check API keys")
        last_error: Exception | None = None
        chain = [provider] + [p for p in self.fallback_chain if p != provider and p in self.get_available_providers()]
        for p in chain[: self.max_retries + 1]:
            try:
                return await self._try_provider(p, payload)
            except ProviderRetryable as exc:
                last_error = exc
                log.info("provider_router.failing_over", from_provider=p, error=exc.__class__.__name__)
                continue
        log.error("provider_router.exhausted", chain=chain, last_error=str(last_error))
        raise RuntimeError(f"All providers exhausted. Last error: {last_error}")

    # ── Streaming ──────────────────────────────────────────────────────

    async def stream_chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        preferred_provider: str | None = None,
    ):
        """Yield SSE-style streaming chunks from the best provider."""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        provider = self._select_provider(preferred_provider, model)
        if not provider:
            raise RuntimeError("No providers available — check API keys")
        cfg = PROVIDERS[provider]
        if not cfg["supports_streaming"]:
            # Fall back to non-streaming and yield one chunk
            result = await self.chat_completion(
                model, messages, temperature, max_tokens, stream=False, preferred_provider=provider
            )
            yield {
                "choices": [{"delta": {"content": result["content"]}, "finish_reason": "stop", "index": 0}],
                "model": result["model"],
                "provider": provider,
            }
            return
        base_url = cfg["base_url"].rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = _headers(provider)
        start = time.perf_counter()
        async with self.client.stream("POST", url, headers=headers, json=payload, timeout=cfg["timeout"]) as response:
            latency_ms = (time.perf_counter() - start) * 1000
            if response.status_code >= 400:
                self.latency.record(provider, latency_ms, False)
                text = await response.aread()
                log.warning("provider_router.stream_error", provider=provider, status=response.status_code, body=text[:200])
                raise ProviderServerError(provider, response.status_code)
            self.latency.record(provider, latency_ms, True)
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    try:
                        parsed = json.loads(chunk)
                        parsed["provider"] = provider
                        yield parsed
                    except json.JSONDecodeError:
                        continue

    # ── Health ───────────────────────────────────────────────────────

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Parallel lightweight health checks across all configured providers."""
        results: dict[str, dict[str, Any]] = {}
        sem = asyncio.Semaphore(10)

        async def _check_one(name: str) -> None:
            async with sem:
                cfg = PROVIDERS[name]
                if not _has_api_key(name):
                    results[name] = {"status": "no_key", "latency_ms": None}
                    return
                base_url = cfg["base_url"].rstrip("/")
                if not base_url:
                    results[name] = {"status": "no_url", "latency_ms": None}
                    return
                start = time.perf_counter()
                try:
                    # Try a minimal chat call; if that fails, fall back to HEAD on base_url
                    r = await self.client.post(
                        f"{base_url}/chat/completions",
                        headers=_headers(name),
                        json={
                            "model": cfg["default_model"],
                            "messages": [{"role": "user", "content": "hi"}],
                            "max_tokens": 1,
                        },
                        timeout=min(cfg["timeout"], 10),
                    )
                    latency_ms = (time.perf_counter() - start) * 1000
                    if r.status_code < 400 or r.status_code == 429:
                        results[name] = {"status": "ok", "latency_ms": round(latency_ms, 2)}
                    else:
                        results[name] = {"status": f"http_{r.status_code}", "latency_ms": round(latency_ms, 2)}
                except (httpx.TimeoutException, asyncio.TimeoutError):
                    latency_ms = (time.perf_counter() - start) * 1000
                    results[name] = {"status": "timeout", "latency_ms": round(latency_ms, 2)}
                except httpx.NetworkError as exc:
                    latency_ms = (time.perf_counter() - start) * 1000
                    results[name] = {"status": "network_error", "latency_ms": round(latency_ms, 2), "error": str(exc)}
                except Exception as exc:
                    results[name] = {"status": "error", "latency_ms": None, "error": str(exc)}

        await asyncio.gather(*[_check_one(p) for p in PROVIDERS], return_exceptions=True)
        return results

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Custom exceptions ─────────────────────────────────────────────────

class ProviderRetryable(Exception):
    """Base for transient provider errors that should trigger failover."""
    pass


class ProviderRateLimit(ProviderRetryable):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limited on {provider}")


class ProviderServerError(ProviderRetryable):
    def __init__(self, provider: str, status: int) -> None:
        self.provider = provider
        self.status = status
        super().__init__(f"Server error {status} on {provider}")


class ProviderTimeout(ProviderRetryable):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Timeout on {provider}")


class ProviderNetworkError(ProviderRetryable):
    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        super().__init__(f"Network error on {provider}: {reason}")
