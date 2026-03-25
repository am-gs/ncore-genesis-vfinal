"""NCore Genesis — FastAPI + LangGraph Orchestrator v3.0

Endpoints:
  POST /run          → route + execute a task
  GET  /health       → liveness check
  GET  /metrics      → Prometheus metrics

Router decision flows:
  → POD tasks (image/video) go to DynamicPodProvisioner
  → LLM tasks go to OpenRouter (Nemotron Nano/Super, Opus, Qwen Coder, Dolphin)
"""
from __future__ import annotations
import os, json, time, logging
from typing import Annotated, TypedDict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import httpx

from router import NCoreMasterRouter
from pod_provisioner import DynamicPodProvisioner
from metrics import (
    REQUEST_COUNTER, REQUEST_LATENCY, ROUTE_TIER_COUNTER,
    COST_COUNTER, update_cost
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ncore")

app = FastAPI(title="NCore Genesis", version="3.0")
ROUTER     = NCoreMasterRouter()
PROVISIONER = DynamicPodProvisioner()

# ── State ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    task:      str
    turns:     int
    route:     dict
    output:    str
    cost_usd:  float
    latency_s: float

# ── LangGraph nodes ──────────────────────────────────────────────────────────

def node_route(state: AgentState) -> AgentState:
    decision = ROUTER.route(state["task"], state.get("turns", 0))
    log.info(f"[ROUTE] tier={decision['tier']} model={decision['model']} "
             f"engine={decision['engine']} reason={decision['reason']}")
    ROUTE_TIER_COUNTER.labels(tier=decision["tier"]).inc()
    return {**state, "route": decision}


def node_execute(state: AgentState) -> AgentState:
    d = state["route"]
    t0 = time.time()

    # ── POD tasks ─────────────────────────────────────────────────────────
    if d.get("requires_pod"):
        spec   = d["pod_spec"]
        result = PROVISIONER.run(spec["type"], state["task"])
        latency = time.time() - t0
        if result.success:
            url    = result.output.get("video_url") or result.output.get("image_url", "")
            output = f"✅ {spec['type'].title()} ready in {result.runtime_seconds:.0f}s\n🔗 {url}"
        else:
            output = f"❌ {spec['type'].title()} failed: {result.error}"
        update_cost(d["tier"], result.cost_usd)
        return {**state, "output": output, "cost_usd": result.cost_usd, "latency_s": latency}

    # ── LLM tasks ─────────────────────────────────────────────────────────
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
        "model": d["model"],
        "messages": [{"role": "user", "content": state["task"]}],
        "temperature": 0.1 if d["tier"] in ("nano", "coder") else 0.4,
        "max_tokens": 8192,
    }
    try:
        r = httpx.post(
            f"{d['endpoint']}/chat/completions",
            headers=headers, json=payload, timeout=120
        )
        r.raise_for_status()
        output = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        output = f"[LLM error] {e}"

    latency  = time.time() - t0
    cost     = d["estimated_cost_usd"]
    update_cost(d["tier"], cost)
    return {**state, "output": output, "cost_usd": cost, "latency_s": latency}


# ── Graph ────────────────────────────────────────────────────────────────────

graph  = StateGraph(AgentState)
graph.add_node("route",   node_route)
graph.add_node("execute", node_execute)
graph.set_entry_point("route")
graph.add_edge("route", "execute")
graph.add_edge("execute", END)
app_graph = graph.compile()

# ── API ──────────────────────────────────────────────────────────────────────

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
        final = app_graph.invoke(init)
    return {
        "output":    final["output"],
        "route":     final["route"],
        "cost_usd":  final["cost_usd"],
        "latency_s": final["latency_s"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0"}


from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator:app", host="0.0.0.0", port=8080, reload=False)
