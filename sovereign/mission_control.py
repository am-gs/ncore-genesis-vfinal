#!/usr/bin/env python3
"""
Sovereign Mission Control — Cognitive Execution Control Plane.

Designed to be compatible with langchain-ai/deepagents SDK patterns:
- Planning tool: plan_steps field maps to Deep Agents' planning
- Subagent spawning: /spawn endpoint maps to Deep Agents' subagent spawning
- Filesystem backend: artifacts stored as JSON in the task store
- Task state machine maps to LangGraph node states
"""

import asyncio
import json
import os
import random
import subprocess
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse

import manus_engine

ROOT = Path('/home/ubuntu/sovereign')
LOGS = ROOT / 'logs'
TASKS_FILE = ROOT / 'tasks.json'

app = FastAPI(title='Sovereign Mission Control')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

SERVICES = {
    'Agent Zero': {'type': 'http', 'url': 'http://127.0.0.1:8090/api/health', 'restart': ['docker', 'restart', 'agent-zero'], 'link': 'http://ncore-v2:8090'},
    'Bifrost': {'type': 'systemd', 'unit': 'sovereign-bifrost', 'url': 'http://127.0.0.1:8000/health', 'link': 'http://127.0.0.1:8000/health'},
    'DeerFlow': {'type': 'systemd', 'unit': 'sovereign-deerflow', 'url': 'http://127.0.0.1:2026/api/health', 'link': 'http://127.0.0.1:2026/api/health'},
    'Mem0': {'type': 'systemd', 'unit': 'sovereign-mem0', 'url': 'http://127.0.0.1:8300/health', 'link': 'http://127.0.0.1:8300/health'},
    'Chroma': {'type': 'compose', 'service': 'chroma', 'url': 'http://127.0.0.1:8200/api/v2/heartbeat', 'link': 'http://127.0.0.1:8200/api/v2/heartbeat'},
    'Postgres': {'type': 'compose', 'service': 'postgres', 'tcp': '127.0.0.1:5432'},
    'Redis': {'type': 'compose', 'service': 'redis', 'tcp': '127.0.0.1:6380'},
    'Grafana': {'type': 'compose', 'service': 'grafana', 'url': 'http://127.0.0.1:3001/login', 'link': 'http://127.0.0.1:3001'},
    'Dashboard': {'type': 'systemd', 'unit': 'ncore-dashboard', 'url': 'http://127.0.0.1:3002/', 'link': 'http://127.0.0.1:3002'},
}

# ---------------------------------------------------------------------------
# Task State Machine
# ---------------------------------------------------------------------------

class TaskState(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_dict(
    name: str,
    description: str,
    agent: str,
    status: TaskState = TaskState.PLANNING,
    plan_steps: Optional[List[dict]] = None,
    parent_id: Optional[str] = None,
    branch_from: Optional[str] = None,
) -> dict:
    now = iso_now()
    plan = []
    if plan_steps:
        for step in plan_steps:
            plan.append({
                "id": str(uuid.uuid4()),
                "description": step.get("description", ""),
                "status": TaskState.PENDING,
                "agent": step.get("agent") or agent,
                "depends_on": step.get("depends_on", []),
                "output": None,
            })
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "status": status,
        "agent": agent,
        "progress": 0.0,
        "created_at": now,
        "updated_at": now,
        "plan": plan,
        "subtasks": [],
        "parent_id": parent_id,
        "branch_from": branch_from,
        "latency_ms": 0,
        "retries": 0,
        "error": None,
        "artifacts": [],
        "memory_refs": [],
    }


# In-memory store + persistence
_tasks: dict[str, dict] = {}
_simulation_tasks: dict[str, asyncio.Task] = {}
_manus_orchs: dict[str, Any] = {}
_lock = asyncio.Lock()
_sse_queues: dict[str, asyncio.Queue] = {}


def _load_tasks() -> None:
    global _tasks
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE, "r") as f:
                data = json.load(f)
            _tasks = {t["id"]: t for t in data}
        except Exception:
            _tasks = {}
    else:
        _tasks = {}


