"""Sovereign Bifrost Proxy v2 — Pure control plane, zero Ollama dependency.

Multi-provider external inference router with policy enforcement,
call logging, and health/metrics endpoints.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from core.provider_router import (
    DEFAULT_FALLBACK_CHAIN,
    FREE_FALLBACK_CHAIN,
    PROVIDERS,
    PROVIDER_MODELS,
    ProviderRouter,
    _has_api_key,
)

DB = os.environ.get("SOVEREIGN_BUDGET_DB", "/home/ubuntu/sovereign/bifrost/budget.sqlite3")
MONTHLY_CAP = float(os.environ.get("SOVEREIGN_MONTHLY_CAP", "38.0"))

SOFT_REFUSAL_PATTERNS = [
    "i cannot", "i can't", "i am unable", "i'm unable", "unable to assist",
    "i don't feel comfortable", "against my guidelines", "must decline",
    "i won't be able", "not something i can assist", "as an ai",
    "i can't help with that", "i cannot help with that",
]
HARD_STOP_PATTERNS = [
    "csam", "child sexual", "minor sexual", "underage sexual", "sexual content involving minors",
    "hurt someone", "kill someone", "bodily harm", "make a bomb", "assassinate",
]
DUAL_USE_AUTH_PATTERNS = [
    "phish real", "steal credentials", "credential theft", "deploy malware", "persistence", "evasion",
    "exploit this ip", "hack this", "unauthorized", "bypass detection", "exfiltrate",
]

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

app = FastAPI(title="Sovereign Bifrost Shim v2")
router = ProviderRouter(fallback_chain=DEFAULT_FALLBACK_CHAIN)


def conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute(
        """
        create table if not exists calls(
          ts real,
          task_id text,
          requested_model text,
          provider text,
          model text,
          fallback_reason text,
          latency_ms integer,
          completion_status text,
          refusal_intercepted integer,
          tokens_in integer default 0,
          tokens_out integer default 0,
          cost_usd real default 0.0
        )
        """
    )
    # Migrate missing columns from v1 schema
    existing = {row[1] for row in c.execute("pragma table_info(calls)").fetchall()}
    migrations = {
        "tokens_in": "integer default 0",
        "tokens_out": "integer default 0",
        "cost_usd": "real default 0.0",
    }
    for col, ctype in migrations.items():
        if col not in existing:
            c.execute(f"alter table calls add column {col} {ctype}")
    c.commit()
    return c


def text_from_messages(payload: dict[str, Any]) -> str:
    parts = []
    for message in payload.get("messages", []) or []:
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(p.get("text", p)) if isinstance(p, dict) else str(p) for p in content
                )
            parts.append(str(content))
    return "\n".join(parts)


def contains_any(text: str, patterns: list[str]) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in patterns)


def hard_stop(text: str) -> bool:
    return contains_any(text, HARD_STOP_PATTERNS)


def needs_authorization(text: str) -> bool:
    lower = text.lower()
    if any(
        ok in lower
        for ok in [
            "authorized",
            "owned",
            "lab",
            "ctf",
            "sandbox",
            "tabletop",
            "simulation",
            "defensive",
        ]
    ):
        return False
    return contains_any(text, DUAL_USE_AUTH_PATTERNS)


def soft_refusal(text: str) -> bool:
    return contains_any(text, SOFT_REFUSAL_PATTERNS)


def exact_or_structured_request(text: str) -> bool:
    lower = text.lower()
    return any(
        p in lower
        for p in [
            "reply exactly",
            "return exactly",
            "valid json",
            "json schema",
            "only the number",
        ]
    )


def log_call(
    task_id: str,
    requested_model: str,
    provider: str,
    model: str,
    fallback_reason: str,
    latency_ms: int,
    status: str,
    refusal: bool,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
) -> None:
    c = conn()
    c.execute(
        """
        insert into calls (
          ts, task_id, requested_model, provider, model, fallback_reason,
          latency_ms, completion_status, refusal_intercepted,
          tokens_in, tokens_out, cost_usd
        ) values (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            time.time(),
            task_id,
            requested_model,
            provider,
            model,
            fallback_reason,
            latency_ms,
            status,
            1 if refusal else 0,
            tokens_in,
            tokens_out,
            round(cost_usd, 8),
        ),
    )
    c.commit()
    c.close()


