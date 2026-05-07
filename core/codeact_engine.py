"""NLLM.ING CodeAct Engine — Executable Python as Action Mechanism v1.0

Inspired by Manus.im's core architectural decision: the model writes executable
Python as its action mechanism instead of just describing what it would do.

This eliminates the "articulation gap" where LLMs produce detailed plans that
never actually get executed.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

WORKSPACE_ROOT = Path(os.environ.get("NLLM_WORKSPACE", "/tmp/nllm-workspace"))
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

# ── Pre-bundled library snippets for common patterns ───────────────────────────
BROWSER_SNIPPET = """
import asyncio, json, sys
from playwright.async_api import async_playwright

async def run_browser_task(url, actions):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        for action in actions:
            if action["type"] == "click":
                await page.click(action["selector"])
            elif action["type"] == "type":
                await page.fill(action["selector"], action["text"])
            elif action["type"] == "screenshot":
                await page.screenshot(path=action.get("path", "screenshot.png"))
            elif action["type"] == "extract":
                result = await page.eval_on_selector(action["selector"], "el => el.textContent")
                print(json.dumps({"extracted": result}))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_browser_task(sys.argv[1], json.loads(sys.argv[2])))
"""

HTTP_SNIPPET = """
import httpx, json, sys

async def fetch(url, method="GET", headers=None, data=None):
    async with httpx.AsyncClient() as client:
        resp = await client.request(method, url, headers=headers, json=data)
        return {"status": resp.status_code, "text": resp.text[:5000]}

result = asyncio.run(fetch(*sys.argv[1:]))
print(json.dumps(result))
"""


class CodeActSandbox:
    """Isolated workspace for a single task execution."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.workspace = WORKSPACE_ROOT / task_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.scripts_dir = self.workspace / "scripts"
        self.scripts_dir.mkdir(exist_ok=True)
        self.outputs_dir = self.workspace / "outputs"
        self.outputs_dir.mkdir(exist_ok=True)
        self.data_dir = self.workspace / "data"
        self.data_dir.mkdir(exist_ok=True)
        log.info("sandbox.created", task_id=task_id, path=str(self.workspace))

    def write_script(self, name: str, code: str) -> Path:
        path = self.scripts_dir / f"{name}.py"
        path.write_text(code)
        return path

    def read_file(self, name: str) -> str:
        path = self.workspace / name
        return path.read_text() if path.exists() else ""

    def list_files(self) -> list[dict]:
        files = []
        for p in sorted(self.workspace.rglob("*")):
            if p.is_file():
                files.append(
                    {
                        "path": str(p.relative_to(self.workspace)),
                        "size": p.stat().st_size,
                        "modified": p.stat().st_mtime,
                    }
                )
        return files

    def destroy(self):
        import shutil

        shutil.rmtree(self.workspace, ignore_errors=True)
        log.info("sandbox.destroyed", task_id=self.task_id)


