from dataclasses import dataclass
from typing import Dict

@dataclass
class ModelConfig:
    name: str
    provider: str
    endpoint: str
    cost_per_1k: float
    context_window: int
    temperature: float = 0.7
    moe_active_params_b: float = 0.0
    role: str = ""  # tactical, director, deep_reasoning


class NCoreModelRegistry:
    def __init__(self) -> None:
        self.models: Dict[str, ModelConfig] = {
            "dolphin-3.0": ModelConfig(
                name="dolphin-3.0-mistral-24b",
                provider="vllm",
                endpoint="http://dolphin-vllm:8000",
                cost_per_1k=0.0008,
                context_window=32768,
                role="tactical",
            ),
            "dark-champion": ModelConfig(
                name="llama-3.2-dark-champion-18b-moe",
                provider="vllm",
                endpoint="http://darkchamp-vllm:8000",
                cost_per_1k=0.0015,
                context_window=128000,
                moe_active_params_b=3.0,
                role="director",
            ),
            "gpt-oss-120b": ModelConfig(
                name="gpt-oss-120b-moe",
                provider="vllm",
                endpoint="http://gptoss-vllm:8000",
                cost_per_1k=0.0045,
                context_window=200000,
                moe_active_params_b=5.1,
                role="deep_reasoning",
            ),
        }

    def get(self, key: str) -> ModelConfig:
        return self.models[key]


class AthenaMoERouter:
    def __init__(self, registry: NCoreModelRegistry) -> None:
        self.registry = registry

    def route(self, prompt: str, max_latency_ms: int = 2000) -> ModelConfig:
        text = prompt.lower()
        length = len(text.split())

        # Very lightweight domain heuristics; you can swap in embeddings later.
        if any(k in text for k in ["shellcode", "exploit", "buffer overflow", "rce", "poc"]):
            return self.registry.get("dolphin-3.0")

        if length > 20000 or any(k in text for k in ["entire repo", "full codebase", "long-running plan"]):
            return self.registry.get("dark-champion")

        if any(k in text for k in ["prove", "formal", "asymptotic", "theorem", "derivative"]):
            return self.registry.get("gpt-oss-120b")

        if max_latency_ms < 1500:
            return self.registry.get("dolphin-3.0")
        return self.registry.get("dark-champion")