def _save_tasks() -> None:
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump(list(_tasks.values()), f, indent=2)
    except Exception:
        pass


_load_tasks()


def _broadcast(task_id: str, data: dict) -> None:
    """Broadcast task update to all SSE listeners."""
    payload = json.dumps({"task_id": task_id, "data": data})
    for q in list(_sse_queues.values()):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

async def _simulate_task(task_id: str) -> None:
    while True:
        await asyncio.sleep(random.uniform(2.0, 5.0))
        async with _lock:
            task = _tasks.get(task_id)
            if not task or task["status"] != TaskState.RUNNING:
                return
            # Random failure (10% chance per tick)
            if random.random() < 0.10:
                task["status"] = TaskState.FAILED
                task["error"] = "Simulated agent failure during execution"
                task["updated_at"] = iso_now()
                _save_tasks()
                _broadcast(task_id, {"status": "failed", "error": task["error"]})
                return
            # Increment progress
            inc = random.uniform(10.0, 25.0)
            task["progress"] = min(100.0, task["progress"] + inc)
            if task["progress"] >= 100.0:
                task["status"] = TaskState.COMPLETED
                task["progress"] = 100.0
            task["updated_at"] = iso_now()
            _save_tasks()
            _broadcast(task_id, {"status": task["status"], "progress": task["progress"]})
            if task["status"] == TaskState.COMPLETED:
                return


def _start_simulation(task_id: str) -> None:
    if task_id in _simulation_tasks:
        _simulation_tasks[task_id].cancel()
    _simulation_tasks[task_id] = asyncio.create_task(_simulate_task(task_id))


def _stop_simulation(task_id: str) -> None:
    t = _simulation_tasks.pop(task_id, None)
    if t:
        t.cancel()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_task(task_id: str) -> dict:
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return task


def _cascade_cancel(task_id: str) -> None:
    task = _tasks.get(task_id)
    if not task:
        return
    task["status"] = TaskState.CANCELLED
    task["updated_at"] = iso_now()
    _stop_simulation(task_id)
    # Cancel any active Manus orchestrator for this task
    orch = _manus_orchs.pop(task_id, None)
    if orch:
        orch.cancel()
    for sub_id in task.get("subtasks", []):
        _cascade_cancel(sub_id)


def _task_to_json(task: dict, depth: int = 0) -> dict:
    out = dict(task)
    if depth < 3:
        out["subtasks_detail"] = []
        for sid in task.get("subtasks", []):
            sub = _tasks.get(sid)
            if sub:
                out["subtasks_detail"].append(_task_to_json(sub, depth + 1))
    return out


def _build_tree(task: dict) -> dict:
    node = dict(task)
    node["children"] = []
    for sid in task.get("subtasks", []):
        sub = _tasks.get(sid)
        if sub:
            node["children"].append(_build_tree(sub))
    return node


def _get_branches(task_id: str) -> List[dict]:
    results = []
    for t in _tasks.values():
        if t.get("branch_from") == task_id:
            results.append(t)
    return results


def _decompose_plan_steps(parent_id: str, steps: List[dict], agent: str) -> List[str]:
    sub_ids = []
    for step in steps:
        child = new_task_dict(
            name=step.get("description", "Subtask"),
            description=step.get("description", ""),
            agent=step.get("agent") or agent,
            status=TaskState.PENDING,
            parent_id=parent_id,
        )
        if step.get("sub_steps"):
            child["subtasks"] = _decompose_plan_steps(child["id"], step["sub_steps"], agent)
        _tasks[child["id"]] = child
        sub_ids.append(child["id"])
    return sub_ids


async def _run_manus(task_id: str) -> None:
    """Helper to launch a Manus orchestrator loop for a task."""
    try:
        await manus_engine._run_manus(task_id)
    finally:
        _manus_orchs.pop(task_id, None)


# ---------------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------------

def run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


async def http_ok(url: str) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
        return r.status_code < 500, (time.perf_counter() - started) * 1000, str(r.status_code)
    except Exception as e:
        return False, (time.perf_counter() - started) * 1000, str(e)


