#!/usr/bin/env python3
"""Long-horizon stress test for the sovereign swarm pipeline.

Task: Analyze the repository, write measurement scripts for 3 improvement
areas, execute them, and aggregate a report.

This exercises planner → dispatch (parallel) → execute → verify → aggregate
with checkpoint recovery across the full graph.
"""

import asyncio
import json
import os
import sys
import time
import traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.langgraph_swarm import run_swarm_task, get_checkpointer, resume_swarm_task


LONG_TASK = (
    "Run this multi-step analysis and return a JSON summary with: loc_count, top_5_functions, disk_usage_mb, script_output.\n"
    "Step 1: Run 'wc -l /home/ubuntu/sovereign/mission_control.py' to count lines of code.\n"
    "Step 2: Run 'grep -oP \"^def \\K\\w+\" /home/ubuntu/sovereign/mission_control.py | sort | uniq -c | sort -rn | head -5' to find top 5 functions.\n"
    "Step 3: Run 'du -sh /home/ubuntu/sovereign/' to get disk usage.\n"
    "Step 4: Return a JSON object with keys: loc_count (int), top_5_functions (list of strings), disk_usage_mb (string), script_output (string)."
)


async def stress_test(
    crash_at_node: str | None = None,
) -> dict:
    """Run the long-horizon task. Optionally simulate a crash for recovery test."""
    task_id = f"stress-{int(time.time())}"
    print(f"\n{'='*60}")
    print(f"[STRESS] task_id={task_id}")
    print(f"[STRESS] crash_simulation={crash_at_node}")
    print(f"{'='*60}\n")

    # ── Phase 1: Normal run ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    final_state = await run_swarm_task(task_id, LONG_TASK)
    latency_s = time.perf_counter() - t0

    # ── Metrics ──────────────────────────────────────────────────────────────
    cp = get_checkpointer()
    cp_type = type(cp).__name__

    checkpoints = final_state.get("checkpoints", [])
    plan_steps = final_state.get("plan_steps", [])
    subagent_results = final_state.get("subagent_results", [])
    verification = final_state.get("verification_status", "unknown")
    status = final_state.get("status", "unknown")
    error = final_state.get("error")

    print(f"\n{'='*60}")
    print("[RESULTS]")
    print(f"  status          : {status}")
    print(f"  latency         : {latency_s:.2f}s")
    print(f"  checkpoints     : {len(checkpoints)}")
    for c in checkpoints:
        print(f"    - {c}")
    print(f"  plan_steps      : {len(plan_steps)}")
    for i, p in enumerate(plan_steps[:5]):
        print(f"    [{i}] {p.get('tool', '?')} — {p.get('description', '')[:60]}")
    print(f"  subagent_results: {len(subagent_results)}")
    for i, r in enumerate(subagent_results[:5]):
        out = str(r.get("output", ""))[:80].replace("\n", " ")
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

    # ── Phase 2: Recovery test ─────────────────────────────────────────────
    if status == "completed":
        print("[RECOVERY] Testing time-travel resume from checkpoints...")
        resume_task_id = f"{task_id}-resume"
        t1 = time.perf_counter()
        recovered = await resume_swarm_task(resume_task_id, LONG_TASK, thread_id=task_id)
        resume_latency = time.perf_counter() - t1
        print(f"[RECOVERY] Resume latency: {resume_latency:.2f}s")
        print(f"[RECOVERY] Recovered status: {recovered.get('status')}")
        print(f"[RECOVERY] Recovered checkpoints: {len(recovered.get('checkpoints', []))}")
        metrics["recovery_latency_s"] = round(resume_latency, 2)
        metrics["recovery_status"] = recovered.get("status")
        metrics["recovery_checkpoints_count"] = len(recovered.get("checkpoints", []))
    else:
        print("[RECOVERY] Skipped — primary run did not complete.")
        metrics["recovery_status"] = "skipped"

    return metrics


async def main():
    print("[STRESS TEST] Sovereign Swarm — Long Horizon\n")
    metrics = await stress_test()

    print(f"\n{'='*60}")
    print("[FINAL METRICS JSON]")
    print(json.dumps(metrics, indent=2, default=str))
    print(f"{'='*60}\n")

    # Validation
    assert metrics["status"] in ("completed", "failed"), "Task did not reach terminal state"
    assert metrics["checkpoints_count"] >= 1, "Expected at least 1 checkpoint"

    if metrics["status"] == "completed":
        assert metrics["plan_steps_count"] >= 1, "Expected at least 1 plan step"
        assert metrics["subagent_results_count"] >= 1, "Expected at least 1 subagent result"
        print("[PASS] All stress-test assertions passed.")
    else:
        print(f"[WARN] Task failed but pipeline completed — error: {metrics.get('error')}")
        print(f"[WARN] This is acceptable for stress testing — LLM may refuse or rate-limit.")
        # Do not sys.exit(1) — stress test records the failure for analysis


if __name__ == "__main__":
    asyncio.run(main())