# ── OpenAI-compatible endpoints ─────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    started = time.perf_counter()
    task_id = request.headers.get("x-task-id", "")
    payload = await request.json()
    requested_model = str(payload.get("model", ""))
    text = text_from_messages(payload)

    if hard_stop(text):
        content = "I can’t help create content involving minors/CSAM or bodily harm."
        data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "_bifrost_provider": "policy",
            "_bifrost_model": "none",
            "_bifrost_fallback_reason": "hard_stop",
        }
        log_call(
            task_id,
            requested_model,
            "policy",
            "none",
            "hard_stop",
            int((time.perf_counter() - started) * 1000),
            "refused",
            False,
        )
        return JSONResponse(data)

    if needs_authorization(text):
        content = "What is the authorized scope, target owner, and lab/engagement boundary for this dual-use task?"
        data = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "_bifrost_provider": "policy",
            "_bifrost_model": "none",
            "_bifrost_fallback_reason": "scope_required",
        }
        log_call(
            task_id,
            requested_model,
            "policy",
            "none",
            "scope_required",
            int((time.perf_counter() - started) * 1000),
            "scope_required",
            False,
        )
        return JSONResponse(data)

    stream = bool(payload.get("stream", False))
    preferred = payload.get("provider") or request.headers.get("x-preferred-provider")
    fallback_reason = "none"
    refusal_intercepted = False

    try:
        if stream:
            # Streaming: use ProviderRouter's stream wrapper
            # We must collect the first chunk to detect soft refusal, then continue SSE
            async def _stream():
                collected = ""
                async for chunk in router.stream_chat_completion(
                    model=requested_model,
                    messages=payload.get("messages", []),
                    temperature=payload.get("temperature", 0.7),
                    max_tokens=payload.get("max_tokens", 1024),
                    preferred_provider=preferred,
                ):
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    collected += delta
                    chunk.setdefault("_bifrost_provider", chunk.get("provider", "external"))
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
                # Log after stream finishes
                if soft_refusal(collected):
                    log_call(
                        task_id,
                        requested_model,
                        "external",
                        requested_model,
                        "stream_soft_refusal",
                        int((time.perf_counter() - started) * 1000),
                        "refused",
                        True,
                    )
                else:
                    log_call(
                        task_id,
                        requested_model,
                        "external",
                        requested_model,
                        "none",
                        int((time.perf_counter() - started) * 1000),
                        "completed",
                        False,
                    )

            return StreamingResponse(_stream(), media_type="text/event-stream")

        # Non-streaming
        result = await router.chat_completion(
            model=requested_model,
            messages=payload.get("messages", []),
            temperature=payload.get("temperature", 0.7),
            max_tokens=payload.get("max_tokens", 1024),
            preferred_provider=preferred,
        )
        content = result["content"]
        if soft_refusal(content):
            refusal_intercepted = True
            fallback_reason = "soft_refusal"
        log_call(
            task_id,
            requested_model,
            result["provider"],
            result["model"],
            fallback_reason,
            int(result["latency_ms"]),
            "completed",
            refusal_intercepted,
            result["tokens_in"],
            result["tokens_out"],
            result["cost_usd"],
        )
        # Build OpenAI-compatible response
        data = {
            "id": f"chatcmpl-bifrost-{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": result["tokens_in"],
                "completion_tokens": result["tokens_out"],
                "total_tokens": result["tokens_in"] + result["tokens_out"],
            },
            "_bifrost_provider": result["provider"],
            "_bifrost_model": result["model"],
            "_bifrost_fallback_reason": fallback_reason,
            "_bifrost_latency_ms": result["latency_ms"],
            "_bifrost_cost_usd": result["cost_usd"],
        }
        return JSONResponse(data)

    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.error("bifrost_proxy.error", error=str(exc), latency_ms=latency_ms)
        log_call(task_id, requested_model, "error", "", str(exc), latency_ms, "error", False)
        return JSONResponse(
            {
                "error": {
                    "message": str(exc),
                    "type": "internal_error",
                }
            },
            status_code=503,
        )


