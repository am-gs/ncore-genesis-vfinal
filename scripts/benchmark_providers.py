#!/usr/bin/env python3
"""Standalone provider benchmark script.

Runs the same prompt across all configured providers and reports
P50/P95 latency, tokens generated, error rate, and a recommendation.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Ensure repo root is on path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.provider_router import ProviderRouter, PROVIDERS  # noqa: E402

PROMPT = (
    "Write a Python function that implements quicksort and returns the sorted list. "
    "Only return code, no explanation."
)

MODELS = {
    "cerebras": "llama-3.3-70b",
    "groq": "llama-3.3-70b-versatile",
    "sambanova": "Meta-Llama-3.3-70B-Instruct",
    "fireworks": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "openrouter": "openrouter/free",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "deepinfra": "meta-llama/Llama-3.3-70B-Instruct",
    "hyperbolic": "meta-llama/Llama-3.3-70B-Instruct",
    "nebius": "meta-llama/Llama-3.3-70B-Instruct",
    "modal": PROVIDERS["modal"]["default_model"],
}

WARMUP_RUNS = 1
MEASURE_RUNS = 3


async def _warmup(provider: str, router: ProviderRouter) -> dict | None:
    model = MODELS.get(provider) or PROVIDERS[provider]["default_model"]
    try:
        await router.chat_completion(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            temperature=0.7,
            max_tokens=256,
            preferred_provider=provider,
        )
        return None
    except Exception as exc:
        return {"error": str(exc)}


async def _measure(provider: str, router: ProviderRouter) -> dict:
    model = MODELS.get(provider) or PROVIDERS[provider]["default_model"]
    start = time.perf_counter()
    try:
        result = await router.chat_completion(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            temperature=0.7,
            max_tokens=256,
            preferred_provider=provider,
        )
        wall_ms = (time.perf_counter() - start) * 1000
        return {
            "wall_ms": round(wall_ms, 2),
            "provider_latency_ms": result["latency_ms"],
            "tokens_out": result["tokens_out"],
            "cost_usd": result["cost_usd"],
            "error": None,
        }
    except Exception as exc:
        wall_ms = (time.perf_counter() - start) * 1000
        return {
            "wall_ms": round(wall_ms, 2),
            "provider_latency_ms": 0.0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "error": str(exc),
        }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(len(s) * p)
    return s[min(idx, len(s) - 1)]


async def main() -> None:
    router = ProviderRouter()
    available = router.get_available_providers()
    if not available:
        print(json.dumps({"status": "error", "message": "No providers configured — set at least one API key"}))
        sys.exit(1)

    print(f"Benchmarking {len(available)} provider(s): {', '.join(available)}", file=sys.stderr)

    # Warmup
    for p in available:
        await _warmup(p, router)
        await asyncio.sleep(0.5)

    # Measure
    raw: dict[str, list[dict]] = defaultdict(list)
    for p in available:
        for _ in range(MEASURE_RUNS):
            raw[p].append(await _measure(p, router))
            await asyncio.sleep(1.0)

    await router.close()

    # Aggregate
    report: dict[str, Any] = {}
    for p in available:
        runs = raw[p]
        errors = [r for r in runs if r["error"]]
        ok = [r for r in runs if not r["error"]]
        wall_ok = [r["wall_ms"] for r in ok]
        provider_lat_ok = [r["provider_latency_ms"] for r in ok]
        tokens_ok = [r["tokens_out"] for r in ok]
        report[p] = {
            "runs": MEASURE_RUNS,
            "errors": len(errors),
            "error_rate": round(len(errors) / MEASURE_RUNS, 2),
            "wall_p50_ms": round(_percentile(wall_ok, 0.5), 2) if wall_ok else None,
            "wall_p95_ms": round(_percentile(wall_ok, 0.95), 2) if wall_ok else None,
            "provider_p50_ms": round(_percentile(provider_lat_ok, 0.5), 2) if provider_lat_ok else None,
            "provider_p95_ms": round(_percentile(provider_lat_ok, 0.95), 2) if provider_lat_ok else None,
            "avg_tokens_out": round(sum(tokens_ok) / len(tokens_ok), 1) if tokens_ok else None,
            "total_cost_usd": round(sum(r["cost_usd"] for r in runs), 8),
        }

    # Recommendation: best = lowest p95 latency + lowest error rate + lowest cost
    scored = []
    for p, stats in report.items():
        if stats["error_rate"] >= 1.0:
            score = float("inf")
        else:
            lat = stats["wall_p95_ms"] or stats["wall_p50_ms"] or 5000.0
            score = lat * (1.0 + stats["error_rate"] * 5.0) + (stats["total_cost_usd"] * 100000.0)
        scored.append((score, p))
    scored.sort()
    recommendation = scored[0][1] if scored else None

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "providers": report,
        "recommendation": recommendation,
        "recommendation_reason": (
            f"{recommendation} has the best blend of low P95 latency, reliability, and cost."
            if recommendation else "No viable provider found."
        ),
    }

    print(json.dumps(output, indent=2))

    out_path = "/tmp/provider_benchmark.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
