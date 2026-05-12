import sys, re, json

path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()

old = '''    try:
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

new = '''    try:
        raw = await llm.chat(messages, temperature=0.1, max_tokens=1500)
        text = raw.strip()
        plan = None

        # 1. Try fenced code blocks (last one first — usually the final answer)
        for m in reversed(list(re.finditer(r'```(?:json)?\\s*(.*?)\\s*```', text, re.S))):
            try:
                cand = m.group(1).strip().strip("`").strip()
                if cand.startswith("json"):
                    cand = cand[4:].strip()
                parsed = json.loads(cand)
                if isinstance(parsed, list):
                    plan = parsed
                    break
                if isinstance(parsed, dict) and "steps" in parsed:
                    plan = parsed["steps"]
                    break
            except Exception:
                continue

        # 2. Try outermost bare JSON array or object
        if plan is None:
            for pat in [r'(\\[.*\\])', r'(\\{.*\\})']:
                m = re.search(pat, text, re.S)
                if m:
                    try:
                        parsed = json.loads(m.group(1))
                        if isinstance(parsed, list):
                            plan = parsed
                            break
                        if isinstance(parsed, dict) and "steps" in parsed:
                            plan = parsed["steps"]
                            break
                    except Exception:
                        continue

        if plan is None:
            plan = []
            state["error"] = "Planner: could not extract JSON plan from model response"
    except Exception as exc:
        plan = []
        state["error"] = f"Planner error: {exc}"
        # error is non-fatal: fallback plan generated below'''

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('Fixed planner node v2')
else:
    print('Old pattern not found')
    idx = content.find('Planner error')
    if idx != -1:
        print(content[idx-200:idx+200])