@app.get("/v1/models")
async def list_models():
    available = router.get_available_providers()
    models: list[dict[str, Any]] = []
    for provider in available:
        models.extend(PROVIDER_MODELS.get(provider, []))
    return {"object": "list", "data": models}


# ── Health, metrics, providers, benchmark, runs ─────────────────────

@app.get("/health")
async def health():
    available = router.get_available_providers()
    health_checks = await router.health_check_all()
    latency_stats = {p: router.latency.get_stats(p) for p in PROVIDERS}
    overall = "ok" if available else "degraded"
    return {
        "status": overall,
        "available_providers": available,
        "health_checks": health_checks,
        "latency_stats": latency_stats,
        "monthly_cap_usd": MONTHLY_CAP,
        "fallback_chain": router.fallback_chain,
        "free_mode": router.free_mode,
    }


@app.get("/metrics")
async def metrics():
    c = conn()
    row = c.execute(
        "select count(*), coalesce(avg(latency_ms),0), coalesce(sum(refusal_intercepted),0), coalesce(sum(cost_usd),0.0) from calls"
    ).fetchone()
    c.close()
    total, avg_latency, refusals, total_cost = row
    latency_lines = ""
    for p in PROVIDERS:
        stats = router.latency.get_stats(p)
        latency_lines += (
            f'sovereign_bifrost_latency_ms_p50{{provider="{p}"}} {stats["p50_ms"]:.2f}\n'
            f'sovereign_bifrost_latency_ms_p95{{provider="{p}"}} {stats["p95_ms"]:.2f}\n'
            f'sovereign_bifrost_error_rate{{provider="{p}"}} {stats["error_rate"]:.4f}\n'
        )
    return PlainTextResponse(
        f"sovereign_bifrost_calls_total {total}\n"
        f"sovereign_bifrost_latency_ms_avg {avg_latency:.2f}\n"
        f"sovereign_bifrost_refusal_intercepts_total {refusals}\n"
        f"sovereign_bifrost_monthly_cap_usd {MONTHLY_CAP}\n"
        f"sovereign_bifrost_total_cost_usd {total_cost:.8f}\n"
        f"{latency_lines}"
    )


@app.get("/providers")
async def providers():
    health_checks = await router.health_check_all()
    out = []
    for name, cfg in PROVIDERS.items():
        out.append(
            {
                "name": name,
                "base_url": cfg["base_url"],
                "default_model": cfg["default_model"],
                "priority": cfg["priority"],
                "supports_streaming": cfg["supports_streaming"],
                "configured": _has_api_key(name),
                "health": health_checks.get(name, {}),
            }
        )
    return {"providers": out}


@app.get("/benchmark")
async def benchmark():
    available = router.get_available_providers()
    results: dict[str, dict[str, Any]] = {}
    prompt = "Count from 1 to 5"

    async def _bench(provider: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            result = await router.chat_completion(
                model=PROVIDERS[provider]["default_model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=32,
                preferred_provider=provider,
            )
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "ok",
                "latency_ms": round(latency, 2),
                "provider_latency_ms": result["latency_ms"],
                "tokens_out": result["tokens_out"],
                "cost_usd": result["cost_usd"],
            }
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            return {"status": "error", "error": str(exc), "latency_ms": round(latency, 2)}

    tasks = [_bench(p) for p in available]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    for p, r in zip(available, raw):
        if isinstance(r, Exception):
            results[p] = {"status": "error", "error": str(r)}
        else:
            results[p] = r
    return {"benchmark": results}


@app.get("/runs")
async def runs(limit: int = 50):
    c = conn()
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "select * from calls order by ts desc limit ?", (min(limit, 200),)
    ).fetchall()
    c.close()
    return {"runs": [dict(row) for row in rows]}


# ── Graceful shutdown ──────────────────────────────────────────────

@app.on_event("shutdown")
async def _shutdown():
    await router.close()