@app.get('/api/health')
async def health():
    cards = []
    for name, cfg in SERVICES.items():
        ok = True
        detail = ''
        latency = 0.0
        if 'url' in cfg:
            ok, latency, detail = await http_ok(cfg['url'])
        elif 'unit' in cfg:
            rc, out = run(['systemctl', 'is-active', cfg['unit']])
            ok, detail = rc == 0 and out.strip() == 'active', out
        elif 'service' in cfg:
            rc, out = run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '--env-file', str(ROOT / '.env'), 'ps', cfg['service']])
            ok, detail = rc == 0 and 'Up' in out, out.splitlines()[-1] if out else ''
        cards.append({'name': name, 'ok': ok, 'latency_ms': round(latency, 1), 'detail': detail, 'link': cfg.get('link', '')})
    return {'services': cards}


@app.get('/api/runs')
async def runs(limit: int = 30):
    safe_limit = max(1, min(limit, 200))
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f'http://127.0.0.1:8000/runs?limit={safe_limit}')
        return r.json()
    except Exception as e:
        return {'runs': [], 'error': str(e)}


@app.get('/api/logs/{name}')
async def logs(name: str, lines: int = 120):
    allowed = {
        'watchdog': LOGS / 'watchdog.log',
        'bifrost': LOGS / 'bifrost.log',
        'regression': max(LOGS.glob('regression_*.log'), default=LOGS / 'missing.log'),
    }
    path = allowed.get(name)
    if not path or not path.exists():
        return PlainTextResponse('log not found', status_code=404)
    data = path.read_text(errors='replace').splitlines()[-min(lines, 500):]
    return PlainTextResponse('\n'.join(data))


