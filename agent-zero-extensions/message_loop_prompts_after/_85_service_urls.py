"""
Extension: Service URL Injector
Injects available local service URLs into the agent context every session.
Agent automatically knows about SearXNG, Crawl4AI, and other services.
"""
from helpers.extension import Extension
from agent import LoopData
import os, requests

SERVICES = {
    "SearXNG Search": ("http://localhost:8888", "/search?q={query}&format=json"),
    "Crawl4AI Web Reader": ("http://localhost:11235", "/crawl"),
    "SpiderFoot OSINT": ("http://host.docker.internal:5001", "/api/v1/startscan"),
}

SERVICE_HINT = """
## Local Services Available (use these before making external API calls)

### SearXNG — Unlimited Free Search
```python
import requests
results = requests.get(
    "http://localhost:8888/search",
    params={"q": YOUR_QUERY, "format": "json"},
    timeout=10
).json().get("results", [])
for r in results[:5]:
    print(r["title"], r["url"])
```

### Crawl4AI — Fast Web Content Extraction (returns clean markdown)
```python
import requests, time
r = requests.post("http://localhost:11235/crawl",
    json={"urls": [YOUR_URL], "priority": 10},
    timeout=5)
task_id = r.json().get("task_id", r.json().get("id", ""))
# Poll for result
for _ in range(20):
    time.sleep(1)
    result = requests.get(f"http://localhost:11235/task/{task_id}").json()
    if result.get("status") == "completed":
        markdown = result.get("results", [{}])[0].get("markdown", "")
        break
```

### trafilatura — Instant URL to Markdown (simpler alternative)
```python
import subprocess
result = subprocess.run(
    ["/opt/venv/bin/python3", "/a0/usr/workdir/web_reader.py", YOUR_URL],
    capture_output=True, text=True, timeout=30
)
markdown_content = result.stdout
```

Use SearXNG instead of browser search. Use Crawl4AI/trafilatura instead of browser page reading. Both are faster and do not count against API rate limits.
"""

class ServiceUrlInjector(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        # Only inject on first iteration of each session
        if hasattr(loop_data, 'extras_persistent') and loop_data.extras_persistent is not None:
            if "_services_injected" not in loop_data.extras_persistent:
                loop_data.extras_persistent["local_services"] = SERVICE_HINT
                loop_data.extras_persistent["_services_injected"] = True
