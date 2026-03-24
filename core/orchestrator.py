"""
NCore Genesis vFinal - Orchestrator (Singularity Layer)

Changes in this revision:
  - set_cache() called after successful ainvoke() so Redis UDS cache warms.
  - All prior Singularity fixes retained (uvloop, orjson, loopback bind,
    _summarise never re-raises, circuit-breaker gauge .set() semantics).
"""
import os
import uvloop
import httpx
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
MAX_MESSAGES        = int(os.getenv("NCORE_MAX_MESSAGES",   "20"))
SUMMARISE_KEEP      = int(os.getenv("NCORE_SUMMARISE_KEEP", "5"))
SUMMARISER_ENDPOINT = os.getenv("NCORE_SUMMARISER_ENDPOINT", "http://127.0.0.1:11434/api/chat")
SUMMARISER_MODEL    = os.getenv("NCORE_SUMMARISER_MODEL",    "gemma2:2b")

http_client: Optional[httpx.AsyncClient] = None

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages:       List[str]
    task:           str
    model_name:     str
    model_endpoint: str
    role:           str
    memory_anchor:  Optional[str]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
registry = NCoreModelRegistry()
router   = AthenaMoERouter(registry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _needs_summarisation(state: AgentState) -> bool:
    return len(state["messages"]) > MAX_MESSAGES


async def _summarise(messages: List[str]) -> str:
    """
    Always returns a string; never re-raises so summarise_node
    except clause is always reachable and the graph never crashes.
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
                "model":    SUMMARISER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream":   False,
            },
        )
        r.raise_for_status()
        CIRCUIT_BREAKER_STATE.labels("summariser").set(0)
        return r.json()["message"]["content"].strip()
    except Exception as exc:
        CIRCUIT_BREAKER_STATE.labels("summariser").set(1)
        increment_metric_safe(SUMMARISATION_ERRORS)
        return "[summary unavailable: {}] ".format(exc) + " | ".join(messages[-3:])


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------
async def route_node(state: AgentState) -> AgentState:
    cfg: ModelConfig = await router.route(state["task"])
    increment_metric_safe(TASKS_TOTAL, cfg.name, cfg.role)
    state["model_name"]     = cfg.name
    state["model_endpoint"] = cfg.endpoint
    state["role"]           = cfg.role
    state["messages"].append(
        f"Routed to {cfg.name} ({cfg.role}) at {cfg.endpoint}"
    )
    return state


async def summarise_node(state: AgentState) -> AgentState:
    increment_metric_safe(SUMMARISATION_TOTAL)
    older  = state["messages"][:-SUMMARISE_KEEP]
    recent = state["messages"][-SUMMARISE_KEEP:]
    anchor = await _summarise(older)
    state["memory_anchor"] = anchor
    state["messages"]      = [f"[MEMORY ANCHOR] {anchor}"] + recent
    return state


def should_summarise(state: AgentState) -> str:
    return "summarise" if _needs_summarisation(state) else END


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
graph = StateGraph(AgentState)
graph.add_node("route",     route_node)
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
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NCore MoE Orchestrator Singularity",
    default_response_class=ORJSONResponse,
)
app.mount("/metrics", make_asgi_app())


@app.on_event("startup")
async def startup_event() -> None:
    global http_client
    mark_event_loop_thread()
    limits = httpx.Limits(max_keepalive_connections=500, max_connections=1000)
    http_client = httpx.AsyncClient(limits=limits, timeout=10.0)
    for ep in ["summariser", "dolphin-vllm", "darkchamp-vllm", "gptoss-vllm"]:
        CIRCUIT_BREAKER_STATE.labels(ep).set(0)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await http_client.aclose()


@app.post("/run")
async def run_task(payload: dict) -> AgentState:
    ACTIVE_REQUESTS.inc()
    try:
        task = payload.get("task", "")

        cached = await router.check_cache(task)
        if cached:
            return ORJSONResponse({
                "messages":       [cached],
                "task":           task,
                "model_name":     "redis-cache",
                "model_endpoint": "unix-socket",
                "role":           "cache",
                "memory_anchor":  None,
            })

        result: AgentState = await agent.ainvoke({
            "messages":      payload.get("messages", []),
            "task":          task,
            "model_name":    "",
            "model_endpoint": "",
            "role":          "",
            "memory_anchor": payload.get("memory_anchor", None),
        })

        # Write routing decision into Redis UDS cache for future fast-path
        await router.set_cache(task, result["model_name"])

        return result
    finally:
        ACTIVE_REQUESTS.dec()


@app.get("/health")
async def health() -> dict:
    return {"status": "apex_operational"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator:app", host="127.0.0.1", port=8080, reload=False)
