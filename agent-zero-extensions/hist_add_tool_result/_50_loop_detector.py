"""
Extension: Loop Detector
Runs after every tool result is added to history.
Detects when the agent is repeating the same tool call and injects an interrupt.
Prevents the agent from burning tokens in infinite loops.
"""
from typing import Any
from helpers.extension import Extension
import json, os, hashlib, time

LOOP_THRESHOLD = 3        # Same call 3x = loop detected
HISTORY_WINDOW = 8        # Check last 8 tool calls
STATE_FILE = "/a0/usr/workdir/.loop_detector_state.json"

def _load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {"recent_calls": [], "last_interrupt": 0}

def _save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

class LoopDetector(Extension):
    def execute(self, data: dict[str, Any] | None = None, **kwargs):
        if not self.agent or not data:
            return

        tool_result = data.get("tool_result")
        if not tool_result:
            return

        # Get tool call info from agent history
        history = []
        try:
            hist = self.agent.context.history
            if hist:
                for msg in hist[-HISTORY_WINDOW:]:
                    msg_str = str(msg)
                    if "tool" in msg_str.lower() and len(msg_str) > 20:
                        history.append(hashlib.md5(msg_str[:200].encode()).hexdigest()[:8])
        except Exception:
            return

        if not history:
            return

        # Check for repetition
        state = _load_state()
        recent = state.get("recent_calls", [])
        recent.append(history[-1] if history else "")
        recent = recent[-HISTORY_WINDOW:]
        state["recent_calls"] = recent

        # Count how many times the last call appeared in recent history
        if len(recent) >= LOOP_THRESHOLD:
            last_call = recent[-1]
            count = recent.count(last_call)

            # Don't interrupt more than once every 5 minutes
            last_interrupt = state.get("last_interrupt", 0)
            if count >= LOOP_THRESHOLD and (time.time() - last_interrupt) > 300:
                state["last_interrupt"] = time.time()
                state["recent_calls"] = []  # Reset after interrupt

                # Inject interrupt message into tool result
                interrupt_msg = f"""

[LOOP DETECTED] You have made the same or very similar tool call {count} times in a row.
STOP. You are stuck in a loop.

Required actions:
1. Identify WHY this approach is not working
2. Try a COMPLETELY DIFFERENT approach
3. If you cannot proceed, summarize what you have found so far and ask the user for clarification
4. Do NOT repeat the same tool call again

What you have attempted is NOT working. Change strategy now.
"""
                # Append to tool result to make agent see it
                if isinstance(data.get("tool_result"), str):
                    data["tool_result"] = data["tool_result"] + interrupt_msg
                elif isinstance(data.get("tool_result"), dict):
                    data["tool_result"]["loop_interrupt"] = interrupt_msg.strip()

        _save_state(state)
