---
name: task-router
description: Intelligent task routing. Classifies tasks by type and routes to the optimal model, profile, and strategy. Automatically decomposes complex multi-step tasks into parallelizable subtasks. Use when a task needs smart execution planning.
triggers: route task, select model, complex task, multi-step task, task planning, how to approach, what model
---

# Intelligent Task Router

## Purpose
Before executing a complex task, classify it and determine the optimal execution strategy — model, profile, tool selection, and parallelization.

## Task Classification

Analyze the task and determine its type:

```python
def classify_task(task):
    t = task.lower()
    if any(w in t for w in ["hack", "osint", "pentest", "scan", "nmap", "enumerate", "investigate", "dossier", "skip trace"]):
        return "security"
    elif any(w in t for w in ["code", "python", "javascript", "debug", "function", "script", "build", "implement"]):
        return "code"
    elif any(w in t for w in ["research", "find", "search", "analyze", "summarize", "compare", "explain"]):
        return "research"
    elif any(w in t for w in ["video", "image", "generate", "face swap", "comfyui", "vast"]):
        return "media"
    elif any(w in t for w in ["browse", "click", "form", "website", "navigate", "register", "login"]):
        return "browser"
    elif any(w in t for w in ["email", "send", "schedule", "remind", "calendar", "slack"]):
        return "automation"
    else:
        return "general"
```

## Routing Table

| Task Type | Profile | Tools | Notes |
|-----------|---------|-------|-------|
| security | hacker | maigret, sherlock, nmap, spiderfoot | Use skip-tracer for people investigation |
| code | developer | code_execution, memory | Test-fix loop, save solutions to memory |
| research | researcher | browser, memory | Use memory-enhance skill first |
| media | operator | nsfw-video-generator, gpu-image-generator | Delegate to operator profile |
| browser | operator | nodriver, imapclient | Use stealth-accounts or browser-broadcast skill |
| automation | hacker | python, composio | Use available MCP integrations |
| general | hacker | all | Default capable profile |

## Execution Patterns

### Pattern 1: Sequential Subtasks
For tasks with dependencies:
```
1. Gather information → 2. Process it → 3. Generate output
```
Execute each step, verify completion, then proceed.

### Pattern 2: Parallel Subtasks
For independent components, use call_subordinate with multiple agents simultaneously. Example for OSINT:
- Agent A: username enumeration (maigret/sherlock)
- Agent B: email investigation (holehe)
- Agent C: public records browser search
- Merge results into unified report

### Pattern 3: Iterative Refinement
For tasks where quality matters:
1. Generate initial output
2. Evaluate against requirements
3. If insufficient, refine with specific improvements
4. Repeat until criteria met

## Complex Task Decomposition

For any task with 3+ distinct steps:
1. List all required subtasks
2. Identify dependencies between them
3. Group independent tasks for parallel execution
4. Create a named context/workdir for the task
5. Save intermediate results as files

Example: "Research competitor X and create a report"
- Subtask A: Web research on company history, products, pricing
- Subtask B: Social media / LinkedIn analysis  
- Subtask C: GitHub presence and tech stack
- Subtask D (depends on A+B+C): Compile findings into structured report

## Always Remember
- Check /a0/usr/skills/ FIRST — there may be an existing skill for the exact task
- Save all task outputs to /a0/usr/workdir/ with meaningful filenames
- Update memory with solutions that took >5 minutes to figure out
- Use subordinate agents for tasks that are parallelizable
