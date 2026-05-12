import sys, re

path = sys.argv[1] if len(sys.argv) > 1 else '/home/ncore-genesis-vfinal/core/langgraph_swarm.py'
with open(path, 'r') as f:
    content = f.read()

old = '''    try:
        raw = await llm.chat(messages, temperature=0.3, max_tokens=1200)
        cleaned = raw.strip().strip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        plan = json.loads(cleaned)
        if isinstance(plan, dict) and "steps" in plan:
            plan = plan["steps"]
        if not isinstance(plan, list):
            plan = []
    except Exception as exc:
        plan = []
        state["error"] = f"Planner error: {exc}"
        # error is non-fatal: fallback plan generated below'''

new = '''    try:
        raw = await llm.chat(messages, temperature=0.3, max_tokens=2000)
        # Reasoning models (Kimi K2.6) emit thinking blocks; strip them
        text = raw.strip()
        text = re.sub(r'\\[Thinking\\].*?\\[/Thinking\\]', '', text, flags=re.S)
        text = re.sub(r'\\[推理过程\\].*?\\[/推理过程\\]', '', text, flags=re.S)
        # Extract JSON from markdown fences
        m = re.search(r'```(?:json)?\\s*(\\[.*?\\]|\\{.*?\\})\\s*```', text, re.S)
        if m:
            cleaned = m.group(1)
        else:
            cleaned = text.strip().strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            arr_start = cleaned.find('[')
            obj_start = cleaned.find('{')
            start = min(x for x in [arr_start, obj_start] if x != -1)
            arr_end = cleaned.rfind(']')
            obj_end = cleaned.rfind('}')
            end = max(x for x in [arr_end, obj_end] if x != -1)
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start:end+1]
        plan = json.loads(cleaned)
        if isinstance(plan, dict) and "steps" in plan:
            plan = plan["steps"]
        if not isinstance(plan, list):
            plan = []
    except Exception as exc:
        plan = []
        state["error"] = f"Planner error: {exc}"
        # error is non-fatal: fallback plan generated below'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('Fixed planner node')
else:
    print('Old pattern not found; checking content around planner...')
    idx = content.find('planner_node')
    if idx != -1:
        print(content[idx:idx+1200])
