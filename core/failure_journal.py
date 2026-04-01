"""NCore Genesis — Failure Journal & Learning Loop v7.5

Tracks task successes and failures in Redis, analyses recurring patterns,
and suggests system improvements.  All data is stored in Redis via UDS to
stay within the Oracle Always-Free memory budget.
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from typing import Any

import redis.asyncio as aioredis
import structlog

# ── structlog JSON logging ───────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# ── Constants ────────────────────────────────────────────────────────────────
REDIS_UDS = "/var/run/redis/redis-server.sock"
FAILURES_ZSET = "ncore:failures"
SUCCESSES_ZSET = "ncore:successes"
FAILURE_HASH_PREFIX = "ncore:failure:"
SUCCESS_HASH_PREFIX = "ncore:success:"
STATS_HASH_PREFIX = "ncore:stats:"
PATTERN_WINDOW = 100  # last N failures to analyse


# ── Redis helper ─────────────────────────────────────────────────────────────
def _redis() -> aioredis.Redis:
    return aioredis.Redis(unix_socket_path=REDIS_UDS, decode_responses=True)


# ── Record events ────────────────────────────────────────────────────────────
async def record_failure(
    task_id: str,
    task: str,
    domain: str,
    error: str,
    model_used: str,
    cost: float,
) -> None:
    """Persist a task failure with full details."""
    ts = time.time()
    r = _redis()
    try:
        await r.zadd(FAILURES_ZSET, {task_id: ts})
        await r.hset(
            f"{FAILURE_HASH_PREFIX}{task_id}",
            mapping={
                "task_id": task_id,
                "task": task,
                "domain": domain,
                "error": error,
                "model_used": model_used,
                "cost": str(cost),
                "timestamp": str(ts),
            },
        )
        log.warning(
            "journal.failure_recorded",
            task_id=task_id,
            domain=domain,
            error=error[:200],
        )
    finally:
        await r.aclose()


async def record_success(
    task_id: str,
    task: str,
    domain: str,
    model_used: str,
    cost: float,
    latency: float,
) -> None:
    """Persist a task success and update rolling domain stats."""
    ts = time.time()
    r = _redis()
    try:
        await r.zadd(SUCCESSES_ZSET, {task_id: ts})
        await r.hset(
            f"{SUCCESS_HASH_PREFIX}{task_id}",
            mapping={
                "task_id": task_id,
                "task": task,
                "domain": domain,
                "model_used": model_used,
                "cost": str(cost),
                "latency": str(latency),
                "timestamp": str(ts),
            },
        )
        # Update rolling domain stats
        stats_key = f"{STATS_HASH_PREFIX}{domain}"
        await _update_domain_stats(r, stats_key, cost, latency)
        log.info(
            "journal.success_recorded",
            task_id=task_id,
            domain=domain,
            cost=cost,
            latency=latency,
        )
    finally:
        await r.aclose()


async def _update_domain_stats(
    r: aioredis.Redis,
    stats_key: str,
    cost: float,
    latency: float,
) -> None:
    """Incrementally update domain statistics (running average)."""
    raw = await r.hgetall(stats_key)
    total = int(raw.get("total", 0)) + 1
    successes = int(raw.get("successes", 0)) + 1
    total_cost = float(raw.get("total_cost", 0)) + cost
    total_latency = float(raw.get("total_latency", 0)) + latency

    await r.hset(
        stats_key,
        mapping={
            "total": str(total),
            "successes": str(successes),
            "total_cost": str(total_cost),
            "total_latency": str(total_latency),
            "avg_cost": str(round(total_cost / total, 6)),
            "avg_latency": str(round(total_latency / total, 3)),
            "success_rate": str(round(successes / total, 4)),
        },
    )


# ── Pattern analysis ────────────────────────────────────────────────────────
async def analyze_patterns() -> dict[str, Any]:
    """Read recent failures, group by domain/error, identify recurring patterns."""
    r = _redis()
    try:
        task_ids = await r.zrevrange(FAILURES_ZSET, 0, PATTERN_WINDOW - 1)
        if not task_ids:
            return {"patterns": [], "recommendations": [], "domains_struggling": []}

        # Fetch failure details
        failures: list[dict] = []
        for tid in task_ids:
            data = await r.hgetall(f"{FAILURE_HASH_PREFIX}{tid}")
            if data:
                failures.append(data)

        # Group by domain
        domain_errors: dict[str, list[str]] = defaultdict(list)
        error_counts: Counter[str] = Counter()
        domain_counts: Counter[str] = Counter()

        for f in failures:
            domain = f.get("domain", "unknown")
            error = f.get("error", "unknown")
            domain_errors[domain].append(error)
            error_counts[error] += 1
            domain_counts[domain] += 1

        # Identify recurring patterns (errors appearing 3+ times)
        patterns = []
        for error, count in error_counts.most_common(10):
            if count >= 3:
                patterns.append({
                    "error": error[:200],
                    "count": count,
                    "domains": [
                        d for d, errs in domain_errors.items() if error in errs
                    ],
                })

        # Struggling domains (> 5 failures in window)
        domains_struggling = [d for d, c in domain_counts.items() if c > 5]

        recommendations = _generate_recommendations(patterns, failures)

        result = {
            "patterns": patterns,
            "recommendations": recommendations,
            "domains_struggling": domains_struggling,
        }
        log.info(
            "journal.analysis_complete",
            pattern_count=len(patterns),
            struggling_domains=domains_struggling,
        )
        return result
    finally:
        await r.aclose()


def _generate_recommendations(
    patterns: list[dict],
    failures: list[dict],
) -> list[str]:
    """Turn observed patterns into actionable suggestions."""
    recs: list[str] = []
    error_texts = [f.get("error", "").lower() for f in failures]

    # Tool-not-found errors
    tool_missing = sum(
        1 for e in error_texts if "not found" in e or "no such" in e or "command not found" in e
    )
    if tool_missing > 3:
        recs.append(
            "Install missing tools — multiple tasks failed due to missing commands. "
            "Run skill_discovery.discover_and_equip() for recent task types."
        )

    # Quality / model failures
    quality_fails = sum(
        1 for e in error_texts if "quality" in e or "hallucin" in e or "invalid" in e
    )
    if quality_fails > 3:
        recs.append(
            "Upgrade model tier for affected domains — recurring quality failures "
            "suggest the current model is under-capable for these tasks."
        )

    # Cost / budget
    cost_fails = sum(
        1 for e in error_texts if "budget" in e or "credit" in e or "rate_limit" in e
    )
    if cost_fails > 2:
        recs.append(
            "Adjust budget or switch to free-tier models — cost-related failures detected. "
            "Consider Gemini Flash Lite or Qwen3-Coder free endpoints."
        )

    # Timeout
    timeout_fails = sum(1 for e in error_texts if "timeout" in e or "timed out" in e)
    if timeout_fails > 3:
        recs.append(
            "Increase timeout thresholds or pre-warm Vast.ai pods — "
            "multiple tasks timing out."
        )

    # Generic catch-all
    if patterns and not recs:
        top = patterns[0]
        recs.append(
            f"Investigate recurring error: '{top['error'][:80]}' "
            f"({top['count']} occurrences across {top['domains']})."
        )

    return recs


# ── Improvement suggestions ──────────────────────────────────────────────────
async def suggest_improvements() -> list[str]:
    """Analyse patterns and return a list of actionable improvement strings."""
    analysis = await analyze_patterns()
    return analysis.get("recommendations", [])


# ── Aggregate stats ──────────────────────────────────────────────────────────
async def get_stats() -> dict[str, Any]:
    """Return overall system stats: totals, rates, costs, top failure reasons."""
    r = _redis()
    try:
        total_failures = await r.zcard(FAILURES_ZSET)
        total_successes = await r.zcard(SUCCESSES_ZSET)
        total_tasks = total_failures + total_successes
        success_rate = round(total_successes / total_tasks, 4) if total_tasks else 0.0

        # Aggregate cost and latency from successes
        success_ids = await r.zrevrange(SUCCESSES_ZSET, 0, 499)
        total_cost = 0.0
        total_latency = 0.0
        domain_costs: dict[str, float] = defaultdict(float)

        for sid in success_ids:
            data = await r.hgetall(f"{SUCCESS_HASH_PREFIX}{sid}")
            if data:
                c = float(data.get("cost", 0))
                total_cost += c
                total_latency += float(data.get("latency", 0))
                domain_costs[data.get("domain", "unknown")] += c

        avg_cost = round(total_cost / len(success_ids), 6) if success_ids else 0.0
        avg_latency = round(total_latency / len(success_ids), 3) if success_ids else 0.0

        # Top failure reasons
        failure_ids = await r.zrevrange(FAILURES_ZSET, 0, 99)
        error_counter: Counter[str] = Counter()
        for fid in failure_ids:
            data = await r.hgetall(f"{FAILURE_HASH_PREFIX}{fid}")
            if data:
                error_counter[data.get("error", "unknown")[:100]] += 1

        return {
            "total_tasks": total_tasks,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "success_rate": success_rate,
            "avg_cost": avg_cost,
            "avg_latency": avg_latency,
            "total_cost": round(total_cost, 4),
            "cost_by_domain": dict(domain_costs),
            "top_failure_reasons": error_counter.most_common(10),
        }
    finally:
        await r.aclose()