class CodeActEngine:
    """Generates and executes Python scripts from task descriptions.

    Core Manus.im pattern: LLM writes executable Python, which IS the action.
    """

    SYSTEM_PROMPT = (
        "You are a Python code generator. Write complete, self-contained, executable Python scripts. "
        "No explanations outside the code. No markdown code fences. "
        "Use only the standard library + httpx (for HTTP) + playwright (for browser automation). "
        "Write all result files to the directory at os.environ.get('OUTPUT_DIR', './outputs'). "
        "Print a JSON summary as the VERY LAST line of stdout. Example final line: "
        '{"status": "success", "files_created": ["outputs/report.txt"], "summary": "..."}'
    )

    def __init__(
        self,
        local_url: str | None = None,
        openrouter_key: str | None = None,
    ):
        self.local_url = local_url or os.environ.get("LOCAL_LLM_URL", "http://localhost:9090")
        self.openrouter_url = "https://openrouter.ai/api/v1"
        self.openrouter_key = openrouter_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60)
        return self._client

    # ── Script generation ────────────────────────────────────────────────────

    async def generate_script(
        self,
        task: str,
        context: str = "",
        model: str | None = None,
    ) -> str:
        """Generate a Python script using the cheapest capable model."""
        # Default to free coder tier
        model = model or os.environ.get("CODER_MODEL", "qwen3-coder-480b:free")
        url = f"{self.openrouter_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
        }

        user_content = f"Task: {task}"
        if context:
            user_content += f"\n\nContext:\n{context}"
        user_content += (
            "\n\nWrite a complete Python script. "
            "The script must be fully self-contained with all imports. "
            "Write result files to the OUTPUT_DIR environment variable. "
            "Print a JSON summary object as the final stdout line."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        r = await self.client.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        code = data["choices"][0]["message"]["content"]

        # Strip markdown fences if present
        code = re.sub(r"^```python\n", "", code, flags=re.IGNORECASE)
        code = re.sub(r"^```\n", "", code)
        code = re.sub(r"\n```$", "", code)
        return code.strip()

    # ── Script execution ─────────────────────────────────────────────────────

    async def execute_script(
        self,
        sandbox: CodeActSandbox,
        code: str,
        timeout: int = 120,
    ) -> dict:
        """Execute script in isolated subprocess with resource guards."""
        script_path = sandbox.write_script("task", code)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(sandbox.workspace)
        env["OUTPUT_DIR"] = str(sandbox.outputs_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sandbox.workspace),
                env=env,
            )

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                stdout_b = b"" if not stdout_b else stdout_b
                return {
                    "status": "timeout",
                    "returncode": -1,
                    "stdout": stdout_b.decode(errors="replace"),
                    "stderr": f"Execution timed out after {timeout}s",
                    "files": sandbox.list_files(),
                }

            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")

            # Try to parse the final JSON summary line
            summary = {}
            lines = stdout.strip().splitlines()
            if lines:
                try:
                    summary = json.loads(lines[-1])
                except json.JSONDecodeError:
                    summary = {"raw_output": lines[-1][:500]}

            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "summary": summary,
                "files": sandbox.list_files(),
            }

        except Exception as e:
            log.error("codeact.execute_failed", error=str(e))
            return {
                "status": "crashed",
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "summary": {},
                "files": sandbox.list_files(),
            }

    # ── Self-healing loop ────────────────────────────────────────────────────

    async def run_with_healing(
        self,
        task: str,
        task_id: str,
        context: str = "",
        max_attempts: int = 3,
    ) -> dict:
        """Generate → Execute → Validate → Retry if failed."""
        sandbox = CodeActSandbox(task_id)
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            try:
                ctx = context
                if last_error:
                    ctx += f"\n\nPrior attempt (#{attempt - 1}) failed with:\n{last_error[:800]}"

                code = await self.generate_script(task, ctx)
                result = await self.execute_script(sandbox, code)
                result["attempt"] = attempt
                result["task_id"] = task_id

                if result["status"] == "ok":
                    log.info(
                        "codeact.success",
                        task_id=task_id,
                        attempts=attempt,
                        files=len(result["files"]),
                    )
                    return result

                last_error = result.get("stderr", "Unknown error")[:500]
                log.warning(
                    "codeact.retry",
                    task_id=task_id,
                    attempt=attempt,
                    error=last_error[:200],
                )

            except Exception as e:
                last_error = str(e)
                log.error(
                    "codeact.attempt_failed",
                    task_id=task_id,
                    attempt=attempt,
                    error=last_error,
                )

        log.error(
            "codeact.max_attempts_reached",
            task_id=task_id,
            attempts=max_attempts,
        )
        return {
            "status": "failed",
            "attempt": max_attempts,
            "task_id": task_id,
            "error": last_error,
            "files": sandbox.list_files(),
        }

    async def close(self):
        if self._client:
            await self._client.aclose()


# ── Convenience one-shot ───────────────────────────────────────────────────
async def run_codeact_task(
    task: str,
    task_id: str | None = None,
    context: str = "",
) -> dict:
    """One-shot: generate and execute a Python script for a task."""
    engine = CodeActEngine()
    task_id = task_id or f"codeact-{int(time.time() * 1000)}"
    try:
        result = await engine.run_with_healing(task, task_id, context)
    finally:
        await engine.close()
    return result


if __name__ == "__main__":

    async def _test():
        result = await run_codeact_task(
            "Calculate fibonacci(20) and write the result to outputs/fibonacci.txt. "
            "Also print a JSON summary with the sequence and the final value.",
            task_id="test-fib",
        )
        print(json.dumps(result, indent=2, default=str))

    asyncio.run(_test())
