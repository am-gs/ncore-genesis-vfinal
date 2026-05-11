#!/usr/bin/env python3
"""Swarm benchmark: 10 concurrent agents sending sequential prompts to providers.

Measures end-to-end throughput, success rate, and average latency per provider.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.provider_router import ProviderRouter  # noqa: E402

PROMPTS = [
    "Summarize quantum computing in one sentence.",
    "Write a haiku about machine learning.",
    "What is the capital of France? Reply with one word.",
    "List three benefits of async programming.",
    "Translate 'hello world' to Spanish.",
]

MAX_TOKENS = 64
CONCURRENCY = 10


async def _agent(name: str, provider: str, router: ProviderRouter) -> dict[str, Any]:
    latencies: list[float] = []
    errors = 0
    total_tokens = 0
    for prompt in PROMPTS:
        start = time.perf_counter()
        try:
            result = await router.chat_completion(
                model="",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=MAX_TOKENS,
                preferred_provider=provider,
            )
            latencies.append(result["latency_ms"])
            total_tokens += result["tokens_out"]
        except Exception as exc:
            errors += 1
            latencies.append((time.perf_counter() - start) * 1000)
    return {
        "agent": name,
        "provider": provider,
        "prompts": len(PROMPTS),
        "errors": errors,
        "success_rate": round((len(PROMPTS) - errors) / len(PROMPTS), 2),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "max_latency_ms": round(max(latencies), 2) if latencies else 0.0,
        "total_tokens_out": total_tokens,
    }


async def main() -> None:
    router = ProviderRouter()
    available = router.get_available_providers()
    if not available:
        print(json.dumps({"status": "error", "message": "No providers configured"}))
        sys.exit(1)

    print(f"Swarm benchmark: {CONCURRENCY} agents across {len(available)} provider(s)", file=sys.stderr)

    # Distribute agents round-robin across available providers
    assignments = [(f"agent-{i+1}", available[i % len(available)]) for i in range(CONCURRENCY)]

    start = time.perf_counter()
    results = await asyncio.gather(*[_agent(name, provider, router) for name, provider in assignments])
    wall_sec = time.perf_counter() - start
    await router.close()

    # Aggregate per provider
    per_provider: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        per_provider.setdefault(r["provider"], []).append(r)

    provider_stats = {}
    for p, runs in per_provider.items():
        provider_stats[p] = {
            "agents": len(runs),
            "total_prompts": sum(r["prompts"] for r in runs),
            "total_errors": sum(r["errors"] for r in runs),
            "success_rate": round(sum(r["success_rate"] for r in runs) / len(runs), 2),
            "avg_latency_ms": round(sum(r["avg_latency_ms"] for r in runs) / len(runs), 2),
            "max_latency_ms": round(max(r["max_latency_ms"] for r in runs), 2),
            "total_tokens_out": sum(r["total_tokens_out"] for r in runs),
        }

    overall = {
        "agents": CONCURRENCY,
        "providers_tested": list(per_provider.keys()),
        "total_prompts": sum(r["prompts"] for r in results),
        "total_errors": sum(r["errors"] for r in results),
        "wall_time_sec": round(wall_sec, 2),
        "prompts_per_sec": round(sum(r["prompts"] for r in results) / wall_sec, 2),
        "success_rate": round(sum(r["success_rate"] for r in results) / len(results), 2),
    }

    # Fastest overall provider by average latency among those with >0 success
    viable = [(s["avg_latency_ms"], p) for p, s in provider_stats.items() if s["success_rate"] > 0]
    fastest = min(viable)[1] if viable else None

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall": overall,
        "per_provider": provider_stats,
        "fastest_provider": fastest,
    }

    print(json.dumps(output, indent=2))

    out_path = "/tmp/swarm_benchmark.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
