#!/usr/bin/env python3
"""
Manus-style autonomous execution engine.

Integrates with Mission Control's task state machine and SSE streaming.
All LLM calls route through Bifrost (http://127.0.0.1:8000).
"""

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Playwright is optional at import time so we can syntax-check without it installed.
try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover
    async_playwright = None  # type: ignore


OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"

BIFROST_URL = "http://127.0.0.1:8000/v1/chat/completions"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_dir(task_id: str) -> Path:
    d = Path("/tmp/manus") / task_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _screenshot_dir(task_id: str) -> Path:
    d = _artifact_dir(task_id) / "screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _task_store() -> Dict[str, Any]:
    # Late import to avoid circular dependency at module-load time.
    import mission_control as mc

    return mc._tasks  # type: ignore[attr-defined]


def _broadcast(task_id: str, data: dict) -> None:
    import mission_control as mc

    mc._broadcast(task_id, data)  # type: ignore[attr-defined]


def _save_tasks() -> None:
    import mission_control as mc

    mc._save_tasks()  # type: ignore[attr-defined]


def _new_task_dict(*args, **kwargs) -> dict:
    import mission_control as mc

    return mc.new_task_dict(*args, **kwargs)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# LLM helpers via Bifrost
# ---------------------------------------------------------------------------

async def _chat(messages: List[dict], model: str = "qwen2.5:3b", max_tokens: int = 256, timeout: float = 120) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    url = OLLAMA_URL
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await asyncio.wait_for(
                client.post(url, json=payload, headers={"content-type": "application/json"}),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"LLM inference timed out after {timeout}s")
    if r.status_code >= 400:
        raise RuntimeError(f"Ollama error {r.status_code}: {r.text}")
    data = r.json()
    choices = data.get("choices") or [{}]
    msg = choices[0].get("message", {})
    return str(msg.get("content", "") or msg.get("reasoning", ""))


async def _generate_plan(task_description: str) -> List[dict]:
    system = (
        "You are an autonomous execution planner. "
        "Given a task, emit a JSON array of steps. Each step is an object with keys: "
        "tool (one of browser_navigate, browser_click, browser_type, browser_screenshot, "
        "terminal_execute, file_read, file_write, file_list, code_execute_python, spawn_subagent), "
        "input (object with args), and description (string). "
        "Return ONLY valid JSON—no markdown fences, no commentary."
    )
    user = f"Task: {task_description}\n\nPlan:"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    raw = await _chat(messages, max_tokens=256, timeout=120)
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
        plan = [{"tool": "terminal_execute", "input": {"command": "echo 'No plan generated'"}, "description": "Fallback terminal step"}]
    return plan


async def _decide_next_action(task_description: str, history: List[dict]) -> dict:
    system = (
        "You are an autonomous execution decider. Given a task and execution history, "
        "decide the next step. Return ONLY a JSON object with keys: "
        "action ('continue' or 'complete'), step (optional step object if continue), "
        "and summary (string). No markdown fences."
    )
    user = f"Task: {task_description}\n\nHistory: {json.dumps(history, default=str)}\n\nDecision:"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    raw = await _chat(messages, max_tokens=128, timeout=120)
    cleaned = raw.strip().strip("`").strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        decision = json.loads(cleaned)
    except Exception:
        decision = {"action": "complete", "summary": "Parsing failed; marking complete."}
    return decision


# ---------------------------------------------------------------------------
# ManusOrchestrator
# ---------------------------------------------------------------------------

