"""
Extension: Speed Routing Hint
Injects a hint about available speed-tier providers into the agent context.
This tells the agent it can use Cerebras for fast sub-tasks without the user configuring anything.
"""
from helpers.extension import Extension
from agent import LoopData
import os

SPEED_HINT = """
## Speed-Tier Providers Available

For fast sub-tasks (classification, validation, quick decisions), use Cerebras directly:

```python
import requests, os
r = requests.post(
    "https://api.cerebras.ai/v1/chat/completions",
    headers={"Authorization": f"Bearer {os.environ.get('CEREBRAS_API_KEY','')}",
             "Content-Type": "application/json"},
    json={"model": "llama3.1-8b",
          "messages": [{"role": "user", "content": YOUR_QUESTION}],
          "max_tokens": 200},
    timeout=8
)
answer = r.json()["choices"][0]["message"]["content"]
```

Speed: 2,533 tok/s. Use for: yes/no decisions, task routing, quick validation, loop control.
For complex reasoning: use "qwen-3-235b-a22b-instruct-2507" at 1,166 tok/s.
"""

class SpeedRoutingHint(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        cerebras_key = os.environ.get("CEREBRAS_API_KEY", "")
        if not cerebras_key or cerebras_key.startswith("register"):
            return  # No key configured, skip

        # Only inject once per session (not every loop iteration)
        if hasattr(loop_data, 'extras_persistent') and loop_data.extras_persistent is not None:
            if "_speed_hint_injected" not in loop_data.extras_persistent:
                loop_data.extras_persistent["speed_providers"] = SPEED_HINT
                loop_data.extras_persistent["_speed_hint_injected"] = True
