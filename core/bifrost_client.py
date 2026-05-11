"""Bifrost Gateway Client for NLLM.ING

Routes all LLM calls through Bifrost (local multi-provider proxy) for:
- Intelligent provider routing with latency-based ranking
- Budget enforcement ($50/month cap)
- Auto-failover across 10+ external providers
- Unified provider management via single OpenAI-compatible API

Fallback: If Bifrost is unreachable, routes directly to OpenRouter.
"""
from __future__ import annotations

import os
import json
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

BIFROST_URL = os.environ.get("BIFROST_URL", "http://localhost:8000")
OPENROUTER_URL = "https://openrouter.ai/api/v1"
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")


class BifrostClient:
    """Drop-in replacement for direct OpenRouter/Anthropic calls.

    All methods prefer Bifrost, fall back to OpenRouter on 502/503/timeout.
    Budget tracking parsed from _bifrost_cost_usd in the response body.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 fallback_enabled: bool = True):
        self.base_url = (base_url or BIFROST_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("BIFROST_API_KEY", "")
        self.fallback = fallback_enabled
        self._client: httpx.AsyncClient | None = None
        self._budget: dict[str, Any] = {}
        log.info("bifrost_client.init", url=self.base_url, fallback=fallback_enabled)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
            self._client = httpx.AsyncClient(timeout=120, limits=limits)
        return self._client

    # ── Core: chat completion ────────────────────────────────────────────

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> dict:
        """Send chat completion through Bifrost → OpenRouter fallback.

        Returns {content, tokens_in, tokens_out, model, provider, cached, cost_usd, latency_ms}
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # Try Bifrost first
        try:
            r = await self.client.post(
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://nllm.ing",
                    "X-Title": "NLLM.ING",
                },
                json=payload,
                timeout=120.0,
            )
            if r.status_code == 200:
                data = r.json()
                usage = data.get("usage", {})
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0),
                    "model": data.get("model", model),
                    "provider": data.get("_bifrost_provider", "bifrost"),
                    "cached": False,
                    "cost_usd": data.get("_bifrost_cost_usd", 0.0),
                    "latency_ms": data.get("_bifrost_latency_ms", 0.0),
                    "source": "bifrost",
                }
            # Bifrost error → fallback
            log.warning("bifrost.error", status=r.status_code, body=r.text[:200])
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            log.warning("bifrost.unreachable", error=str(e))

        # Fallback to OpenRouter
        if not self.fallback:
            raise RuntimeError("Bifrost unreachable and fallback disabled")

        log.info("bifrost.fallback", target="openrouter", model=model)
        r = await self.client.post(
            f"{OPENROUTER_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "HTTP-Referer": "https://nllm.ing",
                "X-Title": "NLLM.ING",
            },
            json=payload,
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage", {})
        return {
            "content": data["choices"][0]["message"]["content"],
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "model": data.get("model", model),
            "provider": "openrouter",
            "cached": False,
            "cost_usd": 0.0,  # Will be estimated downstream
            "latency_ms": 0.0,
            "source": "openrouter",
        }

    # ── Status & health ──────────────────────────────────────────────────

    async def get_health(self) -> dict:
        try:
            r = await self.client.get(f"{self.base_url}/health", timeout=5.0)
            if r.status_code == 200:
                return r.json()
            return {"status": "error", "code": r.status_code, "body": r.text[:200]}
        except Exception as e:
            return {"status": "down", "error": str(e)}

    async def get_budget_status(self) -> dict:
        """Fetch remaining budget from Bifrost."""
        try:
            r = await self.client.get(f"{self.base_url}/metrics", timeout=5.0)
            if r.status_code == 200:
                return {"metrics_raw": r.text}
            return {"status": "error", "code": r.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def list_models(self) -> list[dict]:
        try:
            r = await self.client.get(f"{self.base_url}/v1/models", timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", [])
            return []
        except Exception:
            return []

    async def get_cache_stats(self) -> dict:
        """Semantic cache hit rate and savings (not available in v2)."""
        return {"status": "not_implemented", "note": "Cache stats moved to provider_router.latency tracker"}

    async def get_providers(self) -> dict:
        """List configured providers and their health."""
        try:
            r = await self.client.get(f"{self.base_url}/providers", timeout=10.0)
            if r.status_code == 200:
                return r.json()
            return {"status": "error", "code": r.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Singleton (import once, reuse) ───────────────────────────────────────
_BIFROST: BifrostClient | None = None


def get_bifrost() -> BifrostClient:
    global _BIFROST
    if _BIFROST is None:
        _BIFROST = BifrostClient()
    return _BIFROST


async def bifrost_chat(
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> dict:
    """One-shot convenience: chat through Bifrost with fallback."""
    client = get_bifrost()
    return await client.chat_completion(model, messages, temperature, max_tokens)


if __name__ == "__main__":
    import asyncio

    async def _test():
        bc = BifrostClient()
        health = await bc.get_health()
        print(json.dumps(health, indent=2))
        providers = await bc.get_providers()
        print(json.dumps(providers, indent=2))
        models = await bc.list_models()
        print(f"Models available: {len(models)}")

    asyncio.run(_test())