@app.post('/api/restart/{name}')
async def restart(name: str):
    svc = next((v for k, v in SERVICES.items() if k.lower().replace(' ', '-') == name), None)
    if not svc:
        raise HTTPException(404, 'unknown service')
    if 'restart' in svc:
        cmd = svc['restart']
    elif 'unit' in svc:
        cmd = ['sudo', '-n', 'systemctl', 'restart', svc['unit']]
    elif 'service' in svc:
        cmd = ['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '--env-file', str(ROOT / '.env'), 'restart', svc['service']]
    else:
        raise HTTPException(400, 'service cannot be restarted')
    rc, out = run(cmd, timeout=60)
    return {'ok': rc == 0, 'output': out[-2000:]}


@app.get('/', response_class=HTMLResponse)
async def index():
    return HTML


# ---------------------------------------------------------------------------
# SSE Streaming — Real-time task updates
# ---------------------------------------------------------------------------

@app.get("/api/tasks/stream")
async def stream_tasks():
    """Server-Sent Events endpoint for real-time task updates."""
    q = asyncio.Queue(maxsize=100)
    listener_id = str(uuid.uuid4())
    _sse_queues[listener_id] = q

    async def event_generator():
        try:
            # Send initial snapshot
            async with _lock:
                yield f"data: {json.dumps({'type': 'snapshot', 'tasks': list(_tasks.values())})}\n\n"
            while True:
                payload = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {payload}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _sse_queues.pop(listener_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Task Execution Control Plane endpoints
# ---------------------------------------------------------------------------

@app.get("/api/tasks")
async def list_tasks(status: Optional[TaskState] = None, limit: int = Query(100)):
    async with _lock:
        items = list(_tasks.values())
        if status:
            items = [t for t in items if t["status"] == status]
        items = items[:max(1, min(limit, 1000))]
        return {"tasks": items}


@app.post("/api/tasks")
async def create_task(body: dict):
    name = body.get("name")
    description = body.get("description", "")
    agent = body.get("agent", "default")
    plan_steps = body.get("plan_steps")
    if not name:
        raise HTTPException(400, "name is required")

    async with _lock:
        task = new_task_dict(name, description, agent, status=TaskState.PLANNING, plan_steps=plan_steps)
        if plan_steps and len(plan_steps) > 1:
            task["subtasks"] = _decompose_plan_steps(task["id"], plan_steps, agent)
        _tasks[task["id"]] = task
        _save_tasks()

    # Transition planning -> running -> start simulation
    async with _lock:
        task["status"] = TaskState.RUNNING
        task["updated_at"] = iso_now()
        _save_tasks()
    _start_simulation(task["id"])
    _broadcast(task["id"], {"status": "running", "progress": 0})

    return task


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    async with _lock:
        task = _resolve_task(task_id)
        return _task_to_json(task)


@app.post("/api/tasks/{task_id}/spawn")
async def spawn_subtask(task_id: str, body: dict):
    parent = _resolve_task(task_id)
    name = body.get("name")
    description = body.get("description", "")
    agent = body.get("agent", parent.get("agent", "default"))
    if not name:
        raise HTTPException(400, "name is required")

    async with _lock:
        child = new_task_dict(name, description, agent, status=TaskState.PLANNING, parent_id=task_id)
        child["status"] = TaskState.RUNNING
        child["updated_at"] = iso_now()
        _tasks[child["id"]] = child
        parent["subtasks"].append(child["id"])
        parent["updated_at"] = iso_now()
        _save_tasks()

    _start_simulation(child["id"])
    _broadcast(task_id, {"type": "spawn", "subtask_id": child["id"]})
    return child


@app.post("/api/tasks/{task_id}/branch")
async def branch_task(task_id: str, body: dict):
    source = _resolve_task(task_id)
    name = body.get("name")
    description = body.get("description", "")
    from_step_id = body.get("from_step_id")
    if not name:
        raise HTTPException(400, "name is required")

    # Copy relevant plan steps from the source task
    copied_plan = []
    for step in source.get("plan", []):
        if not from_step_id or step["id"] == from_step_id:
            copied_plan.append({
                "id": str(uuid.uuid4()),
                "description": step["description"],
                "status": TaskState.PENDING,
                "agent": step.get("agent"),
                "depends_on": [],
                "output": None,
            })
            if from_step_id:
                break

    async with _lock:
        task = new_task_dict(
            name=name,
            description=description,
            agent=source.get("agent", "default"),
            status=TaskState.RUNNING,
            plan_steps=copied_plan,
            branch_from=task_id,
        )
        _tasks[task["id"]] = task
        _save_tasks()

    _start_simulation(task["id"])
    _broadcast(task_id, {"type": "branch", "branch_id": task["id"]})
    return task


@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str):
    async with _lock:
        task = _resolve_task(task_id)
        if task["status"] != TaskState.RUNNING:
            raise HTTPException(400, "task is not running")
        task["status"] = TaskState.PAUSED
        task["updated_at"] = iso_now()
        _save_tasks()
    _stop_simulation(task_id)
    _broadcast(task_id, {"status": "paused"})
    return task


@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: str):
    async with _lock:
        task = _resolve_task(task_id)
        if task["status"] != TaskState.PAUSED:
            raise HTTPException(400, "task is not paused")
        task["status"] = TaskState.RUNNING
        task["updated_at"] = iso_now()
        _save_tasks()
    _start_simulation(task_id)
    _broadcast(task_id, {"status": "running"})
    return task


@app.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: str):
    async with _lock:
        task = _resolve_task(task_id)
        task["retries"] += 1
        task["status"] = TaskState.RETRYING
        task["error"] = None
        task["updated_at"] = iso_now()
        _save_tasks()

    async def _delayed_resume():
        await asyncio.sleep(2.0)
        async with _lock:
            t = _tasks.get(task_id)
            if t and t["status"] == TaskState.RETRYING:
                t["status"] = TaskState.RUNNING
                t["updated_at"] = iso_now()
                _save_tasks()
        _start_simulation(task_id)
        _broadcast(task_id, {"status": "running", "retries": task["retries"]})

    asyncio.create_task(_delayed_resume())
    return task


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    async with _lock:
        _resolve_task(task_id)
        _cascade_cancel(task_id)
        _save_tasks()
    _broadcast(task_id, {"status": "cancelled"})
    return _tasks.get(task_id)


