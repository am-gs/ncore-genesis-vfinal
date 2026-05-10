#!/usr/bin/env python3
"""
LangGraph-based agent orchestration for Sovereign Mission Control.

Integrates with Bifrost LLM gateway (Ollama-compatible OpenAI API)
and follows Deep Agents SDK patterns:
- Recursive planning via graph nodes
- Subagent spawning via conditional edges
- Browser grounding + terminal tools
- Memory persistence via Mem0 shim
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime, timezone

import httpx

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

try:
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from langchain_core.language_models import BaseChatModel
except ImportError:
    BaseChatModel = object
    HumanMessage = SystemMessage = AIMessage = object

BIFROST_URL = os.environ.get("BIFROST_URL", "http://127.0.0.1:8000")
DEFAULT_MODEL = "qwen3-8b:latest"


class AgentState(TypedDict):
    """LangGraph state schema for agent execution."""
    task_id: str
    task_description: str
    messages: List[Dict[str, str]]
    plan: List[Dict[str, Any]]
    current_step: int
    artifacts: List[Dict[str, Any]]
    subagents: List[str]
    memory: List[str]
    status: str  # planning, running, paused, completed, failed
    error: Optional[str]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BifrostLLM:
    """Ollama-compatible LLM client that routes through Bifrost gateway."""

    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 0.3):
        self.model = model
        self.temperature = temperature
        self.client = httpx.AsyncClient(timeout=180.0)

    async def invoke(self, messages: List[Dict[str, str]], max_tokens: int = 900) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        r = await self.client.post(
            f"{BIFROST_URL}/v1/chat/completions",
            json=payload,
            headers={"content-type": "application/json"},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Bifrost error {r.status_code}: {r.text}")
        data = r.json()
        choices = data.get("choices") or [{}]
        return str(choices[0].get("message", {}).get("content", ""))

    def __del__(self):
        asyncio.create_task(self.client.aclose()) if hasattr(self, 'client') else None


# ── Graph Nodes ────────────────────────────────────────────────────────────

async def plan_node(state: AgentState) -> AgentState:
    """Generate an execution plan from the task description."""
    llm = BifrostLLM()
    system = (
        "You are an autonomous execution planner for the Sovereign Mission Control system. "
        "Given a task description, emit a JSON array of execution steps. "
        "Each step has: tool (browser_navigate, browser_click, browser_screenshot, "
        "terminal_execute, file_read, file_write, code_execute_python, spawn_subagent), "
        "input (object with args), and description (string). "
        "Return ONLY valid JSON—no markdown fences."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Task: {state['task_description']}\n\nPlan:"},
    ]
    raw = await llm.invoke(messages, max_tokens=1200)
    cleaned = raw.strip().strip("`").strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        plan = json.loads(cleaned)
        if isinstance(plan, dict) and "steps" in plan:
            plan = plan["steps"]
        if not isinstance(plan, list):
            plan = []
    except Exception:
        plan = []
    if not plan:
        plan = [
            {
                "tool": "terminal_execute",
                "input": {"command": f"echo 'No plan generated for: {state['task_description']}'"},
                "description": "Fallback terminal step",
            }
        ]
    state["plan"] = plan
    state["status"] = "running"
    state["messages"].append(
        {"role": "assistant", "content": f"Generated plan with {len(plan)} steps"}
    )
    return state


async def execute_step_node(state: AgentState) -> AgentState:
    """Execute the current plan step."""
    if state["current_step"] >= len(state["plan"]):
        state["status"] = "completed"
        return state

    step = state["plan"][state["current_step"]]
    tool = step.get("tool", "")
    inp = step.get("input") or step.get("args") or {}
    if isinstance(inp, list) and len(inp) == 1 and isinstance(inp[0], dict):
        inp = inp[0]
    if not isinstance(inp, dict):
        inp = {}

    # Import manus_engine tools on demand
    import manus_engine

    orch = manus_engine.ManusOrchestrator(state["task_id"])
    result = {"ok": False, "error": f"Unknown tool: {tool}"}

    try:
        if tool == "browser_navigate":
            out = await orch.browser_navigate(inp.get("url", ""))
            result = {"ok": True, "output": out}
        elif tool == "browser_click":
            out = await orch.browser_click(inp.get("selector", ""))
            result = {"ok": True, "output": out}
        elif tool == "browser_screenshot":
            out = await orch.browser_screenshot()
            result = {"ok": True, "output": out}
        elif tool == "terminal_execute":
            out = await orch.terminal_execute(
                inp.get("command", ""), timeout=inp.get("timeout", 30)
            )
            result = {"ok": True, "output": out}
        elif tool == "file_read":
            out = await orch.file_read(inp.get("path", ""))
            result = {"ok": True, "output": out}
        elif tool == "file_write":
            out = await orch.file_write(
                inp.get("path", ""), inp.get("content", "")
            )
            result = {"ok": True, "output": out}
        elif tool == "code_execute_python":
            out = await orch.code_execute_python(inp.get("code", ""))
            result = {"ok": True, "output": out}
        elif tool == "spawn_subagent":
            out = await orch.spawn_subagent(
                inp.get("name", "subagent"), inp.get("description", "")
            )
            state["subagents"].append(out)
            result = {"ok": True, "output": out}
        else:
            result = {"ok": False, "error": f"Unknown tool: {tool}"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    finally:
        await orch.cleanup()

    state["artifacts"].append(
        {
            "step": state["current_step"],
            "tool": tool,
            "result": result,
            "timestamp": _iso_now(),
        }
    )
    state["messages"].append(
        {
            "role": "assistant",
            "content": f"Step {state['current_step']} ({tool}): {result['output'] if result.get('ok') else result.get('error')}",
        }
    )

    if not result.get("ok"):
        state["status"] = "failed"
        state["error"] = result.get("error")

    state["current_step"] += 1
    return state


async def decide_node(state: AgentState) -> AgentState:
    """Decide whether to continue, complete, or retry."""
    if state["status"] in ("completed", "failed"):
        return state

    llm = BifrostLLM()
    system = (
        "You are an execution controller. Given a task and execution history, "
        "decide the next action. Return ONLY a JSON object with keys: "
        "action ('continue', 'complete', 'retry'), reason (string). "
        "No markdown fences."
    )
    history = json.dumps(state["artifacts"], default=str)
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Task: {state['task_description']}\n\nHistory: {history}\n\nDecision:",
        },
    ]
    raw = await llm.invoke(messages, max_tokens=400)
    cleaned = raw.strip().strip("`").strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        decision = json.loads(cleaned)
    except Exception:
        decision = {"action": "continue", "reason": "Parsing failed; continuing"}

    action = decision.get("action", "continue")
    if action == "complete":
        state["status"] = "completed"
    elif action == "retry" and state["current_step"] > 0:
        state["current_step"] -= 1  # Retry last step
    # else continue

    state["messages"].append(
        {
            "role": "assistant",
            "content": f"Decision: {action} — {decision.get('reason', '')}",
        }
    )
    return state


def route_step(state: AgentState) -> str:
    """Conditional edge: route to next node based on state."""
    if state["status"] == "failed":
        return END
    if state["status"] == "completed":
        return END
    if state["current_step"] >= len(state["plan"]):
        return "decide"
    return "execute"


def route_after_decide(state: AgentState) -> str:
    """After decide node, route to next action."""
    if state["status"] in ("completed", "failed"):
        return END
    return "execute"


# ── Graph Builder ──────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    """Build and compile the LangGraph agent workflow."""
    builder = StateGraph(AgentState)

    builder.add_node("plan", plan_node)
    builder.add_node("execute", execute_step_node)
    builder.add_node("decide", decide_node)

    builder.set_entry_point("plan")
    builder.add_edge("plan", "execute")

    builder.add_conditional_edges(
        "execute",
        route_step,
        {"execute": "execute", "decide": "decide", END: END},
    )
    builder.add_conditional_edges(
        "decide",
        route_after_decide,
        {"execute": "execute", END: END},
    )

    return builder.compile(checkpointer=MemorySaver())


# ── Public API ───────────────────────────────────────────────────────────

_agent_graph = None


def get_agent_graph():
    """Lazy-init singleton graph."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


async def run_langgraph_task(
    task_id: str,
    task_description: str,
    thread_id: Optional[str] = None,
) -> AgentState:
    """Run a task through the LangGraph agent pipeline.

    Integrates with Mission Control's task store and broadcasts updates.
    """
    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id or task_id}}

    initial_state: AgentState = {
        "task_id": task_id,
        "task_description": task_description,
        "messages": [
            {"role": "user", "content": task_description},
        ],
        "plan": [],
        "current_step": 0,
        "artifacts": [],
        "subagents": [],
        "memory": [],
        "status": "planning",
        "error": None,
    }

    # Import mission_control for broadcasting
    import mission_control as mc

    mc._broadcast(task_id, {"status": "planning", "agent": "langgraph"})

    final_state = await graph.ainvoke(initial_state, config=config)

    mc._broadcast(
        task_id,
        {
            "status": final_state["status"],
            "artifacts": len(final_state["artifacts"]),
            "subagents": len(final_state["subagents"]),
        },
    )

    return final_state