class ManusOrchestrator:
    def __init__(self, task_id: str, llm_client: Optional[httpx.AsyncClient] = None):
        self.task_id = task_id
        self.plan: List[dict] = []
        self.current_step = 0
        self._browser_ctx: Optional[Any] = None
        self._page: Optional[Any] = None
        self._playwright: Optional[Any] = None
        self._terminal_proc: Optional[asyncio.subprocess.Process] = None
        self.artifacts: List[dict] = []
        self._history: List[dict] = []
        self._running = False
        self._llm_client = llm_client
        self._cancelled = False

    # -- lifecycle --

    async def _ensure_browser(self) -> Any:
        if self._page is not None:
            return self._page
        if async_playwright is None:
            raise RuntimeError("playwright is not installed")
        self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(headless=True)
        self._browser_ctx = await browser.new_context()
        self._page = await self._browser_ctx.new_page()
        return self._page

    async def _close_browser(self) -> None:
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None
        if self._browser_ctx:
            try:
                await self._browser_ctx.close()
            except Exception:
                pass
            self._browser_ctx = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def _kill_terminal(self) -> None:
        if self._terminal_proc and self._terminal_proc.returncode is None:
            try:
                self._terminal_proc.kill()
                await asyncio.wait_for(self._terminal_proc.wait(), timeout=2.0)
            except Exception:
                pass
        self._terminal_proc = None

    async def cleanup(self) -> None:
        await self._close_browser()
        await self._kill_terminal()

    # -- tool implementations --

    async def browser_navigate(self, url: str) -> str:
        page = await self._ensure_browser()
        await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        return title

    async def browser_click(self, selector: str) -> str:
        page = await self._ensure_browser()
        await page.click(selector)
        return f"Clicked {selector}"

    async def browser_type(self, selector: str, text: str) -> str:
        page = await self._ensure_browser()
        await page.fill(selector, text)
        return f"Typed into {selector}"

    async def browser_screenshot(self) -> str:
        page = await self._ensure_browser()
        sdir = _screenshot_dir(self.task_id)
        fname = f"{uuid.uuid4().hex}.png"
        path = sdir / fname
        await page.screenshot(path=str(path), full_page=True)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        url = page.url if page else ""
        self.artifacts.append({"type": "screenshot", "path": str(path), "url": url, "created_at": _iso_now()})
        _broadcast(self.task_id, {"type": "screenshot", "data": b64, "url": url})
        return str(path)

    async def terminal_execute(self, command: str, timeout: int = 30) -> str:
        # Use exec with /bin/sh -c to avoid shell-injection via IFS/PATH while
        # preserving pipes and redirections for LLM-generated commands.
        proc = await asyncio.create_subprocess_exec(
            "/bin/sh", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._terminal_proc = proc
        stdout_chunks: List[str] = []
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
            text = stdout.decode(errors="replace") if stdout else ""
            stdout_chunks.append(text)
            _broadcast(self.task_id, {"type": "terminal", "output": text})
            return text
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        finally:
            self._terminal_proc = None

    async def file_read(self, path: str) -> str:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        return p.read_text(errors="replace")

    async def file_write(self, path: str, content: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    async def file_list(self, path: str) -> List[str]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        return [str(x) for x in p.iterdir()]

    async def code_execute_python(self, code: str) -> str:
        # Write to temp file under artifact dir so outputs are collected.
        adir = _artifact_dir(self.task_id)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=str(adir), delete=False) as f:
            f.write(code)
            fpath = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, fpath,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
            out = stdout.decode(errors="replace") if stdout else ""
            err = stderr.decode(errors="replace") if stderr else ""
            result = (out + ("\n--- STDERR ---\n" + err if err else "")).strip()
            self.artifacts.append({"type": "code_output", "path": fpath, "output": result, "created_at": _iso_now()})
            return result
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise
        finally:
            try:
                os.unlink(fpath)
            except Exception:
                pass

    async def spawn_subagent(self, name: str, description: str) -> str:
        import mission_control as mc

        child = _new_task_dict(name, description, agent="manus-subagent", status=mc.TaskState.PLANNING, parent_id=self.task_id)
        child["status"] = mc.TaskState.RUNNING  # type: ignore[attr-defined]
        child["updated_at"] = _iso_now()
        store = _task_store()
        store[child["id"]] = child
        parent = store.get(self.task_id)
        if parent:
            parent["subtasks"].append(child["id"])
            parent["updated_at"] = _iso_now()
        _save_tasks()
        _broadcast(self.task_id, {"type": "spawn", "subtask_id": child["id"]})
        # Start a background Manus loop for the subagent as well.
        asyncio.create_task(_run_manus(child["id"]))
        return child["id"]

    # -- dispatch --

    async def run_tool(self, step: dict) -> dict:
        tool = step.get("tool", "")
        inp = step.get("input") or step.get("args") or {}
        if isinstance(inp, list) and len(inp) == 1 and isinstance(inp[0], dict):
            inp = inp[0]
        if not isinstance(inp, dict):
            inp = {}

        payload = {
            "type": "tool_call",
            "step": self.current_step,
            "tool": tool,
            "input": inp,
            "output": "",
            "status": "running",
        }
        _broadcast(self.task_id, payload)

        try:
            if tool == "browser_navigate":
                out = await self.browser_navigate(inp.get("url", ""))
            elif tool == "browser_click":
                out = await self.browser_click(inp.get("selector", ""))
            elif tool == "browser_type":
                out = await self.browser_type(inp.get("selector", ""), inp.get("text", ""))
            elif tool == "browser_screenshot":
                out = await self.browser_screenshot()
            elif tool == "terminal_execute":
                out = await self.terminal_execute(inp.get("command", ""), inp.get("timeout", 30))
            elif tool == "file_read":
                out = await self.file_read(inp.get("path", ""))
            elif tool == "file_write":
                out = await self.file_write(inp.get("path", ""), inp.get("content", ""))
            elif tool == "file_list":
                out = await self.file_list(inp.get("path", "."))
            elif tool == "code_execute_python":
                out = await self.code_execute_python(inp.get("code", ""))
            elif tool == "spawn_subagent":
                out = await self.spawn_subagent(inp.get("name", "subagent"), inp.get("description", ""))
            else:
                out = f"Unknown tool: {tool}"

            payload["output"] = out
            payload["status"] = "done"
            _broadcast(self.task_id, payload)
            return {"ok": True, "output": out}
        except Exception as exc:
            payload["output"] = str(exc)
            payload["status"] = "error"
            _broadcast(self.task_id, payload)
            return {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}

    # -- main loop --

    async def run(self, task_description: str) -> None:
        self._running = True
        self._cancelled = False
        store = _task_store()
        task = store.get(self.task_id)
        if task is None:
            raise RuntimeError("task not found")

        # Clean old artifacts for idempotency.
        adir = _artifact_dir(self.task_id)
        if adir.exists():
            shutil.rmtree(str(adir), ignore_errors=True)
        adir.mkdir(parents=True, exist_ok=True)

        try:
            # Generate plan from description or existing task plan.
            desc = task_description or task.get("description", "")
            plan = task.get("plan")
            if plan and isinstance(plan, list) and len(plan) > 0:
                self.plan = [
                    {
                        "tool": (s.get("agent") or "terminal_execute"),
                        "input": {"command": s.get("description", "")},
                        "description": s.get("description", ""),
                    }
                    for s in plan
                ]
            else:
                self.plan = await _generate_plan(desc)

            task["plan"] = self.plan
            _save_tasks()
            _broadcast(self.task_id, {"type": "plan", "plan": self.plan})

            for i, step in enumerate(self.plan):
                if self._cancelled:
                    break
                self.current_step = i
                result = await self.run_tool(step)
                self._history.append({"step": i, "tool": step.get("tool"), "result": result})

                # After each step, ask LLM whether to continue or finish.
                decision = await _decide_next_action(desc, self._history)
                if decision.get("action") == "complete":
                    break
                # If the LLM suggests an extra step, append it.
                extra = decision.get("step")
                if isinstance(extra, dict) and extra.get("tool"):
                    self.plan.append(extra)

            # Finalize task state.
            import mission_control as mc

            async with mc._lock:  # type: ignore[attr-defined]
                t = store.get(self.task_id)
                if t and not self._cancelled:
                    t["status"] = mc.TaskState.COMPLETED  # type: ignore[attr-defined]
                    t["progress"] = 100.0
                    t["updated_at"] = _iso_now()
                    t["artifacts"] = self.artifacts
                    _save_tasks()
                    _broadcast(self.task_id, {"status": "completed", "progress": 100.0})
        except Exception as exc:
            import mission_control as mc

            async with mc._lock:  # type: ignore[attr-defined]
                t = store.get(self.task_id)
                if t:
                    t["status"] = mc.TaskState.FAILED  # type: ignore[attr-defined]
                    t["error"] = str(exc)
                    t["updated_at"] = _iso_now()
                    _save_tasks()
                    _broadcast(self.task_id, {"status": "failed", "error": str(exc)})
            raise
        finally:
            await self.cleanup()
            self._running = False

    def cancel(self) -> None:
        self._cancelled = True


# ---------------------------------------------------------------------------
# Helpers used by mission_control
# ---------------------------------------------------------------------------

async def _run_manus(task_id: str) -> None:
    orchestrator = ManusOrchestrator(task_id)
    try:
        store = _task_store()
        task = store.get(task_id)
        if task is None:
            return
        desc = task.get("description", "")
        await orchestrator.run(desc)
    except Exception as exc:
        _broadcast(task_id, {"status": "failed", "error": str(exc)})
        import mission_control as mc

        async with mc._lock:  # type: ignore[attr-defined]
            t = store.get(task_id)
            if t:
                t["status"] = mc.TaskState.FAILED  # type: ignore[attr-defined]
                t["error"] = str(exc)
                t["updated_at"] = _iso_now()
                _save_tasks()


async def _manus_terminal_command(task_id: str, command: str, timeout: int = 30) -> str:
    orch = ManusOrchestrator(task_id)
    try:
        return await orch.terminal_execute(command, timeout=timeout)
    finally:
        await orch.cleanup()


def _list_screenshots(task_id: str) -> List[dict]:
    sdir = _screenshot_dir(task_id)
    results: List[dict] = []
    if not sdir.exists():
        return results
    for p in sorted(sdir.iterdir()):
        if p.suffix.lower() == ".png":
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            results.append({"path": str(p), "data": b64})
    return results


def _get_artifacts(task_id: str) -> List[dict]:
    adir = _artifact_dir(task_id)
    results: List[dict] = []
    if not adir.exists():
        return results
    for p in sorted(adir.rglob("*")):
        if p.is_file():
            results.append({"path": str(p.relative_to(adir)), "size": p.stat().st_size})
    return results
