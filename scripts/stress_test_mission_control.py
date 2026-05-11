#!/usr/bin/env python3
"""
Stress-test Mission Control task execution pipeline.

Usage:
    python stress_test_mission_control.py --tasks 10 --concurrency 3 --timeout 600 --output results.json
"""

import argparse
import asyncio
import json
import time
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx


API_BASE = "http://127.0.0.1:3004/api"
DEFAULT_TASK_DESCRIPTION = "List files in /tmp and report count"


async def _create_task(client: httpx.AsyncClient, name: str, description: str) -> dict:
    r = await client.post(
        f"{API_BASE}/tasks",
        json={"name": name, "description": description, "agent": "manus"},
        headers={"content-type": "application/json"},
    )
    r.raise_for_status()
    return r.json()


async def _execute_task(client: httpx.AsyncClient, task_id: str) -> dict:
    r = await client.post(
        f"{API_BASE}/tasks/{task_id}/execute",
        headers={"content-type": "application/json"},
    )
    r.raise_for_status()
    return r.json()


async def _get_task(client: httpx.AsyncClient, task_id: str) -> dict:
    r = await client.get(f"{API_BASE}/tasks/{task_id}")
    r.raise_for_status()
    return r.json()


async def _run_single_task(
    client: httpx.AsyncClient,
    index: int,
    description: str,
    poll_interval: float,
    max_poll_wait: float,
) -> dict:
    start_create = time.monotonic()
    task = await _create_task(client, f"stress-test-{index}", description)
    created_at = time.monotonic()
    task_id = task["id"]

    await _execute_task(client, task_id)
    exec_started_at = time.monotonic()

    terminal_status = None
    elapsed_poll = 0.0
    final_task = None

    while elapsed_poll < max_poll_wait:
        await asyncio.sleep(poll_interval)
        final_task = await _get_task(client, task_id)
        status = final_task.get("status", "")
        if status in ("completed", "failed", "cancelled"):
            terminal_status = status
            break
        elapsed_poll += poll_interval

    completed_at = time.monotonic()

    create_to_exec = exec_started_at - created_at
    exec_to_done = (
        (completed_at - exec_started_at)
        if terminal_status
        else None
    )

    return {
        "index": index,
        "task_id": task_id,
        "status": terminal_status or final_task.get("status", "unknown") if final_task else "unknown",
        "error": final_task.get("error") if final_task else None,
        "create_to_exec_start_seconds": create_to_exec,
        "exec_start_to_done_seconds": exec_to_done,
        "total_seconds": completed_at - start_create,
    }


async def _bounded_run(
    client: httpx.AsyncClient,
    index: int,
    description: str,
    poll_interval: float,
    max_poll_wait: float,
    sem: asyncio.Semaphore,
) -> dict:
    async with sem:
        return await _run_single_task(client, index, description, poll_interval, max_poll_wait)


async def main(args: argparse.Namespace) -> None:
    sem = asyncio.Semaphore(args.concurrency)
    description = args.description or DEFAULT_TASK_DESCRIPTION
    max_poll_wait = args.timeout * 2

    results: List[dict] = []
    start_run = time.monotonic()

    async with httpx.AsyncClient(timeout=30) as client:
        coros = [
            _bounded_run(client, i, description, 2.0, max_poll_wait, sem)
            for i in range(args.tasks)
        ]
        results = await asyncio.gather(*coros, return_exceptions=True)

    end_run = time.monotonic()
    total_run = end_run - start_run

    ok_results: List[dict] = []
    errors: List[dict] = []
    for r in results:
        if isinstance(r, Exception):
            errors.append({"error": str(r)})
        else:
            ok_results.append(r)

    statuses = {"completed": 0, "failed": 0, "cancelled": 0, "timed_out": 0, "other": 0}
    exec_times: List[float] = []
    total_times: List[float] = []

    for r in ok_results:
        st = r["status"]
        if st == "completed":
            statuses["completed"] += 1
        elif st == "failed":
            if r.get("error") and "timed out" in r["error"].lower():
                statuses["timed_out"] += 1
            else:
                statuses["failed"] += 1
        elif st == "cancelled":
            statuses["cancelled"] += 1
        else:
            statuses["other"] += 1
        if r["exec_start_to_done_seconds"] is not None:
            exec_times.append(r["exec_start_to_done_seconds"])
        total_times.append(r["total_seconds"])

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "tasks": args.tasks,
            "concurrency": args.concurrency,
            "timeout": args.timeout,
            "description": description,
        },
        "summary": {
            "total_run_seconds": total_run,
            "success_rate": statuses["completed"] / args.tasks if args.tasks else 0.0,
            "failure_rate": (statuses["failed"] + statuses["timed_out"]) / args.tasks if args.tasks else 0.0,
            "timeout_rate": statuses["timed_out"] / args.tasks if args.tasks else 0.0,
            "avg_exec_time_seconds": (sum(exec_times) / len(exec_times)) if exec_times else None,
            "max_exec_time_seconds": max(exec_times) if exec_times else None,
            "avg_total_time_seconds": (sum(total_times) / len(total_times)) if total_times else None,
            "max_total_time_seconds": max(total_times) if total_times else None,
            "throughput_tasks_per_minute": (statuses["completed"] / total_run * 60) if total_run else 0.0,
            "status_counts": statuses,
            "error_count": len(errors),
        },
        "tasks": ok_results,
        "errors": errors,
    }

    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary["summary"], indent=2))
    print(f"\nFull results written to {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress-test Mission Control")
    parser.add_argument("--tasks", type=int, default=10, help="Number of tasks to create")
    parser.add_argument("--concurrency", type=int, default=3, help="Max concurrent tasks")
    parser.add_argument("--timeout", type=int, default=600, help="Task timeout in seconds")
    parser.add_argument("--description", type=str, default=None, help="Task description")
    parser.add_argument("--output", type=str, default="stress_test_results.json", help="Output JSON path")
    args = parser.parse_args()
    asyncio.run(main(args))
