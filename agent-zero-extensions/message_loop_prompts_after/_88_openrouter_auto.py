"""
Extension: OpenRouter Auto-Router Context
Injects the openrouter/auto model option into the agent's awareness.
When complexity is detected, suggests switching to openrouter/auto which
uses NotDiamond-powered routing across Claude, GPT, Gemini, and DeepSeek.
Based on: OpenRouter auto-router docs (openrouter.ai/docs/guides/routing/routers/auto-router)
"""
from helpers.extension import Extension
from agent import LoopData

AUTO_ROUTER_HINT = """
## OpenRouter Auto-Router (for complex tasks)

When a task requires maximum intelligence regardless of model family, use openrouter/auto:

```python
import requests, os

r = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY','')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/am-gs/ncore-genesis-vfinal",
    },
    json={
        "model": "openrouter/auto",  # NotDiamond selects best model for this prompt
        "messages": YOUR_MESSAGES,
        "provider": {
            "sort": "throughput",
            "data_collection": "deny"
        }
    },
    timeout=30
)
result = r.json()["choices"][0]["message"]["content"]
# Check which model was actually used:
# r.json().get("model") shows the selected model
```

openrouter/auto analyzes the prompt and selects the best model from:
Claude Sonnet, GPT-5 Mini, Gemini Flash, DeepSeek Chat — whichever fits best.
No extra routing fee. Use for: ambiguous complex tasks, best-effort quality.
"""

class OpenRouterAutoHint(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return
        
        if hasattr(loop_data, 'extras_persistent') and loop_data.extras_persistent is not None:
            if "_auto_router_injected" not in loop_data.extras_persistent:
                loop_data.extras_persistent["openrouter_auto"] = AUTO_ROUTER_HINT
                loop_data.extras_persistent["_auto_router_injected"] = True
