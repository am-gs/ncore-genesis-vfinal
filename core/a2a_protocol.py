"""
Google A2A (Agent-to-Agent) Protocol — FastAPI Router v0.1
Implements AgentCard, Task lifecycle, SSE streaming, and agent discovery.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

# ---------------------------------------------------------------------------
# A2A Data Models
# ---------------------------------------------------------------------------

class A2ATaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class Skill:
    id: str
    name: str
    description: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class AgentCard:
    name: str
    description: str
    url: str
    version: str
    skills: List[Skill]
    auth: Dict[str, Any] = field(default_factory=dict)
    default_input_modes: List[str] = field(default_factory=lambda: ["text"])
    default_output_modes: List[str] = field(default_factory=lambda: ["text"])

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "skills": [
                {"id": s.id, "name": s.name, "description": s.description, "tags": s.tags}
                for s in self.skills
            ],
            "auth": self.auth,
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
        }


@dataclass
class TaskMessage:
    role: str  # "user" | "agent"
    parts: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"role": self.role, "parts": self.parts, "metadata": self.metadata}


@dataclass
class Task:
    id: str
    status: A2ATaskStatus
    messages: List[TaskMessage] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "messages": [m.to_dict() for m in self.messages],
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass
class SendTaskRequest:
    id: str
    message: TaskMessage
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SendTaskResponse:
    id: str
    status: A2ATaskStatus
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status.value,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# In-memory registry
# ---------------------------------------------------------------------------

_agent_cards: Dict[str, AgentCard] = {}
_a2a_tasks: Dict[str, Task] = {}
_a2a_listeners: Dict[str, asyncio.Queue] = {}
_a2a_lock = asyncio.Lock()


def _a2a_broadcast(task_id: str, event: dict) -> None:
    payload = json.dumps({"task_id": task_id, **event})
    for q in list(_a2a_listeners.values()):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def register_agent_card(card: AgentCard) -> str:
    agent_id = card.name.lower().replace(" ", "-").replace("_", "-")
    _agent_cards[agent_id] = card
    return agent_id


def get_agent_card(agent_id: str) -> Optional[AgentCard]:
    return _agent_cards.get(agent_id)


def list_agent_cards() -> List[AgentCard]:
    return list(_agent_cards.values())


async def create_a2a_task(request: SendTaskRequest) -> Task:
    task = Task(
        id=request.id or str(uuid.uuid4()),
        status=A2ATaskStatus.SUBMITTED,
        messages=[request.message],
        metadata=request.metadata,
    )
    async with _a2a_lock:
        _a2a_tasks[task.id] = task
    _a2a_broadcast(task.id, {"type": "created", "status": task.status.value})
    return task


async def update_a2a_task_status(task_id: str, status: A2ATaskStatus, artifacts: Optional[List[dict]] = None) -> Task:
    async with _a2a_lock:
        task = _a2a_tasks.get(task_id)
        if not task:
            raise HTTPException(404, "A2A task not found")
        task.status = status
        task.updated_at = time.time()
        if artifacts is not None:
            task.artifacts.extend(artifacts)
    _a2a_broadcast(task_id, {"type": "status", "status": status.value})
    return task


async def add_a2a_message(task_id: str, message: TaskMessage) -> Task:
    async with _a2a_lock:
        task = _a2a_tasks.get(task_id)
        if not task:
            raise HTTPException(404, "A2A task not found")
        task.messages.append(message)
        task.updated_at = time.time()
    _a2a_broadcast(task_id, {"type": "message", "message": message.to_dict()})
    return task


async def get_a2a_task(task_id: str) -> Optional[Task]:
    async with _a2a_lock:
        return _a2a_tasks.get(task_id)


# ---------------------------------------------------------------------------
# FastAPI Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/a2a/v1")


@router.get("/agents")
async def list_agents():
    """Return all registered agent cards (A2A discovery)."""
    return {"agents": [card.to_dict() for card in list_agent_cards()]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    card = get_agent_card(agent_id)
    if not card:
        raise HTTPException(404, "agent not found")
    return card.to_dict()


@router.post("/tasks/send")
async def send_task(request: Request):
    """Submit a new A2A task."""
    body = await request.json()
    req = SendTaskRequest(
        id=body.get("id") or str(uuid.uuid4()),
        message=_parse_message(body.get("message", {})),
        metadata=body.get("metadata", {}),
    )
    task = await create_a2a_task(req)
    # Auto-transition to working after creation
    asyncio.create_task(_auto_working(task.id))
    return JSONResponse(content=task.to_dict(), status_code=201)


@router.get("/tasks/{task_id}/get")
async def get_task(task_id: str):
    """Retrieve an A2A task by ID."""
    task = await get_a2a_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return task.to_dict()


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel an A2A task."""
    task = await update_a2a_task_status(task_id, A2ATaskStatus.CANCELED)
    return task.to_dict()


@router.get("/tasks/stream")
async def stream_tasks():
    """SSE endpoint for real-time A2A task updates."""
    q = asyncio.Queue(maxsize=100)
    listener_id = str(uuid.uuid4())
    _a2a_listeners[listener_id] = q

    async def event_generator():
        try:
            # Snapshot of current tasks
            async with _a2a_lock:
                snapshot = [t.to_dict() for t in _a2a_tasks.values()]
            yield f"data: {json.dumps({'type': 'snapshot', 'tasks': snapshot})}\n\n"
            while True:
                payload = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {payload}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _a2a_listeners.pop(listener_id, None)

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
# Helpers
# ---------------------------------------------------------------------------

async def _auto_working(task_id: str, delay: float = 0.5):
    await asyncio.sleep(delay)
    try:
        await update_a2a_task_status(task_id, A2ATaskStatus.WORKING)
    except HTTPException:
        pass


def _parse_message(raw: dict) -> TaskMessage:
    return TaskMessage(
        role=raw.get("role", "user"),
        parts=raw.get("parts", [{"type": "text", "text": ""}]),
        metadata=raw.get("metadata", {}),
    )


# ---------------------------------------------------------------------------
# Pre-register dummy agents for testing
# ---------------------------------------------------------------------------

def _register_dummy_agents():
    dummy_agents = [
        AgentCard(
            name="planner",
            description="Strategic planning agent that decomposes goals into executable steps.",
            url="http://localhost:3004/a2a/v1/agents/planner",
            version="0.1.0",
            skills=[
                Skill("plan", "Plan Generation", "Break down complex tasks into sub-tasks", ["planning", "strategy"]),
                Skill("estimate", "Effort Estimation", "Estimate time and resource requirements", ["estimation"]),
            ],
            auth={"type": "none"},
        ),
        AgentCard(
            name="coder",
            description="Software engineering agent that writes, reviews, and debugs code.",
            url="http://localhost:3004/a2a/v1/agents/coder",
            version="0.1.0",
            skills=[
                Skill("code", "Code Generation", "Write code in multiple languages", ["coding", "python", "typescript"]),
                Skill("review", "Code Review", "Review code for bugs and style", ["review", "quality"]),
            ],
            auth={"type": "none"},
        ),
        AgentCard(
            name="verifier",
            description="Quality assurance agent that validates outputs against requirements.",
            url="http://localhost:3004/a2a/v1/agents/verifier",
            version="0.1.0",
            skills=[
                Skill("verify", "Output Verification", "Verify correctness of generated artifacts", ["qa", "verification"]),
                Skill("test", "Test Generation", "Generate unit and integration tests", ["testing"]),
            ],
            auth={"type": "none"},
        ),
    ]
    for card in dummy_agents:
        register_agent_card(card)


_register_dummy_agents()
