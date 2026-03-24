"""
NCore Genesis vFinal — Orchestrator (Singularity Layer)

Upgrades applied:
  - uvloop.install() at interpreter level (Cython event loop)
  - ORJSONResponse as default (Rust-based JSON serialization)
  - httpx connection pool initialised in ASGI lifespan
  - Prometheus metrics app mounted at /metrics
  - mark_event_loop_thread() called at startup

Bugs fixed vs. submitted code:
  1. _summarise() re-raised exceptions, making the except clause in
     summarise_node unreachable. Now always returns a string.
  2. CIRCUIT_BREAKER_STATE.inc() semantics wrong for a 0/1 gauge;
     replaced with .set(0) on success and .set(1) on error.
"""
import os
import uvloop
import httpx
import time
from typing import TypedDict, List, Optional

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from langgraph.graph import StateGraph, END
from prometheus_client import make_asgi_app

from moe_router import NCoreModelRegistry, AthenaMoERouter, ModelConfig
from metrics import (
    mark_event_loop_thread,
    increment_metric_safe,
    TASKS_TOTAL,
    SUMMARISATION_TOTAL,
    SUMMARISATION_ERRORS,
    ACTIVE_REQUESTS,
    CIRCUIT_BREAKER_STATE,
)

# Enforce Cython uvloop at interpreter level
uvloop.install()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_MESSAGES = int(os.getenv("NCORE_MAX_MESSAGES", "20"))
SUMMARISE_KEEP = int(os.getenv("NCORE_SUMMARISE_KEEP", "5"))
SUMMARISER_ENDPOINT = os.getenv(
    "NCORE_SUMMARISER_ENDPOINT", "http://127.0.0.1:11434/api/chat"
)
SUMMARISER_MODEL = os.getenv("NCORE_SUMMARISER_MODEL", "gemma2:2b")

# ---------------------------------------------------------------------------
# Shared async HTTP client (initialised in lifespan)
# ---------------------------------------------------------------------------
http_client: Optional[httpx.AsyncClient] = None

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: List[str]
    task: str
    model_name: str
    model_endpoint: str
    role: str
    memory_anchor: Optional[str]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
registry = NCoreModelRegistry()
router = AthenaMoERouter(registry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _needs_summarisation(state: AgentState) -> bool:
    return len(state["messages"]) > MAX_MESSAGES


async def _summarise(messages: List[str]) -> str:
    """
    Call a local cheap model to compress history.
    Bug fix: always returns a string; never re-raises so summarise_node
    except clause is reachable and the graph never crashes on LLM failure.
    """
    prompt = (
        "Summarise this agent trace into ONE short paragraph "
        "capturing all tactical routing decisions:\n\n"
        + "\n".join(messages)
    )
    try:
        r = await http_client.post(
            SUMMARISER_ENDPOINT,
            json={
                "model": SUMMARISER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        r.raise_for_status()
        # Mark summariser circuit as healthy
        CIRCUIT_BREAKER_STATE.labels("summariser").set(0)
        return r.json()["message"]["content"].strip()
    except Exception as exc:
        # Mark summariser circuit as open (unhealthy)
        CIRCUIT_BREAKER_STATE.labels("summariser").set(1)
        increment_metric_safe(SUMMARISATION_ERRORS)
        return "[summary unavailable: {}] ".format(exc) + " | ".join(messages[-3:])


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------
async def route_node(state: AgentState) -> AgentState:
    cfg: ModelConfig = await router.route(state["task"])
    increment_metric_safe(TASKS_TOTAL, cfg.name, cfg.role)
    state["model_name"] = cfg.name
    state["model_endpoint"] = cfg.endpoint
    state["role"] = cfg.role
    state["messages"].append(
        f"Routed to {cfg.name} ({cfg.role}) at {cfg.endpoint}"
    )
    return state


async def summarise_node(state: AgentState) -> AgentState:
    increment_metric_safe(SUMMARISATION_TOTAL)
    older = state["messages"][:-SUMMARISE_KEEP]
    recent = state["messages"][-SUMMARISE_KEEP:]
    anchor = await _summarise(older)   # always returns str (never raises)
    state["memory_anchor"] = anchor
    state["messages"] = [f"[MEMORY ANCHOR] {anchor}"] + recent
    return state


def should_summarise(state: AgentState) -> str:
    return "summarise" if _needs_summarisation(state) else END


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
graph = StateGraph(AgentState)
graph.add_node("route", route_node)
graph.add_node("summarise", summarise_node)
graph.set_entry_point("route")
graph.add_conditional_edges(
    "route",
    should_summarise,
    {"summarise": "summarise", END: END},
)
graph.add_edge("summarise", END)
agent = graph.compile()

# ---------------------------------------------------------------------------
# FastAPI app — Rust-based JSON serialization via orjson
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NCore MoE Orchestrator Singularity",
    default_response_class=ORJSONResponse,
)

# Mount Prometheus scrape endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.on_event("startup")
async def startup_event() -> None:
    global http_client
    # Record this thread as the event-loop thread for safe metric injection
    mark_event_loop_thread()
    limits = httpx.Limits(
        max_keepalive_connections=500, max_connections=1000
    )
    http_client = httpx.AsyncClient(limits=limits, timeout=10.0)
    # Initialise all circuit breaker gauges to healthy
    for endpoint in ["summariser", "dolphin-vllm", "darkchamp-vllm", "gptoss-vllm"]:
        CIRCUIT_BREAKER_STATE.labels(endpoint).set(0)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await http_client.aclose()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/run")
async def run_task(payload: dict) -> AgentState:
    ACTIVE_REQUESTS.inc()
    try:
        task = payload.get("task", "")

        # Fast path: return cached routing decision if available
        cached = await router.check_cache(task)
        if cached:
            return ORJSONResponse({
                "messages": [cached],
                "task": task,
                "model_name": "redis-cache",
                "model_endpoint": "unix-socket",
                "role": "cache",
                "memory_anchor": None,
            })

        result: AgentState = await agent.ainvoke({
            "messages": payload.get("messages", []),
            "task": task,
            "model_name": "",
            "model_endpoint": "",
            "role": "",
            "memory_anchor": payload.get("memory_anchor", None),
        })
        return result
    finally:
        ACTIVE_REQUESTS.dec()


@app.get("/health")
async def health() -> dict:
    return {"status": "apex_operational"}


if __name__ == "__main__":
    import uvicorn
    # Loopback only; Tailscale handles remote access
    uvicorn.run("orchestrator:app", host="127.0.0.1", port=8080, reload=False)
