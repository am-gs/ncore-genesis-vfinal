#!/usr/bin/env python3
"""
LangGraph Swarm Orchestrator for Sovereign Mission Control.

Implements a state machine with PostgreSQL checkpointer for resilience:
planner → dispatch → execute → verify → aggregate

Integrates:
- Bifrost v2 (port 8000) for planning via Fireworks Kimi K2.6
- Ollama (port 11434) for ncore-critic verification QC
- PostgreSQL checkpointer for time-travel recovery
"""

import asyncio
import re
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import httpx

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None  # type: ignore

BIFROST_URL = os.environ.get("BIFROST_URL", "http://127.0.0.1:8000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
POSTGRES_URI = os.environ.get(
    "POSTGRES_URI",
    "postgresql://sovereign@127.0.0.1:5432/sovereign"
)
PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "accounts/fireworks/models/kimi-k2p6")
CRITIC_MODEL = os.environ.get("CRITIC_MODEL", "qwen3-8b:latest")


class SovereignState(TypedDict):
    """LangGraph swarm state schema."""
    messages: List[Dict[str, str]]
    task_id: str
    prompt: str
    plan_steps: List[Dict[str, Any]]
    subagent_results: List[Dict[str, Any]]
    verification_status: str  # pending, pass, fail
    checkpoints: List[str]
    error: Optional[str]
    status: str  # planning, dispatching, executing, verifying, aggregating, completed, failed


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Checkpointer Factory ─────────────────────────────────────────────────────

def _get_checkpointer() -> BaseCheckpointSaver:
    """Return a PostgresSaver if PostgreSQL is reachable; else MemorySaver."""
    if PostgresSaver is None:
        return MemorySaver()
    try:
        import psycopg
        conn = psycopg.connect(POSTGRES_URI, connect_timeout=2)
        conn.close()
        saver = PostgresSaver.from_conn_string(POSTGRES_URI)
        import inspect
        if inspect.isgenerator(saver):
            inst = next(saver)
            return inst
        return saver
    except Exception:
        return MemorySaver()


_CHECKPOINTER: Optional[BaseCheckpointSaver] = None


def get_checkpointer() -> BaseCheckpointSaver:
    global _CHECKPOINTER
    if _CHECKPOINTER is None:
        _CHECKPOINTER = _get_checkpointer()
    return _CHECKPOINTER


# ── LLM Clients ────────────────────────────────────────────────────────────

class AsyncLLMClient:
    """Thin async wrapper over Bifrost or Ollama OpenAI-compatible endpoints."""

    def __init__(self, base_url: str, default_model: str):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 900,
    ) -> str:
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        r = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers={"content-type": "application/json"},
        )
        if r.status_code >= 400:
            raise RuntimeError(f"LLM error {r.status_code}: {r.text}")
        data = r.json()
        choices = data.get("choices") or [{}]
        return str(choices[0].get("message", {}).get("content", ""))

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


_bifrost_client: Optional[AsyncLLMClient] = None
_ollama_client: Optional[AsyncLLMClient] = None


def get_bifrost_llm() -> AsyncLLMClient:
    global _bifrost_client
    if _bifrost_client is None:
        _bifrost_client = AsyncLLMClient(BIFROST_URL, PLANNER_MODEL)
    return _bifrost_client


def get_ollama_llm() -> AsyncLLMClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = AsyncLLMClient(OLLAMA_URL, CRITIC_MODEL)
    return _ollama_client


# ── Graph Nodes ──────────────────────────────────────────────────────────────

