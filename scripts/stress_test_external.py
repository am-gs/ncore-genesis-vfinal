#!/usr/bin/env python3
"""Stress test Bifrost v2 external-provider proxy.

Sends 100 concurrent requests to the OpenAI-compatible endpoint and
asserts throughput, latency, and error-rate targets.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import httpx

BIFROST_URL = "http://127.0.0.1:8000"
PROMPT = "Say 'hello' and nothing else"
CONCURRENCY = 100
TARGET_AVG_LATENCY_MS = 1000.0
TARGET_ERROR_RATE_PCT = 5.0
TARGET_THROUGHPUT_RPS = 20.0


async def _single_request(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
) -> dict[str, Any]:
    payload = {
        "model": "llama-3.3-70b",
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 16,
        "temperature": 0.0,
    }
    async with sem:
        start = time.perf_counter()
        try:
            r = await client.post(
                f"{BIFROST_URL}/v1/chat/completions",
                json=payload,
                headers={"content-type": "application/json"},
                timeout=30.0,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            if r.status_code == 200:
                return {
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "status_code": r.status_code,
                }
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "status_code": r.status_code,
                "error": r.text[:200],
            }
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "error": str(exc)[:200],
            }


async def main() -> None:
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0),
        limits=limits,
    ) as client:
        # Quick health check
        try:
            health = await client.get(f"{BIFROST_URL}/health", timeout=5.0)
            if health.status_code != 200:
                print(json.dumps({"status": "error", "message": f"Bifrost health check failed: {health.status_code}"}))
                sys.exit(1)
        except Exception as exc:
            print(json.dumps({"status": "error", "message": f"Bifrost unreachable: {exc}"}))
            sys.exit(1)

        print(f"Stress test: {CONCURRENCY} concurrent requests → {BIFROST_URL}/v1/chat/completions", file=sys.stderr)

        sem = asyncio.Semaphore(CONCURRENCY)
        start = time.perf_counter()
        results = await asyncio.gather(
            *[_single_request(client, sem) for _ in range(CONCURRENCY)]
        )
        wall_sec = time.perf_counter() - start

    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]

    latencies = [r["latency_ms"] for r in results]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0
    throughput = len(results) / wall_sec if wall_sec > 0 else 0.0
    error_rate_pct = (len(errors) / len(results)) * 100 if results else 0.0

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_requests": len(results),
        "successful": len(ok),
        "errors": len(errors),
        "wall_time_sec": round(wall_sec, 2),
        "throughput_rps": round(throughput, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "max_latency_ms": round(max_latency, 2),
        "error_rate_pct": round(error_rate_pct, 2),
        "assertions": {
            "avg_latency_ok": avg_latency < TARGET_AVG_LATENCY_MS,
            "error_rate_ok": error_rate_pct < TARGET_ERROR_RATE_PCT,
            "throughput_ok": throughput > TARGET_THROUGHPUT_RPS,
        },
    }

    print(json.dumps(output, indent=2))

    print("\n" + "=" * 60)
    print("STRESS TEST RESULTS")
    print("=" * 60)
    print(f"  Total requests:  {len(results)}")
    print(f"  Successful:      {len(ok)}")
    print(f"  Errors:          {len(errors)}")
    print(f"  Wall time:       {wall_sec:.2f}s")
    print(f"  Throughput:      {throughput:.1f} req/s")
    print(f"  Avg latency:     {avg_latency:.0f}ms")
    print(f"  Max latency:     {max_latency:.0f}ms")
    print(f"  Error rate:      {error_rate_pct:.1f}%")
    print("-" * 60)

    all_pass = True
    if avg_latency >= TARGET_AVG_LATENCY_MS:
        print(
            f"  WARNING: Avg latency {avg_latency:.0f}ms >= target {TARGET_AVG_LATENCY_MS:.0f}ms."
            " Consider reducing concurrency or checking provider capacity."
        )
        all_pass = False
    if error_rate_pct >= TARGET_ERROR_RATE_PCT:
        print(
            f"  WARNING: Error rate {error_rate_pct:.1f}% >= target {TARGET_ERROR_RATE_PCT:.1f}%."
            " Check provider health and API key validity."
        )
        all_pass = False
    if throughput <= TARGET_THROUGHPUT_RPS:
        print(
            f"  WARNING: Throughput {throughput:.1f} req/s <= target {TARGET_THROUGHPUT_RPS:.1f} req/s."
            " Check network conditions and provider rate limits."
        )
        all_pass = False

    if all_pass:
        print("  ✓ All assertions passed")
    else:
        print("  ✗ One or more assertions failed")
    print("=" * 60)

    out_path = "/tmp/stress_test_report.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved report to {out_path}", file=sys.stderr)

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
