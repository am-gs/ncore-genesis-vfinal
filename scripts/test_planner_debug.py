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
        'Return ONLY valid JSON array — no markdown fences, no thinking blocks.'
    )
    prompt = (
        'Long-horizon analysis task:\n'
        '1. Count lines in /home/ubuntu/sovereign/mission_control.py\n'
        '2. Find top 5 function names via grep | sort | uniq -c | sort -rn | head -5\n'
        '3. Write a disk-usage script to /tmp/metrics_collector.py\n'
        '4. Run the script and capture output\n'
        '5. Return a JSON summary with: loc_count, top_5_functions list, disk_usage_mb, script_output\n'
        'Return the JSON summary as the final result.'
    )
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': f'Task: {prompt}\n\nPlan:'},
    ]
    raw = await llm.chat(messages, temperature=0.1, max_tokens=2000)
    print('=== RAW RESPONSE (first 3000 chars) ===')
    print(raw[:3000])
    print('=== END RAW ===')

    text = raw.strip()
    plan = None
    for m in reversed(list(re.finditer(r'```(?:json)?\s*(.*?)\s*```', text, re.S))):
        try:
            cand = m.group(1).strip().strip('`').strip()
            if cand.startswith('json'):
                cand = cand[4:].strip()
            parsed = json.loads(cand)
            if isinstance(parsed, list):
                plan = parsed
                print(f'\n[EXTRACT] Fenced JSON array: {len(plan)} steps')
                break
            if isinstance(parsed, dict) and 'steps' in parsed:
                plan = parsed['steps']
                print(f'\n[EXTRACT] Fenced JSON dict.steps: {len(plan)} steps')
                break
        except Exception as e:
            print(f'[EXTRACT] Fenced attempt failed: {e}')
            continue
    if plan is None:
        for pat in [r'(\[.*\])', r'(\{.*\})']:
            m = re.search(pat, text, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                    if isinstance(parsed, list):
                        plan = parsed
                        print(f'\n[EXTRACT] Bare JSON array: {len(plan)} steps')
                        break
                    if isinstance(parsed, dict) and 'steps' in parsed:
                        plan = parsed['steps']
                        print(f'\n[EXTRACT] Bare JSON dict.steps: {len(plan)} steps')
                        break
                except Exception as e:
                    print(f'[EXTRACT] Bare attempt failed: {e}')
                    continue
    if plan is None:
        print('\n[EXTRACT] FAILED — no JSON found')
    else:
        print(f'\n[PLAN] {json.dumps(plan, indent=2)[:500]}')

asyncio.run(test())
