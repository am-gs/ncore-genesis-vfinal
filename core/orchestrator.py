"""
NCore Genesis vFinal — Orchestrator
Audit fixes applied:
  - Fix #2: crypt_shredder.so NOT loaded by this process (jemalloc+force_nodelay only via systemd)
  - Fix #3: uvicorn bound to 127.0.0.1 only
  - Fix #4: sliding-window context cap + summarizer node to prevent OOM
"""
import os
from typing import TypedDict, List, Optional

import httpx
from fastapi import FastAPI
from langgraph.graph import StateGraph, END

from moe_router import NCoreModelRegistry, AthenaMoERouter, ModelConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_MESSAGES = 20       # sliding window cap before summarisation triggers
SUMMARISE_KEEP = 5      # messages to keep verbatim after summary anchor

# Tailscale loopback or local — set NCORE_SUMMARISER_ENDPOINT in .env to
# override with a real vLLM/Ollama URL, e.g. http://127.0.0.1:11434/api/chat
SUMMARISER_ENDPOINT = os.getenv(
    "NCORE_SUMMARISER_ENDPOINT", "http://127.0.0.1:11434/api/chat"
)
SUMMARISER_MODEL = os.getenv("NCORE_SUMMARISER_MODEL", "gemma2:2b")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict):
    messages: List[str]
    task: str
    model_name: str
    model_endpoint: str
    role: str
    memory_anchor: Optional[str]   # persists across summarisation cycles


# ---------------------------------------------------------------------------
# Registry + router
# ---------------------------------------------------------------------------
registry = NCoreModelRegistry()
router = AthenaMoERouter(registry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _needs_summarisation(state: AgentState) -> bool:
    return len(state["messages"]) > MAX_MESSAGES


async def _summarise(messages: List[str]) -> str:
    """Call a local cheap model to compress history into a single anchor."""
    prompt = (
        "You are a concise memory compressor. "
        "Summarise the following agent trace into ONE short paragraph "
        "preserving key decisions and routing choices:\n\n"
        + "\n".join(messages)
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                SUMMARISER_ENDPOINT,
                json={
                    "model": SUMMARISER_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["message"]["content"].strip()
    except Exception as exc:
        # Graceful degradation: fall back to hard truncation
        return f"[summary unavailable: {exc}] " + " | ".join(messages[-3:])


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------
def route_node(state: AgentState) -> AgentState:
    cfg: ModelConfig = router.route(state["task"])
    state["model_name"] = cfg.name
    state["model_endpoint"] = cfg.endpoint
    state["role"] = cfg.role
    state["messages"].append(
        f"Routed to {cfg.name} ({cfg.role}) at {cfg.endpoint}"
    )
    return state


async def summarise_node(state: AgentState) -> AgentState:
    """Compress old messages into a memory anchor; keep only recent tail."""
    older = state["messages"][:-SUMMARISE_KEEP]
    recent = state["messages"][-SUMMARISE_KEEP:]
    anchor = await _summarise(older)
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
graph.add_conditional_edges("route", should_summarise, {
    "summarise": "summarise",
    END: END,
})
graph.add_edge("summarise", END)

agent = graph.compile()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="NCore MoE Orchestrator")


@app.post("/run")
async def run_task(payload: dict) -> AgentState:
    task = payload.get("task", "")
    prior_messages: List[str] = payload.get("messages", [])
    memory_anchor: Optional[str] = payload.get("memory_anchor", None)
    result: AgentState = await agent.ainvoke({
        "messages": prior_messages,
        "task": task,
        "model_name": "",
        "model_endpoint": "",
        "role": "",
        "memory_anchor": memory_anchor,
    })
    return result


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # Fix #3: bind to loopback only; Tailscale handles remote access
    uvicorn.run("orchestrator:app", host="127.0.0.1", port=8080, reload=False)