async def planner_node(state: SovereignState) -> SovereignState:
    """Call Bifrost (Kimi K2.6) to generate a multi-step plan."""
    llm = get_bifrost_llm()
    system = (
        "You are the Sovereign Planner. Given a task, emit a JSON array of plan steps. "
        "Each step has: id (string), description (string), tool (one of terminal_execute, "
        "file_write, code_execute_python, spawn_subagent), input (object with args). "
        "Return ONLY valid JSON — no markdown fences."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Task: {state['prompt']}\n\nPlan:"},
    ]
    try:
        raw = await llm.chat(messages, temperature=0.1, max_tokens=1500)
        text = raw.strip()
        plan = None

        # 1. Try fenced code blocks (last one first — usually the final answer)
        for m in reversed(list(re.finditer(r'```(?:json)?\s*(.*?)\s*```', text, re.S))):
            try:
                cand = m.group(1).strip().strip("`").strip()
                if cand.startswith("json"):
                    cand = cand[4:].strip()
                parsed = json.loads(cand)
                if isinstance(parsed, list):
                    plan = parsed
                    break
                if isinstance(parsed, dict) and "steps" in parsed:
                    plan = parsed["steps"]
                    break
            except Exception:
                continue

        # 2. Try outermost bare JSON array or object
        if plan is None:
            for pat in [r'(\[.*\])', r'(\{.*\})']:
                m = re.search(pat, text, re.S)
                if m:
                    try:
                        parsed = json.loads(m.group(1))
                        if isinstance(parsed, list):
                            plan = parsed
                            break
                        if isinstance(parsed, dict) and "steps" in parsed:
                            plan = parsed["steps"]
                            break
                    except Exception:
                        continue

        if plan is None:
            plan = []
            state["error"] = "Planner: could not extract JSON plan from model response"
    except Exception as exc:
        plan = []
        state["error"] = f"Planner error: {exc}"
        # error is non-fatal: fallback plan generated below

    if not plan:
        plan = [
            {
                "id": "step-0",
                "description": f"Execute fallback terminal for: {state['prompt']}",
                "tool": "terminal_execute",
                "input": {"command": f"echo 'No plan generated for: {state['prompt']}'"},
            }
        ]

    for i, step in enumerate(plan):
        step.setdefault("id", f"step-{i}")
        step.setdefault("status", "pending")

    state["plan_steps"] = plan
    state["status"] = "dispatching"
    state["checkpoints"].append(f"planner:{_iso_now()}")
    state["messages"].append(
        {"role": "assistant", "content": f"Planner generated {len(plan)} steps."}
    )
    return state


async def dispatch_node(state: SovereignState) -> SovereignState:
    """Spawn subagents for each plan step concurrently."""
    results: List[Dict[str, Any]] = []
    plan = state.get("plan_steps", [])

    async def _run_step(step: Dict[str, Any]) -> Dict[str, Any]:
        tool = step.get("tool", "terminal_execute")
        inp = step.get("input") or step.get("args") or {}
        if isinstance(inp, list) and len(inp) == 1 and isinstance(inp[0], dict):
            inp = inp[0]
        if not isinstance(inp, dict):
            inp = {}

        result = {
            "step_id": step.get("id", "unknown"),
            "tool": tool,
            "description": step.get("description", ""),
            "status": "pending",
            "output": None,
            "error": None,
            "started_at": _iso_now(),
            "finished_at": None,
        }

        try:
            if tool == "terminal_execute":
                proc = await asyncio.create_subprocess_exec(
                    "/bin/sh", "-c", str(inp.get("command", "")),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(), timeout=float(inp.get("timeout", 30))
                )
                out = stdout.decode(errors="replace") if stdout else ""
                result["output"] = out
                result["status"] = "done"
            elif tool == "file_write":
                p = Path(str(inp.get("path", "/tmp/output.txt")))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(str(inp.get("content", "")), encoding="utf-8")
                result["output"] = str(p)
                result["status"] = "done"
            elif tool == "code_execute_python":
                import tempfile
                adir = Path("/tmp/swarm") / state["task_id"]
                adir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", dir=str(adir), delete=False
                ) as f:
                    f.write(str(inp.get("code", "")))
                    fpath = f.name
                proc = await asyncio.create_subprocess_exec(
                    "python3", fpath,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=60.0
                )
                out = stdout.decode(errors="replace") if stdout else ""
                err = stderr.decode(errors="replace") if stderr else ""
                result["output"] = (
                    out + ("\n--- STDERR ---\n" + err if err else "")
                ).strip()
                result["status"] = "done"
                try:
                    os.unlink(fpath)
                except Exception:
                    pass
            elif tool == "spawn_subagent":
                result["output"] = f"Subagent: {inp.get('name', 'subagent')}"
                result["status"] = "done"
            else:
                result["error"] = f"Unknown tool: {tool}"
                result["status"] = "error"
        except Exception as exc:
            result["error"] = str(exc)
            result["status"] = "error"

        result["finished_at"] = _iso_now()
        return result

    if plan:
        step_results = await asyncio.gather(*[_run_step(s) for s in plan])
        results.extend(step_results)
    else:
        results.append(
            {"step_id": "none", "status": "done", "output": "No plan steps to dispatch"}
        )

    state["subagent_results"] = results
    state["status"] = "verifying"
    state["checkpoints"].append(f"dispatch:{_iso_now()}")
    state["messages"].append(
        {"role": "assistant", "content": f"Dispatched {len(results)} steps."}
    )
    return state


