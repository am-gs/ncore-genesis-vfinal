---
name: anti-drift
description: Long-task supervisor for multi-hour autonomous workflows. Prevents context overflow, loop detection, progress validation, and checkpoint/resume. Use at the start of any task expected to take more than 20 steps or 30 minutes.
triggers: long task, multi-step task, hours long, complex research, autonomous workflow, multi-hour, checkpoint, resume task
---

# Anti-Drift Long Task Supervisor

## Purpose
Prevents the three failure modes of long autonomous tasks:
1. **Context overflow crash** — context window fills and agent crashes or produces garbage
2. **Infinite loop** — agent calls same tool with same args repeatedly without progress
3. **Goal drift** — agent gradually moves away from original objective

## Setup — Call at Task Start

```python
import json, os, time, hashlib
from datetime import datetime

CHECKPOINT_FILE = "/a0/usr/workdir/task_checkpoint.json"
STEP_COUNTER_FILE = "/a0/usr/workdir/task_steps.json"

def start_long_task(goal, task_id=None):
    """Initialize checkpoint system for a long task"""
    task_id = task_id or hashlib.md5(goal.encode()).hexdigest()[:8]
    
    checkpoint = {
        "task_id": task_id,
        "goal": goal,
        "started": datetime.now().isoformat(),
        "step_count": 0,
        "last_step_time": time.time(),
        "recent_tool_calls": [],  # For loop detection
        "completed_subtasks": [],
        "key_findings": [],
        "status": "running"
    }
    
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f, indent=2)
    
    print(f"[AntiDrift] Task {task_id} started: {goal[:80]}")
    return checkpoint

def load_checkpoint():
    """Load existing checkpoint to resume a task"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return None
```

## Step Tracker — Call After EVERY Tool Use

```python
def track_step(tool_name, tool_args, tool_result, subtask_completed=None, finding=None):
    """
    Call after every tool use. Returns action to take:
    - "continue" — proceed normally
    - "compress" — compress history now (approaching context limit)
    - "loop_detected" — same call made 3x, need to reframe
    - "checkpoint" — step limit approaching, save state
    """
    
    if not os.path.exists(CHECKPOINT_FILE):
        return "continue"
    
    with open(CHECKPOINT_FILE) as f:
        cp = json.load(f)
    
    cp["step_count"] += 1
    cp["last_step_time"] = time.time()
    
    # Save completed subtask
    if subtask_completed:
        cp["completed_subtasks"].append(subtask_completed)
    
    # Save key finding
    if finding:
        cp["key_findings"].append(finding)
    
    # === LOOP DETECTION ===
    call_signature = f"{tool_name}:{str(tool_args)[:100]}"
    cp["recent_tool_calls"].append(call_signature)
    cp["recent_tool_calls"] = cp["recent_tool_calls"][-10:]  # Keep last 10
    
    # Count duplicates in recent calls
    recent = cp["recent_tool_calls"]
    if len(recent) >= 3:
        last_three = recent[-3:]
        if len(set(last_three)) == 1:
            print(f"[AntiDrift] LOOP DETECTED: '{tool_name}' called 3x with same args")
            cp["status"] = "loop_detected"
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump(cp, f, indent=2)
            return "loop_detected"
    
    # === CONTEXT BUDGET CHECK ===
    # Estimate: each step adds ~500-2000 tokens to context
    estimated_tokens = cp["step_count"] * 1000  # Conservative estimate
    gemini_limit = 1_000_000
    groq_limit = 32_000
    
    current_limit = groq_limit  # Use smaller limit to be safe
    token_pct = estimated_tokens / current_limit
    
    action = "continue"
    
    if token_pct >= 0.80:
        print(f"[AntiDrift] Context at ~{token_pct*100:.0f}% — forcing handoff")
        action = "handoff"
    elif token_pct >= 0.60:
        print(f"[AntiDrift] Context at ~{token_pct*100:.0f}% — compress history")
        action = "compress"
    
    # === CHECKPOINT EVERY 10 STEPS ===
    if cp["step_count"] % 10 == 0:
        print(f"[AntiDrift] Checkpoint at step {cp['step_count']}")
        action = "checkpoint" if action == "continue" else action
    
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(cp, f, indent=2)
    
    return action
```

