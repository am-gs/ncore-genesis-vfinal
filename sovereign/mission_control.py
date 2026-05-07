     1	#!/usr/bin/env python3
     2	"""
     3	Sovereign Mission Control — Cognitive Execution Control Plane.
     4	
     5	Designed to be compatible with langchain-ai/deepagents SDK patterns:
     6	- Planning tool: plan_steps field maps to Deep Agents' planning
     7	- Subagent spawning: /spawn endpoint maps to Deep Agents' subagent spawning
     8	- Filesystem backend: artifacts stored as JSON in the task store
     9	- Task state machine maps to LangGraph node states
    10	"""
    11	
    12	import asyncio
    13	import json
    14	import os
    15	import random
    16	import subprocess
    17	import time
    18	import uuid
    19	from datetime import datetime, timezone
    20	from enum import Enum
    21	from pathlib import Path
    22	from typing import List, Optional
    23	
    24	import httpx
    25	from fastapi import FastAPI, HTTPException, Query
    26	from fastapi.middleware.cors import CORSMiddleware
    27	from fastapi.responses import HTMLResponse, PlainTextResponse
    28	
    29	ROOT = Path('/home/ubuntu/sovereign')
    30	LOGS = ROOT / 'logs'
    31	TASKS_FILE = ROOT / 'tasks.json'
    32	
    33	app = FastAPI(title='Sovereign Mission Control')
    34	app.add_middleware(
    35	    CORSMiddleware,
    36	    allow_origins=['*'],
    37	    allow_credentials=True,
    38	    allow_methods=['*'],
    39	    allow_headers=['*'],
    40	)
    41	
    42	SERVICES = {
    43	    'Agent Zero': {'type': 'http', 'url': 'http://127.0.0.1:8090/api/health', 'restart': ['docker', 'restart', 'agent-zero'], 'link': 'http://ncore-v2:8090'},
    44	    'Bifrost': {'type': 'systemd', 'unit': 'sovereign-bifrost', 'url': 'http://127.0.0.1:8000/health', 'link': 'http://127.0.0.1:8000/health'},
    45	    'LLM': {'type': 'systemd', 'unit': 'ollama', 'url': 'http://127.0.0.1:11434/v1/models', 'link': 'http://127.0.0.1:11434/v1/models'},
    46	    'DeerFlow': {'type': 'systemd', 'unit': 'sovereign-deerflow', 'url': 'http://127.0.0.1:2026/api/health', 'link': 'http://127.0.0.1:2026/api/health'},
    47	    'Mem0': {'type': 'systemd', 'unit': 'sovereign-mem0', 'url': 'http://127.0.0.1:8300/health', 'link': 'http://127.0.0.1:8300/health'},
    48	    'Chroma': {'type': 'compose', 'service': 'chroma', 'url': 'http://127.0.0.1:8200/api/v2/heartbeat', 'link': 'http://127.0.0.1:8200/api/v2/heartbeat'},
    49	    'Postgres': {'type': 'compose', 'service': 'postgres', 'tcp': '127.0.0.1:5432'},
    50	    'Redis': {'type': 'compose', 'service': 'redis', 'tcp': '127.0.0.1:6380'},
    51	    'Grafana': {'type': 'compose', 'service': 'grafana', 'url': 'http://127.0.0.1:3001/login', 'link': 'http://127.0.0.1:3001'},
    52	    'Dashboard': {'type': 'systemd', 'unit': 'ncore-dashboard', 'url': 'http://127.0.0.1:3002/', 'link': 'http://127.0.0.1:3002'},
    53	}
    54	
    55	# ---------------------------------------------------------------------------
    56	# Task State Machine
    57	# ---------------------------------------------------------------------------
    58	
    59	class TaskState(str, Enum):
    60	    PENDING = "pending"
    61	    PLANNING = "planning"
    62	    RUNNING = "running"
    63	    PAUSED = "paused"
    64	    COMPLETED = "completed"
    65	    FAILED = "failed"
    66	    RETRYING = "retrying"
    67	    CANCELLED = "cancelled"
    68	
    69	
    70	def iso_now() -> str:
    71	    return datetime.now(timezone.utc).isoformat()
    72	
    73	
    74	def new_task_dict(
    75	    name: str,
    76	    description: str,
    77	    agent: str,
    78	    status: TaskState = TaskState.PLANNING,
    79	    plan_steps: Optional[List[dict]] = None,
    80	    parent_id: Optional[str] = None,
    81	    branch_from: Optional[str] = None,
    82	) -> dict:
    83	    now = iso_now()
    84	    plan = []
    85	    if plan_steps:
    86	        for step in plan_steps:
    87	            plan.append({
    88	                "id": str(uuid.uuid4()),
    89	                "description": step.get("description", ""),
    90	                "status": TaskState.PENDING,
    91	                "agent": step.get("agent") or agent,
    92	                "depends_on": step.get("depends_on", []),
    93	                "output": None,
    94	            })
    95	    return {
    96	        "id": str(uuid.uuid4()),
    97	        "name": name,
    98	        "description": description,
    99	        "status": status,
   100	        "agent": agent,
   101	        "progress": 0.0,
   102	        "created_at": now,
   103	        "updated_at": now,
   104	        "plan": plan,
   105	        "subtasks": [],
   106	        "parent_id": parent_id,
   107	        "branch_from": branch_from,
   108	        "latency_ms": 0,
   109	        "retries": 0,
   110	        "error": None,
   111	        "artifacts": [],
   112	        "memory_refs": [],
   113	    }
   114	
   115	
   116	# In-memory store + persistence
   117	_tasks: dict[str, dict] = {}
   118	_simulation_tasks: dict[str, asyncio.Task] = {}
   119	_lock = asyncio.Lock()
   120	
   121	
   122	def _load_tasks() -> None:
   123	    global _tasks
   124	    if TASKS_FILE.exists():
   125	        try:
   126	            with open(TASKS_FILE, "r") as f:
   127	                data = json.load(f)
   128	            _tasks = {t["id"]: t for t in data}
   129	        except Exception:
   130	            _tasks = {}
   131	    else:
   132	        _tasks = {}
   133	
   134	
   135	def _save_tasks() -> None:
   136	    try:
   137	        with open(TASKS_FILE, "w") as f:
   138	            json.dump(list(_tasks.values()), f, indent=2)
   139	    except Exception:
   140	        pass
   141	
   142	
   143	_load_tasks()
   144	
   145	
   146	# ---------------------------------------------------------------------------
   147	# Simulation
   148	# ---------------------------------------------------------------------------
   149	
   150	async def _simulate_task(task_id: str) -> None:
   151	    while True:
   152	        await asyncio.sleep(random.uniform(2.0, 5.0))
   153	        async with _lock:
   154	            task = _tasks.get(task_id)
   155	            if not task or task["status"] != TaskState.RUNNING:
   156	                return
   157	            # Random failure (10% chance per tick)
   158	            if random.random() < 0.10:
   159	                task["status"] = TaskState.FAILED
   160	                task["error"] = "Simulated agent failure during execution"
   161	                task["updated_at"] = iso_now()
   162	                _save_tasks()
   163	                return
   164	            # Increment progress
   165	            inc = random.uniform(10.0, 25.0)
   166	            task["progress"] = min(100.0, task["progress"] + inc)
   167	            if task["progress"] >= 100.0:
   168	                task["status"] = TaskState.COMPLETED
   169	                task["progress"] = 100.0
   170	            task["updated_at"] = iso_now()
   171	            _save_tasks()
   172	            if task["status"] == TaskState.COMPLETED:
   173	                return
   174	
   175	
   176	def _start_simulation(task_id: str) -> None:
   177	    if task_id in _simulation_tasks:
   178	        _simulation_tasks[task_id].cancel()
   179	    _simulation_tasks[task_id] = asyncio.create_task(_simulate_task(task_id))
   180	
   181	
   182	def _stop_simulation(task_id: str) -> None:
   183	    t = _simulation_tasks.pop(task_id, None)
   184	    if t:
   185	        t.cancel()
   186	
   187	
   188	# ---------------------------------------------------------------------------
   189	# Helpers
   190	# ---------------------------------------------------------------------------
   191	
   192	def _resolve_task(task_id: str) -> dict:
   193	    task = _tasks.get(task_id)
   194	    if not task:
   195	        raise HTTPException(404, "task not found")
   196	    return task
   197	
   198	
   199	def _cascade_cancel(task_id: str) -> None:
   200	    task = _tasks.get(task_id)
   201	    if not task:
   202	        return
   203	    task["status"] = TaskState.CANCELLED
   204	    task["updated_at"] = iso_now()
   205	    _stop_simulation(task_id)
   206	    for sub_id in task.get("subtasks", []):
   207	        _cascade_cancel(sub_id)
   208	
   209	
   210	def _task_to_json(task: dict, depth: int = 0) -> dict:
   211	    out = dict(task)
   212	    if depth < 3:
   213	        out["subtasks_detail"] = []
   214	        for sid in task.get("subtasks", []):
   215	            sub = _tasks.get(sid)
   216	            if sub:
   217	                out["subtasks_detail"].append(_task_to_json(sub, depth + 1))
   218	    return out
   219	
   220	
   221	def _build_tree(task: dict) -> dict:
   222	    node = dict(task)
   223	    node["children"] = []
   224	    for sid in task.get("subtasks", []):
   225	        sub = _tasks.get(sid)
   226	        if sub:
   227	            node["children"].append(_build_tree(sub))
   228	    return node
   229	
   230	
   231	def _get_branches(task_id: str) -> List[dict]:
   232	    results = []
   233	    for t in _tasks.values():
   234	        if t.get("branch_from") == task_id:
   235	            results.append(t)
   236	    return results
   237	
   238	
   239	def _decompose_plan_steps(parent_id: str, steps: List[dict], agent: str) -> List[str]:
   240	    sub_ids = []
   241	    for step in steps:
   242	        child = new_task_dict(
   243	            name=step.get("description", "Subtask"),
   244	            description=step.get("description", ""),
   245	            agent=step.get("agent") or agent,
   246	            status=TaskState.PENDING,
   247	            parent_id=parent_id,
   248	        )
   249	        if step.get("sub_steps"):
   250	            child["subtasks"] = _decompose_plan_steps(child["id"], step["sub_steps"], agent)
   251	        _tasks[child["id"]] = child
   252	        sub_ids.append(child["id"])
   253	    return sub_ids
   254	
   255	
   256	# ---------------------------------------------------------------------------
   257	# Existing endpoints
   258	# ---------------------------------------------------------------------------
   259	
   260	def run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
   261	    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
   262	    return p.returncode, (p.stdout + p.stderr).strip()
   263	
   264	
   265	async def http_ok(url: str) -> tuple[bool, float, str]:
   266	    started = time.perf_counter()
   267	    try:
   268	        async with httpx.AsyncClient(timeout=5) as client:
   269	            r = await client.get(url)
   270	        return r.status_code < 500, (time.perf_counter() - started) * 1000, str(r.status_code)
   271	    except Exception as e:
   272	        return False, (time.perf_counter() - started) * 1000, str(e)
   273	
   274	
   275	@app.get('/api/health')
   276	async def health():
   277	    cards = []
   278	    for name, cfg in SERVICES.items():
   279	        ok = True
   280	        detail = ''
   281	        latency = 0.0
   282	        if 'url' in cfg:
   283	            ok, latency, detail = await http_ok(cfg['url'])
   284	        elif 'unit' in cfg:
   285	            rc, out = run(['systemctl', 'is-active', cfg['unit']])
   286	            ok, detail = rc == 0 and out.strip() == 'active', out
   287	        elif 'service' in cfg:
   288	            rc, out = run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '--env-file', str(ROOT / '.env'), 'ps', cfg['service']])
   289	            ok, detail = rc == 0 and 'Up' in out, out.splitlines()[-1] if out else ''
   290	        cards.append({'name': name, 'ok': ok, 'latency_ms': round(latency, 1), 'detail': detail, 'link': cfg.get('link', '')})
   291	    return {'services': cards}
   292	
   293	
   294	@app.get('/api/runs')
   295	async def runs(limit: int = 30):
   296	    safe_limit = max(1, min(limit, 200))
   297	    try:
   298	        async with httpx.AsyncClient(timeout=5) as client:
   299	            r = await client.get(f'http://127.0.0.1:8000/runs?limit={safe_limit}')
   300	        return r.json()
   301	    except Exception as e:
   302	        return {'runs': [], 'error': str(e)}
   303	
   304	
   305	@app.get('/api/logs/{name}')
   306	async def logs(name: str, lines: int = 120):
   307	    allowed = {
   308	        'watchdog': LOGS / 'watchdog.log',
   309	        'bifrost': LOGS / 'bifrost.log',
   310	        'regression': max(LOGS.glob('regression_*.log'), default=LOGS / 'missing.log'),
   311	    }
   312	    path = allowed.get(name)
   313	    if not path or not path.exists():
   314	        return PlainTextResponse('log not found', status_code=404)
   315	    data = path.read_text(errors='replace').splitlines()[-min(lines, 500):]
   316	    return PlainTextResponse('\n'.join(data))
   317	
   318	
   319	@app.post('/api/restart/{name}')
   320	async def restart(name: str):
   321	    svc = next((v for k, v in SERVICES.items() if k.lower().replace(' ', '-') == name), None)
   322	    if not svc:
   323	        raise HTTPException(404, 'unknown service')
   324	    if 'restart' in svc:
   325	        cmd = svc['restart']
   326	    elif 'unit' in svc:
   327	        cmd = ['sudo', '-n', 'systemctl', 'restart', svc['unit']]
   328	    elif 'service' in svc:
   329	        cmd = ['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '--env-file', str(ROOT / '.env'), 'restart', svc['service']]
   330	    else:
   331	        raise HTTPException(400, 'service cannot be restarted')
   332	    rc, out = run(cmd, timeout=60)
   333	    return {'ok': rc == 0, 'output': out[-2000:]}
   334	
   335	
   336	@app.get('/', response_class=HTMLResponse)
   337	async def index():
   338	    return HTML
   339	
   340	
   341	# ---------------------------------------------------------------------------
   342	# Task Execution Control Plane endpoints
   343	# ---------------------------------------------------------------------------
   344	
   345	@app.get("/api/tasks")
   346	async def list_tasks(status: Optional[TaskState] = None, limit: int = Query(100)):
   347	    async with _lock:
   348	        items = list(_tasks.values())
   349	        if status:
   350	            items = [t for t in items if t["status"] == status]
   351	        items = items[:max(1, min(limit, 1000))]
   352	        return {"tasks": items}
   353	
   354	
   355	@app.post("/api/tasks")
   356	async def create_task(body: dict):
   357	    name = body.get("name")
   358	    description = body.get("description", "")
   359	    agent = body.get("agent", "default")
   360	    plan_steps = body.get("plan_steps")
   361	    if not name:
   362	        raise HTTPException(400, "name is required")
   363	
   364	    async with _lock:
   365	        task = new_task_dict(name, description, agent, status=TaskState.PLANNING, plan_steps=plan_steps)
   366	        if plan_steps and len(plan_steps) > 1:
   367	            task["subtasks"] = _decompose_plan_steps(task["id"], plan_steps, agent)
   368	        _tasks[task["id"]] = task
   369	        _save_tasks()
   370	
   371	    # Transition planning -> running -> start simulation
   372	    async with _lock:
   373	        task["status"] = TaskState.RUNNING
   374	        task["updated_at"] = iso_now()
   375	        _save_tasks()
   376	    _start_simulation(task["id"])
   377	
   378	    return task
   379	
   380	
   381	@app.get("/api/tasks/{task_id}")
   382	async def get_task(task_id: str):
   383	    async with _lock:
   384	        task = _resolve_task(task_id)
   385	        return _task_to_json(task)
   386	
   387	
   388	@app.post("/api/tasks/{task_id}/spawn")
   389	async def spawn_subtask(task_id: str, body: dict):
   390	    parent = _resolve_task(task_id)
   391	    name = body.get("name")
   392	    description = body.get("description", "")
   393	    agent = body.get("agent", parent.get("agent", "default"))
   394	    if not name:
   395	        raise HTTPException(400, "name is required")
   396	
   397	    async with _lock:
   398	        child = new_task_dict(name, description, agent, status=TaskState.PLANNING, parent_id=task_id)
   399	        child["status"] = TaskState.RUNNING
   400	        child["updated_at"] = iso_now()
   401	        _tasks[child["id"]] = child
   402	        parent["subtasks"].append(child["id"])
   403	        parent["updated_at"] = iso_now()
   404	        _save_tasks()
   405	
   406	    _start_simulation(child["id"])
   407	    return child
   408	
   409	
   410	@app.post("/api/tasks/{task_id}/branch")
   411	async def branch_task(task_id: str, body: dict):
   412	    source = _resolve_task(task_id)
   413	    name = body.get("name")
   414	    description = body.get("description", "")
   415	    from_step_id = body.get("from_step_id")
   416	    if not name:
   417	        raise HTTPException(400, "name is required")
   418	
   419	    # Copy relevant plan steps from the source task
   420	    copied_plan = []
   421	    for step in source.get("plan", []):
   422	        if not from_step_id or step["id"] == from_step_id:
   423	            copied_plan.append({
   424	                "id": str(uuid.uuid4()),
   425	                "description": step["description"],
   426	                "status": TaskState.PENDING,
   427	                "agent": step.get("agent"),
   428	                "depends_on": [],
   429	                "output": None,
   430	            })
   431	            if from_step_id:
   432	                break
   433	
   434	    async with _lock:
   435	        task = new_task_dict(
   436	            name=name,
   437	            description=description,
   438	            agent=source.get("agent", "default"),
   439	            status=TaskState.RUNNING,
   440	            plan_steps=copied_plan,
   441	            branch_from=task_id,
   442	        )
   443	        _tasks[task["id"]] = task
   444	        _save_tasks()
   445	
   446	    _start_simulation(task["id"])
   447	    return task
   448	
   449	
   450	@app.post("/api/tasks/{task_id}/pause")
   451	async def pause_task(task_id: str):
   452	    async with _lock:
   453	        task = _resolve_task(task_id)
   454	        if task["status"] != TaskState.RUNNING:
   455	            raise HTTPException(400, "task is not running")
   456	        task["status"] = TaskState.PAUSED
   457	        task["updated_at"] = iso_now()
   458	        _save_tasks()
   459	    _stop_simulation(task_id)
   460	    return task
   461	
   462	
   463	@app.post("/api/tasks/{task_id}/resume")
   464	async def resume_task(task_id: str):
   465	    async with _lock:
   466	        task = _resolve_task(task_id)
   467	        if task["status"] != TaskState.PAUSED:
   468	            raise HTTPException(400, "task is not paused")
   469	        task["status"] = TaskState.RUNNING
   470	        task["updated_at"] = iso_now()
   471	        _save_tasks()
   472	    _start_simulation(task_id)
   473	    return task
   474	
   475	
   476	@app.post("/api/tasks/{task_id}/retry")
   477	async def retry_task(task_id: str):
   478	    async with _lock:
   479	        task = _resolve_task(task_id)
   480	        task["retries"] += 1
   481	        task["status"] = TaskState.RETRYING
   482	        task["error"] = None
   483	        task["updated_at"] = iso_now()
   484	        _save_tasks()
   485	
   486	    async def _delayed_resume():
   487	        await asyncio.sleep(2.0)
   488	        async with _lock:
   489	            t = _tasks.get(task_id)
   490	            if t and t["status"] == TaskState.RETRYING:
   491	                t["status"] = TaskState.RUNNING
   492	                t["updated_at"] = iso_now()
   493	                _save_tasks()
   494	        _start_simulation(task_id)
   495	
   496	    asyncio.create_task(_delayed_resume())
   497	    return task
   498	
   499	
   500	@app.post("/api/tasks/{task_id}/cancel")
   501	async def cancel_task(task_id: str):
   502	    async with _lock:
   503	        _resolve_task(task_id)
   504	        _cascade_cancel(task_id)
   505	        _save_tasks()
   506	    return _tasks.get(task_id)
   507	
   508	
   509	@app.get("/api/tasks/{task_id}/tree")
   510	async def get_tree(task_id: str):
   511	    async with _lock:
   512	        task = _resolve_task(task_id)
   513	        return _build_tree(task)
   514	
   515	
   516	@app.get("/api/tasks/{task_id}/trajectory")
   517	async def get_trajectory(task_id: str):
   518	    async with _lock:
   519	        _resolve_task(task_id)
   520	        branches = _get_branches(task_id)
   521	        return {"task_id": task_id, "branches": branches}
   522	
   523	
   524	HTML = r"""
   525	<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
   526	<title>Sovereign Mission Control</title>
   527	<style>
   528	:root{color-scheme:dark;--bg:#070a12;--panel:#0f172a;--muted:#94a3b8;--ok:#22c55e;--bad:#ef4444;--warn:#f59e0b;--text:#e5e7eb;--line:#1e293b;--accent:#8b5cf6}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#1e1b4b,#070a12 42%);font-family:Inter,ui-sans-serif,system-ui;color:var(--text)}header{padding:28px 32px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}.title{font-size:28px;font-weight:800}.sub{color:var(--muted);margin-top:6px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;padding:24px}.card{background:linear-gradient(180deg,rgba(15,23,42,.94),rgba(15,23,42,.72));border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 10px 35px rgba(0,0,0,.25)}.card h3{margin:0 0 10px}.pill{display:inline-flex;gap:8px;align-items:center;border-radius:999px;padding:5px 10px;font-size:12px;background:#111827;color:var(--muted)}.dot{width:9px;height:9px;border-radius:999px;background:var(--bad)}.ok .dot{background:var(--ok)}button,a.btn{background:#312e81;color:white;border:1px solid #4f46e5;border-radius:10px;padding:8px 10px;text-decoration:none;cursor:pointer;margin-right:6px}button:hover,a.btn:hover{background:#4338ca}.wide{grid-column:1/-1}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}pre{white-space:pre-wrap;background:#020617;border:1px solid var(--line);border-radius:12px;padding:14px;max-height:360px;overflow:auto}.metric{font-size:32px;font-weight:800;color:#c4b5fd}.small{font-size:12px;color:var(--muted)}
   529	</style></head><body><header><div><div class="title">Sovereign Mission Control</div><div class="sub">Local high-compliance agentic stack · localhost/Tailscale only</div></div><button onclick="loadAll()">Refresh</button></header>
   530	<section class="grid" id="services"></section><section class="grid"><div class="card wide"><h3>Recent Task Runs</h3><table><thead><tr><th>Time</th><th>Task</th><th>Provider</th><th>Model</th><th>Fallback</th><th>Latency</th><th>Status</th></tr></thead><tbody id="runs"></tbody></table></div><div class="card wide"><h3>Logs</h3><button onclick="loadLog('watchdog')">Watchdog</button><button onclick="loadLog('regression')">Regression</button><pre id="logs">Select a log.</pre></div></section>
   531	<script>
   532	async function j(u,o){let r=await fetch(u,o);return await r.json()}async function loadHealth(){let d=await j('/api/health');let el=document.getElementById('services');el.innerHTML='';for(let s of d.services){let id=s.name.toLowerCase().replaceAll(' ','-');el.innerHTML+=`<div class="card ${s.ok?'ok':''}"><h3>${s.name}</h3><div class="pill"><span class="dot"></span>${s.ok?'healthy':'unhealthy'} · ${s.latency_ms||0}ms</div><p class="small">${s.detail||''}</p><a class="btn" href="${s.link||'#'}" target="_blank">Open</a><button onclick="restart('${id}')">Restart</button></div>`}}async function loadRuns(){let d=await j('/api/runs');let rows=d.runs||[];document.getElementById('runs').innerHTML=rows.map(r=>`<tr><td>${new Date((r.ts||0)*1000).toLocaleString()}</td><td>${r.task_id||''}</td><td>${r.provider||''}</td><td>${r.model||''}</td><td>${r.fallback_reason||''}${r.refusal_intercepted?' ⚑':''}</td><td>${r.latency_ms||''}ms</td><td>${r.completion_status||''}</td></tr>`).join('')}async function loadLog(n){let r=await fetch('/api/logs/'+n);document.getElementById('logs').textContent=await r.text()}async function restart(n){let d=await j('/api/restart/'+n,{method:'POST'});alert((d.ok?'Restarted':'Failed')+'\n'+(d.output||''));loadAll()}function loadAll(){loadHealth();loadRuns()}loadAll();setInterval(loadAll,10000)
   533	</script></body></html>
   534	"""
   535	