@app.get("/api/tasks/{task_id}/tree")
async def get_tree(task_id: str):
    async with _lock:
        task = _resolve_task(task_id)
        return {"tree": _build_tree(task)}


@app.get("/api/tasks/{task_id}/trajectory")
async def get_trajectory(task_id: str):
    async with _lock:
        _resolve_task(task_id)
        branches = _get_branches(task_id)
        return {"task_id": task_id, "branches": branches}


# ---------------------------------------------------------------------------
# Manus autonomous execution endpoints
# ---------------------------------------------------------------------------

@app.post("/api/tasks/{task_id}/execute")
async def execute_task(task_id: str):
    """Start Manus autonomous execution on a task."""
    async with _lock:
        task = _resolve_task(task_id)
        if task["status"] != TaskState.PLANNING:
            raise HTTPException(400, "task must be in planning state")
        task["status"] = TaskState.RUNNING
        task["updated_at"] = iso_now()
        _save_tasks()
    # Cancel any stale simulation for this task first.
    _stop_simulation(task_id)
    _manus_orchs[task_id] = asyncio.create_task(_run_manus(task_id))
    _broadcast(task_id, {"status": "running", "agent": "manus"})
    return task


@app.post("/api/tasks/{task_id}/execute-langgraph")
async def execute_langgraph_task(task_id: str):
    """Start LangGraph autonomous execution on a task."""
    from langchain_agent import run_langgraph_task

    async with _lock:
        task = _resolve_task(task_id)
        if task["status"] != TaskState.PLANNING:
            raise HTTPException(400, "task must be in planning state")
        task["status"] = TaskState.RUNNING
        task["updated_at"] = iso_now()
        _save_tasks()
    _stop_simulation(task_id)
    _manus_orchs[task_id] = asyncio.create_task(
        run_langgraph_task(task_id, task.get("description", ""))
    )
    _broadcast(task_id, {"status": "running", "agent": "langgraph"})
    return task


@app.get("/api/tasks/{task_id}/screenshots")
async def get_screenshots(task_id: str):
    """Return list of screenshot paths/base64 for a task."""
    async with _lock:
        _resolve_task(task_id)
    shots = manus_engine._list_screenshots(task_id)
    return {"task_id": task_id, "screenshots": shots}


@app.post("/api/tasks/{task_id}/terminal")
async def terminal_command(task_id: str, body: dict):
    """Execute a one-off terminal command for a task."""
    async with _lock:
        _resolve_task(task_id)
    command = body.get("command", "")
    timeout = body.get("timeout", 30)
    if not command:
        raise HTTPException(400, "command is required")
    output = await manus_engine._manus_terminal_command(task_id, command, timeout=int(timeout))
    _broadcast(task_id, {"type": "terminal", "output": output})
    return {"task_id": task_id, "output": output}


@app.get("/api/tasks/{task_id}/artifacts")
async def get_artifacts(task_id: str):
    """List artifact files under /tmp/manus/{task_id}."""
    async with _lock:
        _resolve_task(task_id)
    return {"task_id": task_id, "artifacts": manus_engine._get_artifacts(task_id)}


# ---------------------------------------------------------------------------
# WebSocket interactive terminal
# ---------------------------------------------------------------------------

@app.websocket("/ws/terminal/{task_id}")
async def terminal_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    proc: Optional[asyncio.subprocess.Process] = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async def _reader():
            if proc.stdout is None:
                return
            while True:
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if not line:
                    break
                text = line.decode(errors="replace")
                await websocket.send_text(json.dumps({"type": "terminal", "output": text}))

        reader_task = asyncio.create_task(_reader())

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "input":
                inp = msg.get("data", "")
                if not inp.endswith("\n"):
                    inp += "\n"
                if proc.stdin is not None:
                    proc.stdin.write(inp.encode())
                    await proc.stdin.drain()
            elif msg.get("type") == "resize":
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if proc and proc.returncode is None:
            proc.kill()
            await proc.wait()
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass


