#!/usr/bin/env python3
"""Swarm benchmark: deploy 10 agents across 10 GPU inference providers.

Each agent runs 5 sequential tasks and reports latency, throughput, and reliability.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.provider_router import ProviderRouter, PROVIDERS, PRICING  # noqa: E402

PROMPTS: list[dict[str, str]] = [
    {
        "type": "code_generation",
        "prompt": "Write a Python function that reverses a string using slicing. Only return the code.",
    },
    {
        "type": "reasoning",
        "prompt": "If a train travels 60 km in 30 minutes, what is its average speed in km/h? Show your reasoning in one sentence.",
    },
    {
        "type": "summarization",
        "prompt": "Summarize the following in one sentence: The rapid advancement of artificial intelligence is transforming industries worldwide, from healthcare diagnostics to autonomous vehicles and natural language processing.",
    },
    {
        "type": "json_extraction",
        "prompt": "Extract the name and age from this text and return ONLY valid JSON: 'Alice is 30 years old.'",
    },
    {
        "type": "creative_writing",
        "prompt": "Write a single-sentence haiku about a robot learning to paint.",
    },
]

MAX_TOKENS = 128
CONCURRENCY = 10


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = int(len(s) * p)
    return s[min(idx, len(s) - 1)]


async def _agent(
    name: str,
    provider: str,
    router: ProviderRouter,
) -> dict[str, Any]:
    latencies: list[float] = []
    ttfts: list[float] = []
    errors = 0
    total_tokens = 0
    per_prompt: list[dict[str, Any]] = []

    for task in PROMPTS:
        prompt = task["prompt"]
        start = time.perf_counter()
        ttft_ms: float | None = None
        try:
            result = await router.chat_completion(
                model="",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=MAX_TOKENS,
                preferred_provider=provider,
            )
            wall_ms = (time.perf_counter() - start) * 1000
            latencies.append(wall_ms)
            total_tokens += result.get("tokens_out", 0)
            per_prompt.append(
                {
                    "task_type": task["type"],
                    "latency_ms": round(wall_ms, 2),
                    "ttft_ms": None,
                    "tokens_out": result.get("tokens_out", 0),
                    "success": True,
                }
            )
        except Exception as exc:
            errors += 1
            wall_ms = (time.perf_counter() - start) * 1000
            latencies.append(wall_ms)
            per_prompt.append(
                {
                    "task_type": task["type"],
                    "latency_ms": round(wall_ms, 2),
                    "ttft_ms": None,
                    "tokens_out": 0,
                    "success": False,
                    "error": str(exc)[:200],
                }
            )

    return {
        "agent": name,
        "provider": provider,
        "prompts": len(PROMPTS),
        "errors": errors,
        "success_rate": round((len(PROMPTS) - errors) / len(PROMPTS), 4),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": round(_percentile(latencies, 0.95), 2) if latencies else 0.0,
        "max_latency_ms": round(max(latencies), 2) if latencies else 0.0,
        "total_tokens_out": total_tokens,
        "per_prompt": per_prompt,
    }


def _estimated_cost_per_1m(provider: str, avg_tokens_out: int) -> float:
    """Estimate cost per 1M tokens produced, using approximate input/output split."""
    p = PRICING.get(provider, {"input": 0.0, "output": 0.0})
    # Assume input tokens are roughly 2x output tokens (prompt + context)
    input_tokens = avg_tokens_out * 2
    output_tokens = avg_tokens_out
    return (input_tokens * p["input"] + output_tokens * p["output"]) / max(avg_tokens_out, 1)


async def main() -> None:
    router = ProviderRouter()
    available = router.get_available_providers()
    if not available:
        print(json.dumps({"status": "error", "message": "No providers configured — set at least one API key"}))
        sys.exit(1)

    print(
        f"Swarm benchmark: {CONCURRENCY} agents across {len(available)} provider(s)",
        file=sys.stderr,
    )

    # Distribute agents round-robin across available providers
    assignments = [
        (f"agent-{i+1}", available[i % len(available)]) for i in range(CONCURRENCY)
    ]

    start = time.perf_counter()
    results = await asyncio.gather(
        *[_agent(name, provider, router) for name, provider in assignments]
    )
    wall_sec = time.perf_counter() - start
    await router.close()

    # Aggregate per provider
    per_provider: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        per_provider.setdefault(r["provider"], []).append(r)

    provider_stats: list[dict[str, Any]] = []
    for p, runs in per_provider.items():
        all_latencies: list[float] = []
        for r in runs:
            all_latencies.extend(
                [pp["latency_ms"] for pp in r["per_prompt"] if pp["success"]]
            )

        total_prompts = sum(r["prompts"] for r in runs)
        total_errors = sum(r["errors"] for r in runs)
        total_tokens = sum(r["total_tokens_out"] for r in runs)
        avg_tokens = total_tokens / max(len(runs), 1)
        success_rate = round(
            sum(r["success_rate"] for r in runs) / len(runs), 4
        )
        avg_lat = round(
            sum(r["avg_latency_ms"] for r in runs) / len(runs), 2
        )
        p95 = round(_percentile(all_latencies, 0.95), 2) if all_latencies else 0.0
        max_lat = round(max(r["max_latency_ms"] for r in runs), 2)
        cost_per_1m = round(_estimated_cost_per_1m(p, int(avg_tokens)), 4)

        # Overall score: lower is better (latency * success_rate / cost)
        # Penalize high cost and low success rate
        score = round(
            (avg_lat * (1.0 + (1.0 - success_rate) * 10.0))
            / max(cost_per_1m, 0.0001),
            2,
        )

        provider_stats.append(
            {
                "provider": p,
                "agents": len(runs),
                "total_prompts": total_prompts,
                "total_errors": total_errors,
                "success_rate": success_rate,
                "avg_latency_ms": avg_lat,
                "p95_latency_ms": p95,
                "max_latency_ms": max_lat,
                "total_tokens_out": total_tokens,
                "cost_per_1m_tokens_usd": cost_per_1m,
                "score": score,
            }
        )

    # Sort by score descending (higher score = better)
    provider_stats.sort(key=lambda x: x["score"], reverse=True)

    overall = {
        "agents": CONCURRENCY,
        "providers_tested": list(per_provider.keys()),
        "total_prompts": sum(r["prompts"] for r in results),
        "total_errors": sum(r["errors"] for r in results),
        "wall_time_sec": round(wall_sec, 2),
        "prompts_per_sec": round(sum(r["prompts"] for r in results) / wall_sec, 2),
        "success_rate": round(sum(r["success_rate"] for r in results) / len(results), 4),
    }

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall": overall,
        "leaderboard": provider_stats,
    }

    # Print ranked leaderboard
    print("\n" + "=" * 80)
    print("PROVIDER LEADERBOARD")
    print("=" * 80)
    print(
        f"{'Rank':<6}{'Provider':<15}{'Avg Lat':<12}{'P95 Lat':<12}{'Success':<10}{'Cost/1M':<12}{'Score':<10}"
    )
    print("-" * 80)
    for i, s in enumerate(provider_stats, 1):
        print(
            f"{i:<6}{s['provider']:<15}{s['avg_latency_ms']:<12.2f}{s['p95_latency_ms']:<12.2f}"
            f"{s['success_rate']*100:<9.1f}%{s['cost_per_1m_tokens_usd']:<12.4f}{s['score']:<10.2f}"
        )
    print("=" * 80)

    # Recommendation per task type
    task_type_best: dict[str, tuple[float, str]] = {}
    for task_type in ["code_generation", "reasoning", "summarization", "json_extraction", "creative_writing"]:
        best_lat = float("inf")
        best_provider = None
        for p in per_provider:
            for r in per_provider[p]:
                for pp in r["per_prompt"]:
                    if pp["task_type"] == task_type and pp["success"] and pp["latency_ms"] < best_lat:
                        best_lat = pp["latency_ms"]
                        best_provider = p
        if best_provider:
            task_type_best[task_type] = (best_lat, best_provider)

    print("\nRECOMMENDATIONS")
    print("-" * 40)
    for task_type, (lat, provider) in task_type_best.items():
        print(f"Best provider for {task_type}: {provider} ({lat:.0f}ms)")
    if provider_stats:
        print(f"Overall best provider: {provider_stats[0]['provider']}")
    print("-" * 40)

    print(json.dumps(output, indent=2))

    out_path = "/tmp/swarm_benchmark_report.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved full report to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
