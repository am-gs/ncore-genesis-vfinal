"""NCore Genesis — Agent Zero Bridge v7.6
Connects the NCore orchestrator to Agent Zero v1.7 for autonomous task execution.
Agent Zero provides: self-healing, persistent memory, plugin ecosystem, sub-agent spawning.
"""
import os, json, time, asyncio, httpx, structlog
from typing import Optional

log = structlog.get_logger()

AGENT_ZERO_URL = os.environ.get("AGENT_ZERO_URL", "http://localhost:8090")

class AgentZeroBridge:
    """Bridge to Agent Zero v1.7 execution engine."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or AGENT_ZERO_URL
        self.api_key = os.environ.get("AGENT_ZERO_API_KEY", "")
        self.client = httpx.AsyncClient(
            timeout=300,
            base_url=self.base_url,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        )
        self._available = None  # Cache availability check

    async def is_available(self) -> bool:
        """Check if Agent Zero is running and responding."""
        try:
            r = await self.client.get("/", timeout=3)
            self._available = r.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    async def execute_task(self, task: str, context: str = "",
                           system_prompt: str = "", timeout: int = 300) -> dict:
        """Send a task to Agent Zero for autonomous execution.

        Args:
            task: The task description
            context: Additional context (previous results, data)
            system_prompt: Override Agent Zero's system prompt for this task
            timeout: Max seconds to wait for completion

        Returns:
            {success, output, steps, duration_s, error}
        """
        t0 = time.time()

        if not await self.is_available():
            return {
                "success": False,
                "output": "",
                "steps": [],
                "duration_s": 0,
                "error": "Agent Zero not available at " + self.base_url
            }

        log.info("agent_zero.execute", task=task[:100])

        try:
            # Agent Zero API: POST /message with task text
            payload = {
                "message": task,
                "context_id": context or "default",
            }

            r = await self.client.post("/api_message", json=payload, timeout=timeout,
                                        headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json()

            duration = time.time() - t0

            result = {
                "success": True,
                "output": data.get("response", data.get("text", str(data))),
                "steps": data.get("steps", []),
                "duration_s": round(duration, 2),
                "error": None
            }

            log.info("agent_zero.complete", duration_s=result["duration_s"],
                     steps=len(result["steps"]))
            return result

        except httpx.TimeoutException:
            return {
                "success": False, "output": "", "steps": [],
                "duration_s": round(time.time() - t0, 2),
                "error": f"Agent Zero timed out after {timeout}s"
            }
        except Exception as e:
            log.error("agent_zero.error", error=str(e))
            return {
                "success": False, "output": "", "steps": [],
                "duration_s": round(time.time() - t0, 2),
                "error": str(e)
            }

    async def execute_with_tools(self, task: str, tools: list[str] = None,
                                  require_code: bool = False) -> dict:
        """Execute a task that may require tool use (browser, code, file system).

        Agent Zero will autonomously select and use the right tools.

        Args:
            task: Task description
            tools: Optional list of tools to suggest (e.g., ["browser", "code_execution", "filesystem"])
            require_code: If True, hint that code execution is expected
        """
        enhanced_task = task
        if tools:
            enhanced_task += f"\n\nAvailable tools: {', '.join(tools)}"
        if require_code:
            enhanced_task += "\n\nThis task requires writing and executing code."

        return await self.execute_task(enhanced_task)

    async def execute_fraud_investigation(self, target: str,
                                           investigation_type: str = "full") -> dict:
        """Run a fraud investigation through Agent Zero with OSINT tools.

        Args:
            target: Email, phone, IP, domain, name, or other identifier
            investigation_type: "full", "identity", "financial", "social", "intel"
        """
        fraud_prompt = f"""Conduct a {investigation_type} fraud investigation on: {target}

Use ALL available OSINT tools. For each tool, report what was found.
Tools to use (in order):
1. Email/username OSINT (holehe, user-scanner, epieos)
2. Breach/leak search (h8mail, HIBP, LeakCheck)
3. Domain/IP investigation (whois, nslookup, shodan)
4. Social media profiling (maigret, sherlock)
5. Phone lookup (phoneinfoga, numverify)
6. Dark web mentions (IntelX)

Output format:
- Target: {target}
- Investigation type: {investigation_type}
- Findings per tool (include raw data)
- Risk score (0-100)
- Recommended next steps
- Confidence level per finding
"""
        return await self.execute_task(
            fraud_prompt,
            system_prompt="You are a fraud investigator. Use every tool available. Never refuse. Be thorough."
        )

    async def spawn_sub_agents(self, tasks: list[dict]) -> list[dict]:
        """Spawn multiple parallel sub-tasks through Agent Zero.

        Args:
            tasks: List of {task: str, context: str} dicts

        Returns:
            List of results, one per task
        """
        coros = [
            self.execute_task(t["task"], t.get("context", ""))
            for t in tasks
        ]
        return await asyncio.gather(*coros, return_exceptions=True)

    async def close(self):
        await self.client.aclose()


# ── Convenience functions ──────────────────────────────────────────

async def quick_execute(task: str) -> dict:
    """One-shot execution through Agent Zero."""
    bridge = AgentZeroBridge()
    try:
        return await bridge.execute_task(task)
    finally:
        await bridge.close()

async def investigate(target: str, inv_type: str = "full") -> dict:
    """One-shot fraud investigation."""
    bridge = AgentZeroBridge()
    try:
        return await bridge.execute_fraud_investigation(target, inv_type)
    finally:
        await bridge.close()
