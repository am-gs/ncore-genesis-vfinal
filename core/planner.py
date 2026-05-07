"""NLLM.ING Persistent Planning Engine — File-Based Markdown Plans v1.0

Manus.im pattern: each task gets a persistent markdown plan that tracks
status, steps, outputs, and learns across iterations.
"""
from __future__ import annotations

import json
import os
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

WORKSPACE_ROOT = Path(os.environ.get("NLLM_WORKSPACE", "/tmp/nllm-workspace"))


class TaskPlanner:
    """Creates and manages persistent markdown plans for tasks."""

    def __init__(self, root: Path | None = None):
        self.root = root or WORKSPACE_ROOT

    def _plan_path(self, task_id: str) -> Path:
        ws = self.root / task_id
        ws.mkdir(parents=True, exist_ok=True)
        return ws / "plan.md"

    def create_plan(
        self,
        task_id: str,
        task_description: str,
        agents: list[dict],
    ) -> Path:
        """Create a new markdown plan for a task."""
        now = datetime.now(timezone.utc).isoformat()
        plan_path = self._plan_path(task_id)

        lines = [
            f"# Task: {task_description}",
            "",
            f"- **Status**: pending",
            f"- **Created**: {now}",
            f"- **Last Updated**: {now}",
            f"- **Task ID**: {task_id}",
            "",
            "## Execution Plan",
            "",
        ]

        for i, agent in enumerate(agents, 1):
            role = agent.get("role", f"Agent {i}")
            prompt = agent.get("prompt", "")
            tool = agent.get("tool", "llm")
            mode = agent.get("execution_mode", "llm")
            uncensored = "yes" if agent.get("uncensored") else "no"
            deps = agent.get("depends_on", [])
            deps_str = f" (depends on: {', '.join(deps)})" if deps else ""

            lines.extend(
                [
                    f"### Step {i}: {role}{deps_str}",
                    "",
                    f"- **Status**: pending",
                    f"- **Tool**: {tool}",
                    f"- **Mode**: {mode}",
                    f"- **Uncensored**: {uncensored}",
                    f"- **Agent Prompt**: {prompt[:200]}{'...' if len(prompt) > 200 else ''}",
                    "- **Output**: _(not yet executed)_",
                    "",
                ]
            )

        plan_path.write_text("\n".join(lines))
        log.info("planner.created", task_id=task_id, agents=len(agents))
        return plan_path

    def update_step(
        self,
        task_id: str,
        step_num: int,
        status: str,
        output: str = "",
        metadata: dict | None = None,
    ) -> bool:
        """Update a step's status and output in the plan."""
        plan_path = self._plan_path(task_id)
        if not plan_path.exists():
            return False

        content = plan_path.read_text()
        now = datetime.now(timezone.utc).isoformat()

        # Update the top-level status if all steps are done
        overall_status = self._compute_overall_status(content, step_num, status)

        # Replace the step block
        old_block = self._extract_step_block(content, step_num)
        if old_block is None:
            log.warning("planner.step_not_found", task_id=task_id, step=step_num)
            return False

        new_block = old_block.replace(
            f"- **Status**: pending", f"- **Status**: {status}"
        ).replace(
            f"- **Status**: running", f"- **Status**: {status}"
        )

        # Update output line
        output_line = f"- **Output**: {output[:500]}{'...' if len(output) > 500 else ''}"
        if "- **Output**: _(not yet executed)_" in new_block:
            new_block = new_block.replace(
                "- **Output**: _(not yet executed)_", output_line
            )
        elif "- **Output**: " in new_block:
            # Replace existing output
            new_block = re.sub(r"- \*\*Output\*\*: .*", output_line, new_block, count=1)
        else:
            new_block += f"\n{output_line}"

        # Add metadata if provided
        if metadata:
            meta_str = json.dumps(metadata, default=str)
            new_block += f"\n- **Metadata**: {meta_str[:300]}"

        content = content.replace(old_block, new_block)
        content = re.sub(
            r"- \*\*Last Updated\*\*: .*",
            f"- **Last Updated**: {now}",
            content,
        )
        content = re.sub(
            r"- \*\*Status\*\*: .*",
            f"- **Status**: {overall_status}",
            content,
            count=1,
        )

        plan_path.write_text(content)
        log.info("planner.updated", task_id=task_id, step=step_num, status=status)
        return True

    def get_plan(self, task_id: str) -> dict:
        """Parse a plan.md into a structured dict."""
        plan_path = self._plan_path(task_id)
        if not plan_path.exists():
            return {}

        content = plan_path.read_text()

        # Extract top-level metadata
        status_match = re.search(r"- \*\*Status\*\*: (\w+)", content)
        created_match = re.search(r"- \*\*Created\*\*: ([\d\-T:.Z+]+)", content)

        # Extract steps
        steps = []
        step_pattern = re.compile(r"### Step (\d+): (.+?)\n(.*?)(?=### Step \d+:|\Z)", re.DOTALL)
        for m in step_pattern.finditer(content):
            step_num = int(m.group(1))
            role = m.group(2).strip()
            block = m.group(3)

            step_status = re.search(r"- \*\*Status\*\*: (\w+)", block)
            step_tool = re.search(r"- \*\*Tool\*\*: (\w+)", block)
            step_mode = re.search(r"- \*\*Mode\*\*: (\w+)", block)
            step_output = re.search(r"- \*\*Output\*\*: (.*)", block)

            steps.append(
                {
                    "step": step_num,
                    "role": role,
                    "status": step_status.group(1) if step_status else "unknown",
                    "tool": step_tool.group(1) if step_tool else "llm",
                    "mode": step_mode.group(1) if step_mode else "llm",
                    "output": step_output.group(1) if step_output else "",
                }
            )

        return {
            "task_id": task_id,
            "status": status_match.group(1) if status_match else "unknown",
            "created": created_match.group(1) if created_match else "",
            "steps": steps,
            "raw": content,
        }

    def mark_complete(self, task_id: str, summary: str = ""):
        """Mark the entire task as completed."""
        plan_path = self._plan_path(task_id)
        if not plan_path.exists():
            return

        content = plan_path.read_text()
        now = datetime.now(timezone.utc).isoformat()
        content = re.sub(
            r"- \*\*Status\*\*: .*", "- **Status**: completed", content, count=1
        )
        content = re.sub(
            r"- \*\*Last Updated\*\*: .*", f"- **Last Updated**: {now}", content
        )
        if summary:
            content += f"\n\n## Summary\n\n{summary}\n"

        plan_path.write_text(content)
        log.info("planner.completed", task_id=task_id)

    def mark_failed(self, task_id: str, error: str):
        """Mark the entire task as failed."""
        plan_path = self._plan_path(task_id)
        if not plan_path.exists():
            return

        content = plan_path.read_text()
        now = datetime.now(timezone.utc).isoformat()
        content = re.sub(
            r"- \*\*Status\*\*: .*", "- **Status**: failed", content, count=1
        )
        content = re.sub(
            r"- \*\*Last Updated\*\*: .*", f"- **Last Updated**: {now}", content
        )
        content += f"\n\n## Error\n\n{error}\n"

        plan_path.write_text(content)
        log.info("planner.failed", task_id=task_id, error=error[:200])

    # ── Helpers ─────────────────────────────────────────────────────────────────

    def _compute_overall_status(self, content: str, updated_step: int, new_status: str) -> str:
        """Compute overall status based on all steps."""
        # Parse all step statuses
        statuses = re.findall(r"### Step \d+:.*?- \*\*Status\*\*: (\w+)", content, re.DOTALL)
        # Update the one we just changed
        if updated_step <= len(statuses):
            statuses[updated_step - 1] = new_status

        if all(s == "completed" for s in statuses):
            return "completed"
        if any(s == "failed" for s in statuses):
            return "failed"
        if any(s == "running" for s in statuses):
            return "running"
        return "pending"

    def _extract_step_block(self, content: str, step_num: int) -> str | None:
        pattern = re.compile(rf"(### Step {step_num}:.+?)(?=### Step \d+:|\Z)", re.DOTALL)
        m = pattern.search(content)
        return m.group(1) if m else None


# re is used above but not imported; add it here
import re