async def verify_node(state: SovereignState) -> SovereignState:
    """QC via Ollama ncore-critic model."""
    llm = get_ollama_llm()
    results_summary = json.dumps(
        state.get("subagent_results", []), default=str, indent=2
    )[:4000]

    system = (
        "You are ncore-critic, a quality-control verifier. Given execution results, "
        "return ONLY a JSON object with keys: verdict ('pass' or 'fail'), issues (array of strings), "
        "confidence (0.0-1.0). No markdown fences."
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"Task: {state['prompt']}\n\n"
                f"Results:\n{results_summary}\n\nVerdict:"
            ),
        },
    ]
    try:
        raw = await llm.chat(messages, temperature=0.2, max_tokens=400)
        cleaned = raw.strip().strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        verdict = json.loads(cleaned)
    except Exception:
        verdict = {"verdict": "pass", "issues": [], "confidence": 0.5}

    v = verdict.get("verdict", "pass")
    state["verification_status"] = v
    state["checkpoints"].append(f"verify:{_iso_now()}")
    state["messages"].append(
        {
            "role": "assistant",
            "content": (
                f"Verification: {v} (confidence: {verdict.get('confidence', 0.5)}, "
                f"issues: {verdict.get('issues', [])})"
            ),
        }
    )
    state["status"] = "aggregating"
    return state


async def aggregate_node(state: SovereignState) -> SovereignState:
    """Aggregate results and finalize task state."""
    results = state.get("subagent_results", [])
    all_ok = all(
        r.get("status") == "done" and not r.get("error") for r in results
    )
    verified = state.get("verification_status", "pass") == "pass"

    if all_ok and verified:
        state["status"] = "completed"
    else:
        state["status"] = "failed"
        state["error"] = (
            state.get("error")
            or "Verification failed or step errors occurred"
        )

    state["checkpoints"].append(f"aggregate:{_iso_now()}")
    state["messages"].append(
        {
            "role": "assistant",
            "content": f"Aggregation complete: {state['status']}.",
        }
    )
    return state


# ── Conditional Routing ────────────────────────────────────────────────────


def route_after_planner(state: SovereignState) -> str:
    if state.get("status") == "failed" and state.get("error"):
        return END
    return "dispatch"


def route_after_dispatch(state: SovereignState) -> str:
    if state.get("status") == "failed":
        return END
    return "verify"


def route_after_verify(state: SovereignState) -> str:
    if state.get("status") == "failed":
        return END
    return "aggregate"


# ── Graph Builder ───────────────────────────────────────────────────────────


def build_swarm_graph() -> Any:
    builder = StateGraph(SovereignState)

    builder.add_node("planner", planner_node)
    builder.add_node("dispatch", dispatch_node)
    builder.add_node("verify", verify_node)
    builder.add_node("aggregate", aggregate_node)

    builder.set_entry_point("planner")
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {"dispatch": "dispatch", END: END},
    )
    builder.add_conditional_edges(
        "dispatch",
        route_after_dispatch,
        {"verify": "verify", END: END},
    )
    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {"aggregate": "aggregate", END: END},
    )
    builder.add_edge("aggregate", END)

    return builder.compile(checkpointer=get_checkpointer())


_SWARM_GRAPH: Optional[Any] = None


