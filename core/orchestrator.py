"""NCore Genesis — FastAPI + LangGraph Orchestrator v3.2

Fixes (v3.2 — March 31 2026):
  - MoE router init crash: AthenaMoERouter now constructed with its registry
  - MoE route() is async: node_route converted to async, graph uses .ainvoke()
  - MoE route returns ModelConfig dataclass: access .name/.endpoint/.role not dict keys
  - LangGraph async: graph compiled and invoked properly via ainvoke()
  - Removed asyncio.to_thread(app_graph.invoke) anti-pattern

Prior fixes retained (v3.1):
  C1 — Persistent httpx.AsyncClient with connection pooling
  C2 — Pod provisioner fully async (asyncio.create_subprocess_exec)
  M1 — tenacity retry with exponential backoff on LLM calls
  M2 — structlog JSON logging
  H1 — AthenaMoERouter wired for Vast self-hosted tier model selection
"""
from __future__ import annotations
import asyncio, os, time
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import httpx
import structlog
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from router import NCoreMasterRouter
from moe_router import AthenaMoERouter, NCoreModelRegistry  # H1: wired in
from pod_provisioner import DynamicPodProvisioner
from metrics import (
    REQUEST_COUNTER, REQUEST_LATENCY, ROUTE_TIER_COUNTER,
    ROUTING_LATENCY, CACHE_HITS, CACHE_MISSES,
    update_cost, increment_metric_safe
)

# ── structlog JSON logging (M2) ───────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# ── ASGI lifespan: persistent HTTP client (C1) ───────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        timeout=httpx.Timeout(120.0, connect=10.0),
    )
    # H1: connect MoE router cache
    await MOE_ROUTER.connect_cache()
    log.info("ncore.startup", msg="HTTP client + MoE cache ready")
    yield
    await app.state.http.aclose()
    await MOE_ROUTER.disconnect_cache()
    log.info("ncore.shutdown")

app = FastAPI(title="NCore Genesis", version="3.2", lifespan=lifespan)

MASTER_ROUTER = NCoreMasterRouter()
MOE_ROUTER    = AthenaMoERouter(NCoreModelRegistry())  # H1: must pass registry
PROVISIONER   = DynamicPodProvisioner()

# ── State ─────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    task:      str
    turns:     int
    route:     dict
    output:    str
    cost_usd:  float
    latency_s: float

# ── tenacity-wrapped LLM call (C1 + M1) ──────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    before_sleep=before_sleep_log(structlog.stdlib.get_logger(), 30),
)
async def _call_llm(client: httpx.AsyncClient, endpoint: str, headers: dict, payload: dict) -> str:
    r = await client.post(f"{endpoint}/chat/completions", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ── LangGraph nodes (both async for ainvoke compatibility) ────────────────────
async def node_route(state: AgentState) -> AgentState:
    with ROUTING_LATENCY.time():
        decision = MASTER_ROUTER.route(state["task"], state.get("turns", 0))

    # H1: for Vast self-hosted tier, defer model selection to MoE router
    if decision["provider"] == "vast-serverless":
        moe_result = await MOE_ROUTER.route(state["task"])  # async — returns ModelConfig
        decision["model"]    = moe_result.name       # ModelConfig.name
        decision["endpoint"] = moe_result.endpoint   # ModelConfig.endpoint
        decision["engine"]   = moe_result.role        # ModelConfig.role
        increment_metric_safe(CACHE_HITS)
    else:
        increment_metric_safe(CACHE_MISSES)

    log.info("ncore.route",
             tier=decision["tier"], model=decision["model"],
             engine=decision.get("engine"), reason=decision["reason"])
    ROUTE_TIER_COUNTER.labels(tier=decision["tier"]).inc()
    return {**state, "route": decision}


async def node_execute(state: AgentState) -> AgentState:   # C2: now truly async
    d  = state["route"]
    t0 = time.time()

    # ── POD tasks ─────────────────────────────────────────────────────────────
    if d.get("requires_pod"):
        spec = d["pod_spec"]
        # C2: provisioner is now fully async (H4 fix)
        result = await PROVISIONER.run(spec["type"], state["task"])
        latency = time.time() - t0
        if result.success:
            url    = result.output.get("video_url") or result.output.get("image_url", "")
            output = f"✅ {spec['type'].title()} ready in {result.runtime_seconds:.0f}s\n🔗 {url}"
        else:
            output = f"❌ {spec['type'].title()} failed: {result.error}"
        update_cost(d["tier"], result.cost_usd)
        return {**state, "output": output, "cost_usd": result.cost_usd, "latency_s": latency}

    # ── LLM tasks ─────────────────────────────────────────────────────────────
    api_key = (
        os.environ.get("OPENROUTER_API_KEY", "")
        if d["provider"] == "openrouter"
        else os.environ.get("VAST_API_KEY", "")
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer":  "https://ncore.internal",
        "X-Title":       "NCore Genesis",
    }
    payload = {
        "model":       d["model"],
        "messages":    [{"role": "user", "content": state["task"]}],
        "temperature": 0.1 if d["tier"] in ("nano", "coder") else 0.4,
        "max_tokens":  8192,
    }
    try:
        # C1: reuse persistent client; M1: tenacity retry on timeout/5xx
        output = await _call_llm(app.state.http, d["endpoint"], headers, payload)
    except Exception as e:
        log.error("ncore.llm_error", error=str(e), model=d["model"])
        output = f"[LLM error after retries] {e}"

    latency = time.time() - t0
    cost    = d["estimated_cost_usd"]
    update_cost(d["tier"], cost)
    log.info("ncore.execute", tier=d["tier"], latency_s=round(latency, 3), cost_usd=cost)
    return {**state, "output": output, "cost_usd": cost, "latency_s": latency}


# ── Graph (async nodes → use ainvoke) ─────────────────────────────────────────
_builder = StateGraph(AgentState)
_builder.add_node("route",   node_route)    # async
_builder.add_node("execute", node_execute)  # async
_builder.set_entry_point("route")
_builder.add_edge("route", "execute")
_builder.add_edge("execute", END)
app_graph = _builder.compile()

# ── API ───────────────────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    task:  str
    turns: int = 0

@app.post("/run")
async def run(req: RunRequest):
    with REQUEST_LATENCY.time():
        REQUEST_COUNTER.inc()
        init: AgentState = {
            "task":      req.task,
            "turns":     req.turns,
            "route":     {},
            "output":    "",
            "cost_usd":  0.0,
            "latency_s": 0.0,
        }
        # Async graph: ainvoke runs async nodes natively, no thread pool needed
        final = await app_graph.ainvoke(init)
    return {
        "output":    final["output"],
        "route":     final["route"],
        "cost_usd":  final["cost_usd"],
        "latency_s": final["latency_s"],
    }

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.2"}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator:app", host="0.0.0.0", port=8080, reload=False)
