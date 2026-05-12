import asyncio, json, re, sys
sys.path.insert(0, '/home/ubuntu/sovereign')
sys.path.insert(0, '/home/ubuntu/sovereign/core')
from core.langgraph_swarm import get_bifrost_llm

async def test():
    llm = get_bifrost_llm()
    system = (
        'You are the Sovereign Planner. Given a task, emit a JSON array of plan steps. '
        'Each step has: id (string), description (string), tool (one of terminal_execute, '
        'file_write, code_execute_python, spawn_subagent), input (object with args). '
        'Return ONLY valid JSON array — no markdown fences, no thinking blocks, no explanation before or after.'
    )
    prompt = 'Plan steps for: count lines in a file, find top 5 functions, write a script, run it, return JSON summary'
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': f'Task: {prompt}\n\nPlan:'},
    ]
    raw = await llm.chat(messages, temperature=0.0, max_tokens=1500)
    print('=== LAST 2000 chars ===')
    print(raw[-2000:])
    print('=== END ===')

    text = raw.strip()
    plan = None

    all_fenced = list(re.finditer(r'```(?:json)?\s*(.*?)\s*```', text, re.S))
    if all_fenced:
        for m in reversed(all_fenced):
            try:
                cand = m.group(1).strip().strip('`').strip()
                if cand.startswith('json'):
                    cand = cand[4:].strip()
                parsed = json.loads(cand)
                if isinstance(parsed, list):
                    plan = parsed
                    print(f'\n[EXTRACT] Fenced JSON array (last): {len(plan)} steps')
                    break
            except:
                continue

    if plan is None:
        for start_idx in reversed([m.start() for m in re.finditer(r'\[', text)]):
            for end_idx in [m.end() for m in re.finditer(r'\]', text) if m.end() > start_idx]:
                if end_idx <= start_idx:
                    continue
                try:
                    candidate = text[start_idx:end_idx]
                    if candidate.count('[') != candidate.count(']'):
                        continue
                    parsed = json.loads(candidate)
                    if isinstance(parsed, list):
                        plan = parsed
                        print(f'\n[EXTRACT] Bare JSON array (end-scan): {len(plan)} steps')
                        break
                except:
                    continue
            if plan:
                break

    if plan is None:
        print('\n[EXTRACT] FAILED')
    else:
        print(f'\n[PLAN] {json.dumps(plan, indent=2)[:500]}')

asyncio.run(test())