HTML = r"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sovereign Mission Control</title>
<style>
:root{color-scheme:dark;--bg:#070a12;--panel:#0f172a;--muted:#94a3b8;--ok:#22c55e;--bad:#ef4444;--warn:#f59e0b;--text:#e5e7eb;--line:#1e293b;--accent:#8b5cf6}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#1e1b4b,#070a12 42%);font-family:Inter,ui-sans-serif,system-ui;color:var(--text)}header{padding:28px 32px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}.title{font-size:28px;font-weight:800}.sub{color:var(--muted);margin-top:6px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;padding:24px}.card{background:linear-gradient(180deg,rgba(15,23,42,.94),rgba(15,23,42,.72));border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 10px 35px rgba(0,0,0,.25)}.card h3{margin:0 0 10px}.pill{display:inline-flex;gap:8px;align-items:center;border-radius:999px;padding:5px 10px;font-size:12px;background:#111827;color:var(--muted)}.dot{width:9px;height:9px;border-radius:999px;background:var(--bad)}.ok .dot{background:var(--ok)}button,a.btn{background:#312e81;color:white;border:1px solid #4f46e5;border-radius:10px;padding:8px 10px;text-decoration:none;cursor:pointer;margin-right:6px}button:hover,a.btn:hover{background:#4338ca}.wide{grid-column:1/-1}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}pre{white-space:pre-wrap;background:#020617;border:1px solid var(--line);border-radius:12px;padding:14px;max-height:360px;overflow:auto}.metric{font-size:32px;font-weight:800;color:#c4b5fd}.small{font-size:12px;color:var(--muted)}
</style></head><body><header><div><div class="title">Sovereign Mission Control</div><div class="sub">Local high-compliance agentic stack · localhost/Tailscale only</div></div><button onclick="loadAll()">Refresh</button></header>
<section class="grid" id="services"></section><section class="grid"><div class="card wide"><h3>Recent Task Runs</h3><table><thead><tr><th>Time</th><th>Task</th><th>Provider</th><th>Model</th><th>Fallback</th><th>Latency</th><th>Status</th></tr></thead><tbody id="runs"></tbody></table></div><div class="card wide"><h3>Logs</h3><button onclick="loadLog('watchdog')">Watchdog</button><button onclick="loadLog('regression')">Regression</button><pre id="logs">Select a log.</pre></div></section>
<script>
async function j(u,o){let r=await fetch(u,o);return await r.json()}async function loadHealth(){let d=await j('/api/health');let el=document.getElementById('services');el.innerHTML='';for(let s of d.services){let id=s.name.toLowerCase().replaceAll(' ','-');el.innerHTML+=`<div class="card ${s.ok?'ok':''}"><h3>${s.name}</h3><div class="pill"><span class="dot"></span>${s.ok?'healthy':'unhealthy'} · ${s.latency_ms||0}ms</div><p class="small">${s.detail||''}</p><a class="btn" href="${s.link||'#'}" target="_blank">Open</a><button onclick="restart('${id}')">Restart</button></div>`}}async function loadRuns(){let d=await j('/api/runs');let rows=d.runs||[];document.getElementById('runs').innerHTML=rows.map(r=>`<tr><td>${new Date((r.ts||0)*1000).toLocaleString()}</td><td>${r.task_id||''}</td><td>${r.provider||''}</td><td>${r.model||''}</td><td>${r.fallback_reason||''}${r.refusal_intercepted?' ⚑':''}</td><td>${r.latency_ms||''}ms</td><td>${r.completion_status||''}</td></tr>`).join('')}async function loadLog(n){let r=await fetch('/api/logs/'+n);document.getElementById('logs').textContent=await r.text()}async function restart(n){let d=await j('/api/restart/'+n,{method:'POST'});alert((d.ok?'Restarted':'Failed')+'\n'+(d.output||''));loadAll()}function loadAll(){loadHealth();loadRuns()}loadAll();setInterval(loadAll,10000)
</script></body></html>
"""