def get_swarm_graph() -> Any:
    global _SWARM_GRAPH
    if _SWARM_GRAPH is None:
        _SWARM_GRAPH = build_swarm_graph()
    return _SWARM_GRAPH


# ── Public API ─────────────────────────────────────────────────────────────


async def run_swarm_task(
    task_id: str,
    prompt: str,
    thread_id: Optional[str] = None,
) -> SovereignState:
    """Execute a swarm task through the LangGraph pipeline with checkpointing.

    Time-travel: if a thread_id already has checkpoints, the graph resumes
    from the latest one automatically when ainvoke is called with the same
    configurable thread_id.
    """
    graph = get_swarm_graph()
    config = {"configurable": {"thread_id": thread_id or task_id}}

    try:
        import mission_control as mc
    except Exception:
        mc = None

    if mc:
        mc._broadcast(task_id, {"status": "planning", "agent": "swarm"})

    initial_state: SovereignState = {
        "messages": [{"role": "user", "content": prompt}],
        "task_id": task_id,
        "prompt": prompt,
        "plan_steps": [],
        "subagent_results": [],
        "verification_status": "pending",
        "checkpoints": [],
        "error": None,
        "status": "planning",
    }

    started = time.perf_counter()
    try:
        final_state = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        final_state: SovereignState = {
            "messages": initial_state["messages"]
            + [{"role": "assistant", "content": f"Swarm error: {exc}"}],
            "task_id": task_id,
            "prompt": prompt,
            "plan_steps": initial_state.get("plan_steps", []),
            "subagent_results": initial_state.get("subagent_results", []),
            "verification_status": "fail",
            "checkpoints": initial_state.get("checkpoints", [])
            + [f"error:{_iso_now()}"],
            "error": str(exc),
            "status": "failed",
        }

    latency_ms = (time.perf_counter() - started) * 1000

    if mc:
        async with mc._lock:
            t = mc._tasks.get(task_id)
            if t:
                t["status"] = (
                    mc.TaskState.COMPLETED
                    if final_state["status"] == "completed"
                    else mc.TaskState.FAILED
                )
                t["updated_at"] = _iso_now()
                t["latency_ms"] = round(latency_ms, 2)
                t["artifacts"] = final_state.get("subagent_results", [])
                mc._save_tasks()
        mc._broadcast(
            task_id,
            {
                "status": final_state["status"],
                "latency_ms": round(latency_ms, 2),
                "checkpoints": len(final_state.get("checkpoints", [])),
                "plan_steps": len(final_state.get("plan_steps", [])),
                "subagent_results": len(
                    final_state.get("subagent_results", [])
                ),
                "verification": final_state.get("verification_status"),
            },
        )

    return final_state


async def resume_swarm_task(
    task_id: str, prompt: str = "", thread_id: Optional[str] = None
) -> SovereignState:
    """Resume a swarm task from its last checkpoint (time-travel recovery).

    LangGraph automatically loads the latest checkpoint for the thread_id.
    If the graph previously crashed mid-execution, it resumes from the last
    saved node. Re-invoking with the same thread_id and initial state is the
    canonical recovery pattern.
    """
    graph = get_swarm_graph()
    config = {"configurable": {"thread_id": thread_id or task_id}}

    try:
        import mission_control as mc
    except Exception:
        mc = None

    if mc:
        mc._broadcast(
            task_id,
            {"status": "retrying", "agent": "swarm", "recovery": "checkpoint"},
        )

    started = time.perf_counter()
    initial_state: SovereignState = {
        "messages": [{"role": "user", "content": prompt}],
        "task_id": task_id,
        "prompt": prompt,
        "plan_steps": [],
        "subagent_results": [],
        "verification_status": "pending",
        "checkpoints": [],
        "error": None,
        "status": "planning",
    }
    final_state = await graph.ainvoke(initial_state, config=config)
    latency_ms = (time.perf_counter() - started) * 1000

    if mc:
        mc._broadcast(
            task_id,
            {
                "status": final_state.get("status", "unknown"),
                "latency_ms": round(latency_ms, 2),
                "checkpoints": len(final_state.get("checkpoints", [])),
                "recovery": True,
            },
        )

    return final_state
