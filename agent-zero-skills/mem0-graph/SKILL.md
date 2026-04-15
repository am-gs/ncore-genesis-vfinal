---
name: mem0-graph
description: Graph-enhanced memory system using Mem0. Extracts entities and relationships from conversations, stores them in a graph alongside vector embeddings, and retrieves relationship-aware context. 91% faster than full-context injection with 90% token savings. Use for: cross-session knowledge retention, entity relationship mapping, "who knows who", "what connects X to Y" queries.
triggers: remember relationship, connect entities, who is related to, graph memory, entity extraction, cross-session memory, mem0
---

# Mem0 Graph Memory

## Purpose
Extract entities and relationships from agent work and store them with graph structure.
Enables queries like "what did we find about X last time" that return relationship-aware context.

## Installation (first time only)

```python
import subprocess
result = subprocess.run(
    ["/opt/venv/bin/pip", "install", "-q", "mem0ai"],
    capture_output=True, text=True
)
print("Mem0 installed" if result.returncode == 0 else f"Error: {result.stderr[:200]}")
```

## Setup

```python
from mem0 import Memory

# Configure with local file storage (no external service needed)
config = {
    "vector_store": {
        "provider": "chroma",  # Or use qdrant/faiss
        "config": {
            "collection_name": "ncore_memories",
            "path": "/a0/usr/memory/mem0_chroma"
        }
    },
    "llm": {
        "provider": "litellm",
        "config": {
            "model": "gemini/gemini-2.5-flash",
            "api_key": os.environ.get("GOOGLE_API_KEY", ""),
        }
    },
    "embedder": {
        "provider": "litellm",
        "config": {
            "model": "text-embedding-3-small",
        }
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "ncore2026"
        }
    } if False else {}  # Disable graph store initially — use vector only
}

import os
os.makedirs("/a0/usr/memory/mem0_chroma", exist_ok=True)
m = Memory.from_config(config)
```

## Adding Memories

```python
# Add finding from current task
def add_memory(content, user_id="ncore_agent", metadata=None):
    """Store a finding, solution, or fact"""
    m.add(
        content,
        user_id=user_id,
        metadata=metadata or {
            "timestamp": str(__import__("datetime").datetime.now()),
            "source": "agent_zero"
        }
    )
    print(f"[Mem0] Stored: {content[:60]}...")

# Examples:
add_memory("The Vast.ai API requires JSON dict format for search queries, NOT string format")
add_memory("DeepSeek V3 context window on OpenRouter is capped at 32K by some providers")
add_memory("SearXNG JSON format requires adding 'json' to the formats list in settings.yml")
```

## Searching Memories

```python
def search_memory(query, user_id="ncore_agent", limit=5):
    """Semantic search across all stored memories"""
    results = m.search(query, user_id=user_id, limit=limit)
    
    if not results:
        return "No relevant memories found."
    
    output = f"Found {len(results)} relevant memories for: '{query[:60]}'\n\n"
    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        memory_text = r.get("memory", "")
        output += f"[{i}] (relevance: {score:.2f})\n{memory_text}\n\n"
    
    return output

# Search example:
print(search_memory("Vast.ai API authentication errors"))
print(search_memory("model context window limits OpenRouter"))
```

## Getting All Memories

```python
def get_all_memories(user_id="ncore_agent"):
    """List all stored memories"""
    all_mems = m.get_all(user_id=user_id)
    print(f"Total stored memories: {len(all_mems)}")
    for mem in all_mems[-10:]:  # Last 10
        print(f"  - {mem.get('memory', '')[:100]}")
    return all_mems
```

## Updating a Memory

```python
def update_memory(memory_id, new_content):
    """Update an existing memory (e.g., when solution changes)"""
    m.update(memory_id=memory_id, data=new_content)
    print(f"[Mem0] Updated memory {memory_id[:8]}")
```

## Deleting Memories

```python
def delete_memory(memory_id):
    m.delete(memory_id=memory_id)

def clear_all_memories(user_id="ncore_agent"):
    m.delete_all(user_id=user_id)
    print("[Mem0] All memories cleared")
```

## Post-Task Learning Pattern

After every successful complex task, call this to store learnings:

```python
def capture_task_learning(task_description, solution, tools_used, outcome="success"):
    """Auto-capture what was learned from this task"""
    learning = f"""
Task: {task_description[:100]}
Solution: {solution[:300]}
Tools: {', '.join(tools_used)}
Outcome: {outcome}
"""
    add_memory(learning.strip(), metadata={"type": "task_learning", "outcome": outcome})

# Usage after completing a task:
capture_task_learning(
    "Deploy SearXNG on Oracle ARM",
    "docker run -d searxng/searxng:latest -p 8888:8080, then add json to formats in settings.yml",
    ["docker", "curl"],
    "success"
)
```

## Notes
- Mem0 uses chromadb for vector storage locally (no external service)
- First search is slower (cold start) — subsequent searches are cached
- Memories persist across Agent Zero restarts (stored on volume)
- Use search_memory() at the START of complex tasks for relevant prior context
- Use add_memory() at the END of tasks to store learnings
