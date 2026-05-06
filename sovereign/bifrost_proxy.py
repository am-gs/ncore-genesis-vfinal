import json
import os
import sqlite3
import time
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

OLLAMA = os.environ.get("SOVEREIGN_OLLAMA_URL", "http://127.0.0.1:11434")
DB = os.environ.get("SOVEREIGN_BUDGET_DB", "/home/ubuntu/sovereign/bifrost/budget.sqlite3")
MONTHLY_CAP = float(os.environ.get("SOVEREIGN_MONTHLY_CAP", "38.0"))
REMOTE_BASE_URL = os.environ.get("SOVEREIGN_REMOTE_BASE_URL", "").rstrip("/")
REMOTE_API_KEY = os.environ.get("SOVEREIGN_REMOTE_API_KEY", "")
REMOTE_MODEL = os.environ.get("SOVEREIGN_REMOTE_MODEL", "")

LOCAL_CHAIN = ["qwen3-8b:latest", "dolphin-mistral-7b:latest"]
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

app = FastAPI(title="Sovereign Bifrost Shim")


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
          refusal_intercepted integer
        )
        """
    )
    required_columns = {
        "ts": "real",
        "task_id": "text",
        "requested_model": "text",
        "provider": "text",
        "model": "text",
        "fallback_reason": "text",
        "latency_ms": "integer",
        "completion_status": "text",
        "refusal_intercepted": "integer",
    }
    existing_columns = {row[1] for row in c.execute("pragma table_info(calls)").fetchall()}
    for name, column_type in required_columns.items():
        if name not in existing_columns:
            c.execute(f"alter table calls add column {name} {column_type}")
    c.commit()
    return c


def text_from_messages(payload: dict[str, Any]) -> str:
    parts = []
    for message in payload.get("messages", []) or []:
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(p.get("text", p)) if isinstance(p, dict) else str(p) for p in content)
            parts.append(str(content))
    return "\n".join(parts)


def contains_any(text: str, patterns: list[str]) -> bool:
    lower = text.lower()
    return any(pattern in lower for pattern in patterns)


def hard_stop(text: str) -> bool:
    return contains_any(text, HARD_STOP_PATTERNS)


def needs_authorization(text: str) -> bool:
    lower = text.lower()
    if any(ok in lower for ok in ["authorized", "owned", "lab", "ctf", "sandbox", "tabletop", "simulation", "defensive"]):
        return False
    return contains_any(text, DUAL_USE_AUTH_PATTERNS)


def soft_refusal(text: str) -> bool:
    return contains_any(text, SOFT_REFUSAL_PATTERNS)


def exact_or_structured_request(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in ["reply exactly", "return exactly", "valid json", "json schema", "only the number"])


def clean_exact_text(text: str) -> str:
    return text.strip().strip("`").strip()


def local_model_for(requested: str | None, fallback_index: int = 0) -> str:
    if requested in ("dolphin-mistral-7b", "dolphin-mistral-7b:latest"):
        return "dolphin-mistral-7b:latest"
    if requested in ("qwen3-8b", "qwen3-8b:latest", "claude-haiku-4-5", "gpt-4o-mini", None, ""):
        return LOCAL_CHAIN[min(fallback_index, len(LOCAL_CHAIN) - 1)]
    return requested or LOCAL_CHAIN[min(fallback_index, len(LOCAL_CHAIN) - 1)]


async def call_openai(base_url: str, payload: dict[str, Any], api_key: str = "sovereign", timeout: float = 180) -> tuple[int, dict[str, Any] | bytes]:
    headers = {"content-type": "application/json", "authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base_url.rstrip('/')}/v1/chat/completions", json=payload, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.content


def choice_text(data: dict[str, Any] | bytes) -> str:
    if not isinstance(data, dict):
        return ""
    return str((data.get("choices") or [{}])[0].get("message", {}).get("content", ""))


def with_provider(data: dict[str, Any] | bytes, provider: str, model: str, fallback_reason: str) -> dict[str, Any] | bytes:
    if isinstance(data, dict):
        data["_bifrost_provider"] = provider
        data["_bifrost_model"] = model
        data["_bifrost_fallback_reason"] = fallback_reason
    return data


def log_call(task_id: str, requested_model: str, provider: str, model: str, fallback_reason: str, latency_ms: int, status: str, refusal: bool) -> None:
    c = conn()
    c.execute(
        """
        insert into calls (
          ts, task_id, requested_model, provider, model, fallback_reason,
          latency_ms, completion_status, refusal_intercepted
        ) values (?,?,?,?,?,?,?,?,?)
        """,
        (time.time(), task_id, requested_model, provider, model, fallback_reason, latency_ms, status, 1 if refusal else 0),
    )
    c.commit()
    c.close()


@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{OLLAMA}/v1/models")
        if r.status_code >= 400:
            raise RuntimeError(f"ollama returned {r.status_code}")
    except Exception as e:
        return JSONResponse({"status": "degraded", "ollama": "down", "error": str(e)}, status_code=503)
    return {"status": "ok", "ollama": "ok", "monthly_cap_usd": MONTHLY_CAP, "local_chain": LOCAL_CHAIN, "remote_configured": bool(REMOTE_BASE_URL and REMOTE_API_KEY)}


@app.get("/metrics")
async def metrics():
    c = conn()
    rows = c.execute("select count(*), coalesce(avg(latency_ms),0), coalesce(sum(refusal_intercepted),0) from calls").fetchone()
    c.close()
    total, avg_latency, refusals = rows
    return PlainTextResponse(
        f"sovereign_bifrost_calls_total {total}\n"
        f"sovereign_bifrost_latency_ms_avg {avg_latency}\n"
        f"sovereign_bifrost_refusal_intercepts_total {refusals}\n"
        f"sovereign_bifrost_monthly_cap_usd {MONTHLY_CAP}\n"
    )


@app.get("/runs")
async def runs(limit: int = 50):
    c = conn()
    c.row_factory = sqlite3.Row
    rows = c.execute("select * from calls order by ts desc limit ?", (min(limit, 200),)).fetchall()
    c.close()
    return {"runs": [dict(row) for row in rows]}


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def openai_proxy(path: str, request: Request):
    if path != "chat/completions":
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.request(request.method, f"{OLLAMA}/v1/{path}", content=await request.body(), headers={"content-type": request.headers.get("content-type", "application/json")})
        return Response(r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    started = time.perf_counter()
    task_id = request.headers.get("x-task-id", "")
    payload = await request.json()
    requested_model = str(payload.get("model", ""))
    text = text_from_messages(payload)

    if hard_stop(text):
        content = "I can’t help create content involving minors/CSAM or bodily harm."
        data = {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop", "index": 0}], "_bifrost_provider": "policy", "_bifrost_model": "none", "_bifrost_fallback_reason": "hard_stop"}
        log_call(task_id, requested_model, "policy", "none", "hard_stop", int((time.perf_counter() - started) * 1000), "refused", False)
        return JSONResponse(data)

    if needs_authorization(text):
        content = "What is the authorized scope, target owner, and lab/engagement boundary for this dual-use task?"
        data = {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop", "index": 0}], "_bifrost_provider": "policy", "_bifrost_model": "none", "_bifrost_fallback_reason": "scope_required"}
        log_call(task_id, requested_model, "policy", "none", "scope_required", int((time.perf_counter() - started) * 1000), "scope_required", False)
        return JSONResponse(data)

    fallback_reason = "none"
    refusal_intercepted = False

    if REMOTE_BASE_URL and REMOTE_API_KEY and requested_model not in ("qwen3-8b", "qwen3-8b:latest", "dolphin-mistral-7b", "dolphin-mistral-7b:latest"):
        remote_payload = dict(payload)
        if REMOTE_MODEL:
            remote_payload["model"] = REMOTE_MODEL
        status, data = await call_openai(REMOTE_BASE_URL, remote_payload, REMOTE_API_KEY, timeout=60)
        content = choice_text(data)
        structured_bad = exact_or_structured_request(text) and not content.strip()
        if status < 400 and not soft_refusal(content) and not structured_bad:
            model = str(remote_payload.get("model", requested_model))
            log_call(task_id, requested_model, "remote", model, "none", int((time.perf_counter() - started) * 1000), "completed", False)
            return JSONResponse(with_provider(data, "remote", model, "none"), status_code=status)
        fallback_reason = "remote_soft_refusal_or_failure"
        refusal_intercepted = soft_refusal(content)

    last_data: dict[str, Any] | bytes = {}
    last_status = 500
    for i, model in enumerate([local_model_for(requested_model, 0), local_model_for("dolphin-mistral-7b", 1)]):
        local_payload = dict(payload)
        local_payload["model"] = model
        if exact_or_structured_request(text):
            local_payload["max_tokens"] = min(int(local_payload.get("max_tokens", 96) or 96), 128)
        else:
            local_payload["max_tokens"] = int(local_payload.get("max_tokens", 900) or 900)
        status, data = await call_openai(OLLAMA, local_payload, "sovereign", timeout=180)
        content = choice_text(data)
        last_status, last_data = status, data
        if status < 400 and content.strip() and not soft_refusal(content):
            reason = fallback_reason if fallback_reason != "none" else ("local_default" if i == 0 else "local_secondary")
            log_call(task_id, requested_model, "sovereign-local", model, reason, int((time.perf_counter() - started) * 1000), "completed", refusal_intercepted)
            return JSONResponse(with_provider(data, "sovereign-local", model, reason), status_code=status)
        fallback_reason = "local_structured_or_refusal_failure"
        refusal_intercepted = refusal_intercepted or soft_refusal(content)

    log_call(task_id, requested_model, "sovereign-local", "fallback-chain", fallback_reason, int((time.perf_counter() - started) * 1000), "failed", refusal_intercepted)
    if isinstance(last_data, dict):
        return JSONResponse(with_provider(last_data, "sovereign-local", "fallback-chain", fallback_reason), status_code=last_status)
    return Response(last_data, status_code=last_status)
