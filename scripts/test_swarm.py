#!/usr/bin/env python3
"""End-to-end test for the LangGraph Swarm pipeline."""

import asyncio
import sys
import time

sys.path.insert(0, "/home/ncore-genesis-vfinal")
sys.path.insert(0, "/home/ncore-genesis-vfinal/core")

from core.langgraph_swarm import run_swarm_task, get_checkpointer


async def test_word_count_task():
    task_id = f"test-{int(time.time())}"
    prompt = "Create a Python script that counts words in a file"

    print(f"[TEST] Starting swarm task {task_id}")
    print(f"[TEST] Prompt: {prompt}")

    start = time.perf_counter()
    final_state = await run_swarm_task(task_id, prompt)
    latency_ms = (time.perf_counter() - start) * 1000

    print("\n[RESULT] Final state:")
    print(f"  status: {final_state['status']}")
    print(f"  checkpoints: {final_state.get('checkpoints', [])}")
    print(f"  plan_steps count: {len(final_state.get('plan_steps', []))}")
    print(f"  subagent_results count: {len(final_state.get('subagent_results', []))}")
    print(f"  verification_status: {final_state.get('verification_status')}")
    print(f"  error: {final_state.get('error')}")
    print(f"  latency_ms: {latency_ms:.1f}")

    # Verify checkpoint count
    cp = get_checkpointer()
    print(f"\n[CHECKPOINTER] type: {type(cp).__name__}")

    # For MemorySaver, we can inspect internal state
    if hasattr(cp, 'get'):
        try:
            checkpoints = list(cp.get({'configurable': {'thread_id': task_id}}))
            print(f"[CHECKPOINTER] checkpoints stored: {len(checkpoints)}")
        except Exception as e:
            print(f"[CHECKPOINTER] Could not enumerate checkpoints: {e}")

    # Validation
    assert final_state["status"] in ("completed", "failed"), "Task did not reach terminal state"
    assert len(final_state.get("checkpoints", [])) >= 2, "Expected at least 2 checkpoints"
    assert final_state["task_id"] == task_id, "Task ID mismatch"

    print("\n[TEST] All assertions passed.")
    return final_state, latency_ms


if __name__ == "__main__":
    final_state, latency_ms = asyncio.run(test_word_count_task())
    print(f"\nOperational metrics: latency={latency_ms:.1f}ms, checkpoints={len(final_state.get('checkpoints', []))}")
