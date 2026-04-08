"""NCore Genesis — FastAPI + LangGraph Orchestrator v3.3

Fixes (v3.3 — April 7 2026):
  - Dashboard served from FastAPI on port 8080 (eliminates CORS/proxy issues)
  - CORS middleware for external clients
  - WebSocket /ws endpoint for real-time dashboard updates
  - Ollama provider support in node_execute
  - Prompt enhancer wired into LangGraph pipeline (route → enhance → discover → execute)
  - Agent Zero delegation for complex opus-tier tasks

Prior fixes retained (v3.2):
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
import asyncio, os, re, time, pathlib, uuid, shutil, base64
import json as json_lib
from contextlib import asynccontextmanager
from typing import TypedDict, Optional, Annotated

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import httpx
import structlog
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
)
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

import litellm
from litellm import acompletion
from litellm.caching.caching import Cache

from router import NCoreMasterRouter
from moe_router import AthenaMoERouter, NCoreModelRegistry  # H1: wired in
from comfyui_bridge import ComfyUIBridge
from gpu_manager import GPUManager
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
    # LiteLLM: semantic cache + fallbacks + cost tracking
    redis_url = f"redis+unix://{os.environ.get('NCORE_REDIS_UDS', '/var/run/redis/redis-server.sock')}"
    try:
        litellm.cache = Cache(
            type="redis",
            host="localhost",
            port=6379,
            ttl=3600,
        )
        litellm.success_callback = ["cache_hit"]
        litellm.set_verbose = False
        log.info("ncore.litellm_cache", status="ready")
    except Exception as e:
        log.warning("ncore.litellm_cache_skip", error=str(e))

    # H1: connect MoE router cache
    await MOE_ROUTER.connect_cache()
    log.info("ncore.startup", msg="HTTP client + MoE cache ready")
    yield
    await app.state.http.aclose()
    await MOE_ROUTER.disconnect_cache()
    log.info("ncore.shutdown")

app = FastAPI(title="NCore Genesis", version="3.3", lifespan=lifespan)

# ── CORS middleware (FIX 1) ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = pathlib.Path(__file__).resolve().parent.parent / "dashboard"

UPLOAD_DIR = pathlib.Path("/tmp/ncore_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MASTER_ROUTER = NCoreMasterRouter()
MOE_ROUTER    = AthenaMoERouter(NCoreModelRegistry())  # H1: must pass registry
try:
    GPU_MANAGER = GPUManager()
    COMFYUI = ComfyUIBridge(gpu_manager=GPU_MANAGER)
except Exception as e:
    log.warning("gpu_init_deferred", error=str(e))
    GPU_MANAGER = None
    COMFYUI = None

# ── State ─────────────────────────────────────────────────────────────────────
def _last_value(left, right):
    """Reducer: last writer wins. Allows parallel nodes to write the same key safely."""
    return right if right is not None else left

class AgentState(TypedDict):
    task:      Annotated[str, _last_value]
    turns:     Annotated[int, _last_value]
    route:     Annotated[dict, _last_value]
    output:    Annotated[str, _last_value]
    cost_usd:  Annotated[float, _last_value]
    latency_s: Annotated[float, _last_value]

# ── tenacity-wrapped LLM call (C1 + M1) ──────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(structlog.stdlib.get_logger(), 30),
)
async def _call_llm(client: httpx.AsyncClient, endpoint: str, headers: dict, payload: dict) -> str:
    """LLM call via LiteLLM — gets caching, fallbacks, cost tracking for free."""
    model = payload.get("model", "")
    messages = payload.get("messages", [])

    try:
        # Use LiteLLM for OpenRouter models — gives us caching + fallbacks
        response = await acompletion(
            model=model,
            messages=messages,
            temperature=payload.get("temperature", 0.4),
            max_tokens=payload.get("max_tokens", 8192),
            api_key=headers.get("Authorization", "").replace("Bearer ", ""),
            api_base=endpoint,
            stream=False,
            caching=True,
        )
        return response.choices[0].message.content
    except Exception:
        # Fallback to direct httpx call if LiteLLM fails
        r = await client.post(f"{endpoint}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

# ── WebSocket support (FIX 2) ─────────────────────────────────────────────────
ws_clients: list[WebSocket] = []

async def broadcast_ws(event: dict):
    """Broadcast an event to all connected dashboard clients."""
    message = json_lib.dumps(event)
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)

# ── LangGraph nodes ──────────────────────────────────────────────────────────
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
    await broadcast_ws({"type": "route", "data": decision})
    return {**state, "route": decision}


async def node_enhance(state: AgentState) -> AgentState:
    """Heuristic prompt enhancement before LLM execution (FIX 4)."""
    d = state["route"]
    # Skip enhancement for fast/simple/local/media tiers — only enhance complex cloud tasks
    if d["tier"] in ("fast", "image", "video", "free_coder", "investigation", "uncensored_local", "uncensored"):
        return state

    try:
        r = await app.state.http.post(
            "http://localhost:8081/enhance",
            json={"prompt": state["task"], "context": "", "task_id": ""},
            timeout=10.0,
        )
        if r.status_code == 200:
            enhanced = r.json()
            enhanced_prompt = enhanced.get("enhanced", state["task"])
            log.info("ncore.enhance", domains=enhanced.get("domains"),
                     critic_score=enhanced.get("critic_score", -1))
            await broadcast_ws({"type": "enhance", "data": {"domains": enhanced.get("domains"), "critic_score": enhanced.get("critic_score", -1)}})
            return {**state, "task": enhanced_prompt}
    except Exception as e:
        log.warning("ncore.enhance_skip", error=str(e))

    return state  # Fall through if enhancer is down


async def node_discover(state: AgentState) -> AgentState:
    """Search for existing tools/skills before executing.
    Checks ClawHub (44K+ skills), PyPI, and GitHub.
    Skips for trivial/fast tasks to avoid latency.
    """
    d = state["route"]
    # Skip discovery for fast/simple/local tiers — only discover for complex cloud tasks
    if d["tier"] in ("fast", "free_coder", "investigation", "uncensored_local", "uncensored", "image", "video"):
        return state

    try:
        from skill_discovery import discover_and_equip
        installed = await discover_and_equip(state["task"])
        if installed:
            tools_msg = ", ".join(t.get("name", "unknown") for t in installed)
            log.info("ncore.discover", installed=tools_msg, count=len(installed))
            await broadcast_ws({
                "type": "discover",
                "data": {
                    "tools_found": len(installed),
                    "tools": [t.get("name") for t in installed]
                }
            })
    except Exception as e:
        log.warning("ncore.discover_skip", error=str(e))

    return state


async def node_execute(state: AgentState) -> AgentState:   # C2: now truly async
    d  = state["route"]
    t0 = time.time()

    # ── POD tasks ─────────────────────────────────────────────────────────────
    if d.get("requires_pod"):
        spec = d.get("pod_spec", {})
        pod_type = spec.get("type", "image")

        if COMFYUI is None:
            output = "❌ GPU manager not initialized (check VAST_API_KEY)"
            return {**state, "output": output, "cost_usd": 0, "latency_s": time.time() - t0}

        try:
            # Extract image paths if attached
            image_paths = []
            img_match = re.search(r'\[ATTACHED_IMAGES: ([^\]]+)\]', state["task"])
            if img_match:
                image_paths = [p.strip() for p in img_match.group(1).split(",")]
                # Clean task text (remove the metadata tag)
                clean_task = re.sub(r'\n\n\[ATTACHED_IMAGES:[^\]]+\]', '', state["task"])
            else:
                clean_task = state["task"]

            # Decompose the task
            from task_decomposer import TaskDecomposer
            decomposer = TaskDecomposer()
            plan = await decomposer.analyze(clean_task, image_paths)
            await decomposer.close()

            await broadcast_ws({"type": "plan", "data": plan})

            # Check if blocked (missing images, etc.)
            if plan.get("blocked"):
                output = f"⚠️ {plan['block_reason']}\n\n"
                output += f"Task type detected: {plan['task_type']}\n"
                output += f"Expected faces: {plan['expected_faces']}\n"
                output += f"Images provided: {plan['faces_provided']}\n"
                if plan.get("image_issues"):
                    output += "\nImage issues:\n" + "\n".join(f"  - {issue}" for issue in plan["image_issues"])
                output += f"\n\nPlease re-submit via POST /run/media with the required images attached."
                return {**state, "output": output, "cost_usd": 0, "latency_s": time.time() - t0}

            # Report image issues as warnings (non-blocking)
            warnings = ""
            if plan.get("image_issues"):
                warnings = "\n⚠️ Image warnings:\n" + "\n".join(f"  - {issue}" for issue in plan["image_issues"])

            # Execute based on task type
            if plan["task_type"] == "face_swap_video":
                result = await COMFYUI.generate_faceswap_video(
                    prompt=clean_task,
                    face_images=image_paths,
                    width=spec.get("width", 832),
                    height=spec.get("height", 480),
                    frames=plan["frames"],
                    steps=spec.get("steps", 30),
                    hd=plan["needs_hd"],
                    task_id=f"fsvid_{int(time.time())}",
                )
                output = f"✅ Face-swap video generated in {result['duration_s']:.0f}s\n"
                output += f"Stages: {' → '.join(result['stages'])}\n"
                output += f"Faces applied: {result['faces_applied']}\n"
                output += f"GPU: {result['gpu_profile']} | Cost: ${result['cost_usd']:.4f}\n"
                output += f"📁 {result['output_path']}"
                output += warnings
                cost = result["cost_usd"]
            elif plan["task_type"] == "image_to_video" and image_paths:
                result = await COMFYUI.generate_video(
                    prompt=clean_task,
                    width=spec.get("width", 832),
                    height=spec.get("height", 480),
                    frames=plan["frames"],
                    steps=spec.get("steps", 30),
                    hd=plan["needs_hd"],
                    task_id=f"i2v_{int(time.time())}",
                )
                output = f"✅ I2V video generated in {result['duration_s']:.0f}s | Cost: ${result['cost_usd']:.4f}\n📁 {result['output_path']}"
                output += warnings
                cost = result["cost_usd"]
            elif pod_type == "video":
                result = await COMFYUI.generate_video(
                    prompt=clean_task,
                    negative=spec.get("negative", ""),
                    width=spec.get("width", 832),
                    height=spec.get("height", 480),
                    frames=plan.get("frames", spec.get("frames", 81)),
                    steps=spec.get("steps", 30),
                    hd=plan.get("needs_hd", False),
                    task_id=f"video_{int(time.time())}",
                )
                output = f"✅ Video generated in {result['duration_s']:.0f}s | GPU: {result['gpu_profile']} | Cost: ${result['cost_usd']:.4f}\n📁 {result['output_path']}"
                output += warnings
                cost = result["cost_usd"]
            else:
                result = await COMFYUI.generate_image(
                    prompt=clean_task,
                    negative=spec.get("negative", ""),
                    width=spec.get("width", 1024),
                    height=spec.get("height", 1024),
                    steps=spec.get("steps", 20),
                    task_id=f"img_{int(time.time())}",
                )
                output = f"✅ Image generated in {result['duration_s']:.0f}s | GPU: {result['gpu_profile']} | Cost: ${result['cost_usd']:.4f}\n📁 {result['output_path']}"
                output += warnings
                cost = result["cost_usd"]

            latency = time.time() - t0
            update_cost(d["tier"], cost)
            await broadcast_ws({"type": "gpu_complete", "data": {"pod_type": pod_type, "task_type": plan["task_type"], "duration_s": result["duration_s"], "cost_usd": cost, "gpu_profile": result["gpu_profile"]}})
            return {**state, "output": output, "cost_usd": cost, "latency_s": latency}

        except Exception as e:
            log.error("ncore.gpu_error", error=str(e), pod_type=pod_type)
            output = f"❌ {pod_type.title()} generation failed: {e}"
            return {**state, "output": output, "cost_usd": 0, "latency_s": time.time() - t0}

    # ── INVESTIGATION tasks — fast path via OpenRouter, local Ollama fallback ───
    if d["tier"] == "investigation":
        # v7.6.3: Route investigation to OpenRouter FREE_REASONING (DeepSeek R1 free)
        # instead of slow local Ollama. Only fall back to local if OpenRouter fails.
        investigation_model = os.environ.get("FREE_REASONING", "deepseek/deepseek-r1:free")
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        log.info("ncore.investigation_openrouter", model=investigation_model)
        try:
            output = await _call_llm(
                app.state.http,
                "https://openrouter.ai/api/v1",
                {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://ncore.internal", "X-Title": "NCore Genesis"},
                {"model": investigation_model, "messages": [{"role": "user", "content": state["task"]}],
                 "temperature": 0.3, "max_tokens": 8192},
            )
            latency = time.time() - t0
            cost = 0.0
            update_cost(d["tier"], cost)
            d["model"] = investigation_model
            d["provider"] = "openrouter"
            log.info("ncore.execute", tier="investigation", model=investigation_model, latency_s=round(latency, 3))
            await broadcast_ws({"type": "result", "data": {"tier": d["tier"], "model": investigation_model, "latency_s": round(latency, 3), "cost_usd": cost, "output_preview": output[:200] if isinstance(output, str) else ""}})
            return {**state, "output": output, "cost_usd": cost, "latency_s": latency, "route": d}
        except Exception as e:
            log.warning("ncore.investigation_openrouter_failed", error=str(e), fallback="ollama")

        # OpenRouter failed — fall back to local Ollama (Qwen 2.5 3B for speed)
        d["provider"] = "ollama"
        d["model"] = os.environ.get("LOCAL_FAST_MODEL", "qwen2.5:3b")
        d["endpoint"] = "http://localhost:11434"
        d["estimated_cost_usd"] = 0.0
        log.info("ncore.investigation_fallback_local", model=d["model"])

    # ── OLLAMA tasks (local uncensored) (FIX 3) ──────────────────────────────
    if d["provider"] == "ollama":
        try:
            ollama_payload = {
                "model": d["model"],
                "messages": [{"role": "user", "content": state["task"]}],
                "stream": False,
                "options": {
                    "num_predict": 2048,   # Cap tokens to prevent ARM CPU generation spirals
                    "num_ctx": 4096,       # Context window
                    "num_thread": 4,       # Match 4 ARM OCPUs
                },
            }
            r = await app.state.http.post(
                f"{d['endpoint']}/api/chat",
                json=ollama_payload,
                timeout=300.0  # Ollama on ARM CPU needs longer for first load + generation
            )
            r.raise_for_status()
            output = r.json().get("message", {}).get("content", "")
        except Exception as e:
            log.error("ncore.ollama_error", error=str(e), model=d["model"])
            output = f"[Ollama error] {e}"
        latency = time.time() - t0
        cost = 0.0
        update_cost(d["tier"], cost)
        log.info("ncore.execute", tier=d["tier"], latency_s=round(latency, 3), cost_usd=cost)
        await broadcast_ws({"type": "result", "data": {"tier": d["tier"], "model": d["model"], "latency_s": round(latency, 3), "cost_usd": cost, "output_preview": output[:200]}})
        return {**state, "output": output, "cost_usd": cost, "latency_s": latency}

    # ── AGENT ZERO delegation (complex multi-step tasks) (FIX 5) ─────────────
    if d["tier"] in ("opus", "worker", "free_reasoning") and os.environ.get("AGENT_ZERO_URL"):
        try:
            from agent_zero_bridge import AgentZeroBridge
            az = AgentZeroBridge()
            if await az.is_available():
                result = await az.execute_task(state["task"])
                if result["success"]:
                    latency = time.time() - t0
                    update_cost(d["tier"], d["estimated_cost_usd"])
                    await broadcast_ws({"type": "agent_zero", "data": {"steps": len(result["steps"]), "duration_s": result["duration_s"]}})
                    return {**state, "output": result["output"], "cost_usd": d["estimated_cost_usd"], "latency_s": latency}
            await az.close()
        except Exception as e:
            log.warning("ncore.agent_zero_fallback", error=str(e))
        # Fall through to regular LLM if Agent Zero fails

    # ── LLM tasks — with tier-level fallback cascade ──────────────────────────
    # Fallback order: primary model → FALLBACK_FREE → FAST_MODEL → WORKER_MODEL
    FALLBACK_CHAIN = [
        {"model": d["model"], "endpoint": d["endpoint"], "provider": d["provider"]},
        {"model": os.environ.get("FAST_MODEL", "openai/gpt-oss-20b:free"),
         "endpoint": "https://openrouter.ai/api/v1", "provider": "openrouter"},
        {"model": os.environ.get("FALLBACK_FREE", "google/gemini-2.0-flash-lite-001"),
         "endpoint": "https://openrouter.ai/api/v1", "provider": "openrouter"},
        {"model": os.environ.get("WORKER_MODEL", "deepseek/deepseek-chat"),
         "endpoint": "https://openrouter.ai/api/v1", "provider": "openrouter"},
    ]
    # Deduplicate (if primary is already a fallback model)
    seen = set()
    chain = []
    for fb in FALLBACK_CHAIN:
        if fb["model"] not in seen:
            seen.add(fb["model"])
            chain.append(fb)

    output = None
    used_model = d["model"]
    for i, fb in enumerate(chain):
        api_key = (
            os.environ.get("OPENROUTER_API_KEY", "")
            if fb["provider"] == "openrouter"
            else os.environ.get("VAST_API_KEY", "")
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer":  "https://ncore.internal",
            "X-Title":       "NCore Genesis",
        }
        payload = {
            "model":       fb["model"],
            "messages":    [{"role": "user", "content": state["task"]}],
            "temperature": 0.1 if d["tier"] in ("nano", "coder") else 0.4,
            "max_tokens":  8192,
        }
        try:
            output = await _call_llm(app.state.http, fb["endpoint"], headers, payload)
            used_model = fb["model"]
            if i > 0:
                log.info("ncore.fallback_success", original=d["model"], fallback=fb["model"], attempt=i)
            break
        except Exception as e:
            log.warning("ncore.llm_attempt_failed", model=fb["model"], attempt=i, error=str(e))
            if i == len(chain) - 1:
                output = f"[LLM error after all fallbacks] {e}"

    latency = time.time() - t0
    cost    = d["estimated_cost_usd"]
    update_cost(d["tier"], cost)
    log.info("ncore.execute", tier=d["tier"], model=used_model, latency_s=round(latency, 3), cost_usd=cost)
    await broadcast_ws({"type": "result", "data": {"tier": d["tier"], "model": used_model, "latency_s": round(latency, 3), "cost_usd": cost, "output_preview": output[:200] if isinstance(output, str) else ""}})
    return {**state, "output": output, "cost_usd": cost, "latency_s": latency}


# ── Graph (async nodes → use ainvoke) ─────────────────────────────────────────
_builder = StateGraph(AgentState)
_builder.add_node("route",    node_route)     # async
_builder.add_node("enhance",  node_enhance)   # async — prompt enhancement
_builder.add_node("discover", node_discover)  # async — search 44K+ ClawHub skills
_builder.add_node("execute",  node_execute)   # async
_builder.set_entry_point("route")
# Parallel fan-out: enhance + discover run simultaneously (LangGraph superstep)
# Safe: AgentState uses Annotated[str, _last_value] reducers on all keys
_builder.add_edge("route", "enhance")
_builder.add_edge("route", "discover")
_builder.add_edge("enhance", "execute")
_builder.add_edge("discover", "execute")
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

@app.post("/run/stream")
async def run_stream(req: RunRequest):
    """Streaming version of /run — tokens arrive in real-time via SSE."""
    REQUEST_COUNTER.inc()

    # Route first
    with ROUTING_LATENCY.time():
        decision = MASTER_ROUTER.route(req.task, req.turns)

    ROUTE_TIER_COUNTER.labels(tier=decision["tier"]).inc()
    await broadcast_ws({"type": "route", "data": decision})
    log.info("ncore.route", tier=decision["tier"], model=decision["model"])

    # Handle non-LLM tasks (pods, ollama) via regular /run
    if decision.get("requires_pod") or decision.get("provider") == "ollama":
        # Delegate to non-streaming path
        init = {"task": req.task, "turns": req.turns, "route": {}, "output": "", "cost_usd": 0.0, "latency_s": 0.0}
        final = await app_graph.ainvoke(init)
        async def single_chunk():
            yield f"data: {json_lib.dumps({'content': final['output'], 'done': True, 'route': final['route']})}\n\n"
        return StreamingResponse(single_chunk(), media_type="text/event-stream")

    # Streaming LLM call
    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    async def generate():
        t0 = time.time()
        full_response = ""
        try:
            response = await acompletion(
                model=decision["model"],
                messages=[{"role": "user", "content": req.task}],
                temperature=0.4,
                max_tokens=8192,
                api_key=api_key,
                api_base=decision["endpoint"],
                stream=True,
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield f"data: {json_lib.dumps({'content': token, 'done': False})}\n\n"

            latency = time.time() - t0
            cost = decision["estimated_cost_usd"]
            update_cost(decision["tier"], cost)
            yield f"data: {json_lib.dumps({'content': '', 'done': True, 'route': decision, 'cost_usd': cost, 'latency_s': round(latency, 3)})}\n\n"

        except Exception as e:
            yield f"data: {json_lib.dumps({'content': f'[Error] {e}', 'done': True, 'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/run/media")
async def run_media(
    task: str = Form(...),
    turns: int = Form(0),
    images: list[UploadFile] = File(default=[]),
):
    """Run a task with optional image attachments."""
    # Save uploaded images
    image_paths = []
    for img in images:
        ext = img.filename.split(".")[-1] if img.filename else "jpg"
        path = UPLOAD_DIR / f"{uuid.uuid4().hex}.{ext}"
        with open(path, "wb") as f:
            shutil.copyfileobj(img.file, f)
        image_paths.append(str(path))
        log.info("ncore.upload", filename=img.filename, path=str(path), size=path.stat().st_size)

    # Build enhanced state with image references
    init: AgentState = {
        "task": task,
        "turns": turns,
        "route": {},
        "output": "",
        "cost_usd": 0.0,
        "latency_s": 0.0,
    }

    # Inject image paths into task context for downstream nodes
    if image_paths:
        init["task"] = task + f"\n\n[ATTACHED_IMAGES: {','.join(image_paths)}]"

    with REQUEST_LATENCY.time():
        REQUEST_COUNTER.inc()
        final = await app_graph.ainvoke(init)

    return {
        "output": final["output"],
        "route": final["route"],
        "cost_usd": final["cost_usd"],
        "latency_s": final["latency_s"],
        "images_received": len(image_paths),
    }

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.3"}

@app.get("/ready")
async def readiness_check():
    """Deep health check — verifies every system component."""
    checks = {}
    client = app.state.http

    # 1. Gateway itself
    checks["gateway"] = {"status": "ok", "version": "3.3"}

    # 2. Redis
    try:
        import redis as redis_lib
        uds = os.environ.get("NCORE_REDIS_UDS", "/var/run/redis/redis-server.sock")
        r = redis_lib.Redis(unix_socket_path=uds)
        r.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}

    # 3. Ollama
    try:
        resp = await client.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        checks["ollama"] = {"status": "ok", "models": models}
    except Exception as e:
        checks["ollama"] = {"status": "error", "error": str(e)}

    # 4. OpenRouter
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        checks["openrouter"] = {"status": "ok" if resp.status_code == 200 else "error"}
    except Exception as e:
        checks["openrouter"] = {"status": "error", "error": str(e)}

    # 5. Agent Zero (if running)
    try:
        resp = await client.get("http://localhost:8090/", timeout=3)
        checks["agent_zero"] = {"status": "ok" if resp.status_code == 200 else "down"}
    except Exception:
        checks["agent_zero"] = {"status": "not_deployed"}

    # 6. Vast.ai API
    vast_key = os.environ.get("VAST_API_KEY", "")
    if vast_key:
        try:
            resp = await client.get(
                "https://console.vast.ai/api/v0/users/current/",
                headers={"Authorization": f"Bearer {vast_key}"},
                timeout=5,
                follow_redirects=True,
            )
            checks["vastai"] = {"status": "ok" if resp.status_code == 200 else "error"}
        except Exception as e:
            checks["vastai"] = {"status": "error", "error": str(e)}
    else:
        checks["vastai"] = {"status": "no_key"}

    # 7. Prompt Enhancer
    try:
        resp = await client.get("http://localhost:8081/", timeout=3)
        checks["prompt_enhancer"] = {"status": "ok"}
    except Exception:
        checks["prompt_enhancer"] = {"status": "not_running"}

    # Overall
    all_ok = all(c.get("status") == "ok" for c in checks.values()
                 if c.get("status") not in ("not_deployed", "not_running", "no_key"))

    return {
        "ready": all_ok,
        "checks": checks,
        "timestamp": time.time(),
    }

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ── WebSocket endpoint (FIX 2) ───────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
            # Echo back acknowledgment
            await websocket.send_text(json_lib.dumps({"type": "ack", "data": data}))
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
    except Exception:
        if websocket in ws_clients:
            ws_clients.remove(websocket)

# ── Dashboard static serving (FIX 1) ─────────────────────────────────────────
if DASHBOARD_DIR.exists():
    @app.get("/dashboard")
    @app.get("/dashboard/{path:path}")
    async def dashboard(path: str = ""):
        return FileResponse(DASHBOARD_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator:app", host="0.0.0.0", port=8080, reload=False)
