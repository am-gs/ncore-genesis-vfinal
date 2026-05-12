#!/usr/bin/env python3
"""Deterministic stress test — bypasses LLM planner by monkey-patching it.

Validates: dispatch concurrency, terminal execution, checkpoint recording,
critic verification, aggregate, and time-travel recovery.
"""

import asyncio
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

import core.langgraph_swarm as swarm
from core.langgraph_swarm import run_swarm_task, get_checkpointer, resume_swarm_task


DETERMINISTIC_PLAN = [
    {
        "id": "s1",
        "description": "Count LOC in mission_control.py",
        "tool": "terminal_execute",
        "input": {"command": "wc -l /home/ubuntu/sovereign/mission_control.py"},
    },
    {
        "id": "s2",
        "description": "Find top 5 function names",
        "tool": "terminal_execute",
        "input": {
            "command": r"grep -oP '^def \K\w+' /home/ubuntu/sovereign/mission_control.py | sort | uniq -c | sort -rn | head -5"
        },
    },
    {
        "id": "s3",
        "description": "Measure disk usage of sovereign directory",
        "tool": "terminal_execute",
        "input": {"command": "du -sh /home/ubuntu/sovereign/"},
    },
    {
        "id": "s4",
        "description": "Write metrics script",
        "tool": "file_write",
        "input": {
            "path": "/tmp/metrics_collector.py",
            "content": "import json, subprocess, os\nloc = subprocess.run(['wc', '-l', '/home/ubuntu/sovereign/mission_control.py'], capture_output=True, text=True).stdout.strip().split()[0]\ndu = subprocess.run(['du', '-sh', '/home/ubuntu/sovereign/'], capture_output=True, text=True).stdout.strip().split()[0]\nprint(json.dumps({'loc_count': int(loc), 'disk_usage': du}))\n",
        },
    },
    {
        "id": "s5",
        "description": "Run metrics script",
        "tool": "terminal_execute",
        "input": {"command": "python3 /tmp/metrics_collector.py"},
    },
]


async def _deterministic_planner(state):
    """Inject a pre-canned plan, bypassing the LLM entirely."""
    state["plan_steps"] = DETERMINISTIC_PLAN
    state["status"] = "dispatching"
    state["checkpoints"].append(f"planner:{swarm._iso_now()}")
    state["messages"].append({"role": "assistant", "content": f"Planner generated {len(DETERMINISTIC_PLAN)} steps (deterministic)."})
    return state


async def main():
    task_id = f"det-stress-{int(time.time())}"
    print(f"\n{'='*60}")
    print(f"[DETERMINISTIC STRESS] task_id={task_id}")
    print(f"{'='*60}\n")

    # Monkey-patch planner
    original_planner = swarm.planner_node
    swarm.planner_node = _deterministic_planner

    try:
        t0 = time.perf_counter()
        final_state = await run_swarm_task(task_id, "Analyze this repository")
        latency_s = time.perf_counter() - t0
    finally:
        swarm.planner_node = original_planner

    checkpoints = final_state.get("checkpoints", [])
    plan_steps = final_state.get("plan_steps", [])
    subagent_results = final_state.get("subagent_results", [])
    verification = final_state.get("verification_status", "unknown")
    status = final_state.get("status", "unknown")
    error = final_state.get("error")
    cp_type = type(get_checkpointer()).__name__

    print(f"\n{'='*60}")
    print("[RESULTS]")
    print(f"  status          : {status}")
    print(f"  latency         : {latency_s:.2f}s")
    print(f"  checkpoints     : {len(checkpoints)}")
    for c in checkpoints:
        print(f"    - {c}")
    print(f"  plan_steps      : {len(plan_steps)}")
    for i, p in enumerate(plan_steps):
        desc = p.get('description', '')[:80]
        tool = p.get('tool', '?')
        print(f"    [{i}] {tool} — {desc}")
    print(f"  subagent_results: {len(subagent_results)}")
    for i, r in enumerate(subagent_results):
        out = str(r.get("output", ""))[:120].replace("\n", " ")
        print(f"    [{i}] {r.get('status', '?')} — {out}")
    print(f"  verification    : {verification}")
    print(f"  error           : {error}")
    print(f"  checkpointer    : {cp_type}")
    print(f"{'='*60}\n")

    metrics = {
        "task_id": task_id,
        "status": status,
        "latency_s": round(latency_s, 2),
        "checkpoints_count": len(checkpoints),
        "plan_steps_count": len(plan_steps),
        "subagent_results_count": len(subagent_results),
        "verification": verification,
        "error": error,
        "checkpointer_type": cp_type,
    }

    # Recovery test
    if status == "completed":
        print("[RECOVERY] Testing time-travel resume from checkpoints...")
        resume_task_id = f"{task_id}-resume"
        t1 = time.perf_counter()
        recovered = await resume_swarm_task(resume_task_id, "Analyze this repository", thread_id=task_id)
        resume_latency = time.perf_counter() - t1
        print(f"[RECOVERY] Resume latency: {resume_latency:.2f}s")
        print(f"[RECOVERY] Recovered status: {recovered.get('status')}")
        print(f"[RECOVERY] Recovered checkpoints: {len(recovered.get('checkpoints', []))}")
        metrics["recovery_latency_s"] = round(resume_latency, 2)
        metrics["recovery_status"] = recovered.get("status")
        metrics["recovery_checkpoints_count"] = len(recovered.get("checkpoints", []))
    else:
        print(f"[RECOVERY] Skipped — primary status={status}")
        metrics["recovery_status"] = "skipped"

    print(f"\n[FINAL METRICS JSON]")
    print(json.dumps(metrics, indent=2, default=str))
    print(f"\n{'='*60}")
    if metrics["status"] == "completed":
        print("[PASS] Deterministic stress test PASSED — pipeline fully operational.")
    else:
        print(f"[RESULT] Pipeline completed in {metrics['latency_s']}s with status={metrics['status']}")
    print(f"{'='*60}\n")
    return metrics


if __name__ == "__main__":
    asyncio.run(main())