## Handle Each Action

```python
def handle_action(action, goal):
    """Take corrective action based on track_step() return value"""
    
    cp = load_checkpoint()
    
    if action == "loop_detected":
        # Inject reframe prompt
        completed = "\n".join(f"- {s}" for s in cp["completed_subtasks"][-5:])
        findings = "\n".join(f"- {f}" for f in cp["key_findings"][-5:])
        
        print(f"""
[AntiDrift] LOOP REFRAME — inject this into your next prompt:

You are stuck in a loop. STOP what you're doing.

Your original goal: {goal}

What you've already completed:
{completed if completed else "Nothing recorded yet"}

Key findings so far:
{findings if findings else "None recorded yet"}

Choose a DIFFERENT approach. You may NOT use the same tool with the same arguments again.
Consider: Have you searched broadly enough? Do you have all the information you need?
Is there a simpler path to the goal?
""")
        return "reframe"
    
    elif action in ("compress", "checkpoint", "handoff"):
        # Build context summary
        cp = load_checkpoint()
        summary = f"""
=== TASK CHECKPOINT (Step {cp['step_count']}) ===
Goal: {cp['goal']}
Started: {cp['started']}

Completed subtasks ({len(cp['completed_subtasks'])}):
{chr(10).join(f"- {s}" for s in cp['completed_subtasks'])}

Key findings:
{chr(10).join(f"- {f}" for f in cp['key_findings'])}

Status: {cp['status']}
=== END CHECKPOINT ===
"""
        print(summary)
        
        if action == "handoff":
            print("[AntiDrift] Context limit approaching. Spawn a fresh agent with this checkpoint.")
            print(f"Checkpoint saved at: {CHECKPOINT_FILE}")
        
        return summary
    
    return None
```

## Progress Validator — Call Every 5 Steps

```python
def validate_progress(goal, recent_outputs):
    """
    Quick check: is the agent making progress toward the goal?
    Uses local heuristics — no LLM call needed.
    """
    
    cp = load_checkpoint()
    if not cp:
        return True
    
    # Check time since last progress
    time_since_last = time.time() - cp["last_step_time"]
    
    # Check if subtasks are being completed
    subtask_velocity = len(cp["completed_subtasks"]) / max(1, cp["step_count"])
    
    if subtask_velocity < 0.05 and cp["step_count"] > 20:
        # Less than 5% of steps are completing subtasks after 20 steps
        print(f"[AntiDrift] WARNING: Low progress rate ({subtask_velocity*100:.1f}% steps complete subtasks)")
        print(f"[AntiDrift] Inject: 'Are you making progress toward: {goal[:60]}? If stuck, try a different approach.'")
        return False
    
    return True
```

## Complete Usage Example

```python
# At task start:
checkpoint = start_long_task("Research AI agent frameworks and write a comparison report")

# After EVERY tool call:
action = track_step(
    tool_name="browser_search",
    tool_args={"query": "agent zero vs autogpt 2026"},
    tool_result="Found 10 results...",
    subtask_completed="Searched for agent frameworks",  # Optional
    finding="Agent Zero has 45K GitHub stars"  # Optional key fact
)

# Handle the action:
if action != "continue":
    response = handle_action(action, checkpoint["goal"])
    # If "loop_detected": inject reframe prompt
    # If "compress": summarize context
    # If "handoff": spawn fresh agent with checkpoint

# Every 5 steps:
if checkpoint["step_count"] % 5 == 0:
    validate_progress(checkpoint["goal"], [])
```

## Checkpoint Resume Pattern

If a task was interrupted, load the checkpoint and continue:

```python
checkpoint = load_checkpoint()
if checkpoint and checkpoint["status"] == "running":
    print(f"Resuming task: {checkpoint['goal']}")
    print(f"Already completed: {len(checkpoint['completed_subtasks'])} subtasks")
    print(f"Step count: {checkpoint['step_count']}")
    # Continue from where it left off
```
