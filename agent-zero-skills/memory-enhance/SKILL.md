---
name: memory-enhance
description: Enhanced memory search and recall. Performs deep semantic search across all stored Agent Zero memories, task history, and learned solutions to surface relevant context before executing tasks. Also saves learnings after task completion.
triggers: remember, recall, what did we discuss, previous session, memory search, context from before, have we done this
---

# Enhanced Memory Recall

## Purpose
Before starting complex tasks, search existing memory for relevant prior solutions, patterns, or context. After completing tasks, save learnings for future recall.

## Pre-Task Memory Search

### Step 1: Extract Search Terms
```python
import os, json, glob, re

def extract_terms(task_text):
    # Remove common stop words, keep meaningful terms
    stop = {"the","a","an","is","are","was","to","for","of","in","on","at","by","with","this","that","it","be","do","have","has"}
    words = re.findall(r'\b\w{4,}\b', task_text.lower())
    return [w for w in words if w not in stop][:15]  # Top 15 terms
```

### Step 2: Search All Memory Locations
```python
def deep_memory_search(query_terms):
    search_dirs = [
        "/a0/usr/memory",
        "/a0/usr/workdir/reports",
        "/a0/usr/workdir/osint",
    ]
    results = []
    
    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            for fname in files:
                if not fname.endswith(('.json', '.md', '.txt')):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r', errors='ignore') as f:
                        content = f.read()
                    
                    # Score: count term matches
                    score = sum(content.lower().count(term) for term in query_terms)
                    if score > 0:
                        # Extract most relevant snippet
                        snippet = content[:600]
                        results.append({
                            "file": fpath.replace("/a0/usr/", ""),
                            "score": score,
                            "snippet": snippet,
                            "size": len(content)
                        })
                except:
                    pass
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:8]  # Top 8 results

# Execute
terms = extract_terms(current_task_description)
memories = deep_memory_search(terms)

if memories:
    print(f"Found {len(memories)} relevant memories:")
    for m in memories[:3]:  # Show top 3
        print(f"\n[Memory: {m['file']} | relevance: {m['score']}]")
        print(m['snippet'][:300])
else:
    print("No relevant prior memories found.")
```

### Step 3: Check Agent Zero's Native Memory
Use the memory tool to search stored facts:
```python
# Agent Zero's built-in memory search
# The memory tool will surface relevant stored facts
```

## Post-Task Learning Capture

After successfully completing a task, save learnings:

```python
import datetime

def save_task_learning(task_summary, key_solution, tools_used, success=True):
    """Save task outcome to memory for future recall"""
    learning = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "task": task_summary[:200],
        "outcome": "success" if success else "failed",
        "tools": tools_used,
        "solution": key_solution[:500],
        "reusable": True
    }
    
    save_dir = "/a0/usr/memory/learned"
    os.makedirs(save_dir, exist_ok=True)
    
    fname = f"{int(datetime.datetime.now().timestamp())}_{task_summary[:30].replace(' ','_')[:30]}.json"
    with open(os.path.join(save_dir, fname), "w") as f:
        json.dump(learning, f, indent=2)
    
    print(f"[Memory] Saved learning: {fname}")
```

## Memory Categories

| Category | Location | What's Stored |
|----------|----------|---------------|
| Task learnings | /a0/usr/memory/learned/ | Solutions, approaches, what worked |
| OSINT results | /a0/usr/workdir/osint/ | Investigation reports per subject |
| Code snippets | /a0/usr/memory/code/ | Useful scripts, API patterns |
| Config notes | /a0/usr/memory/config/ | Service credentials, endpoints, API quirks |
| Error solutions | /a0/usr/memory/fixes/ | How specific errors were resolved |

## When to Use This Skill
- At start of any task that might have been done before
- When asked "remember when...", "last time we...", "have we done..."
- Before writing code that might already exist in workdir
- After completing any multi-step task (save learnings)
