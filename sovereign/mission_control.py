import json
import os
import subprocess
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

ROOT = Path('/home/ubuntu/sovereign')
LOGS = ROOT / 'logs'
app = FastAPI(title='Sovereign Mission Control')

SERVICES = {
    'Agent Zero': {'type': 'http', 'url': 'http://127.0.0.1:8090/api/health', 'restart': ['docker', 'restart', 'agent-zero'], 'link': 'http://ncore-v2:8090'},
    'Bifrost': {'type': 'systemd', 'unit': 'sovereign-bifrost', 'url': 'http://127.0.0.1:8000/health', 'link': 'http://127.0.0.1:8000/health'},
    'LLM': {'type': 'systemd', 'unit': 'ollama', 'url': 'http://127.0.0.1:11434/v1/models', 'link': 'http://127.0.0.1:11434/v1/models'},
    'DeerFlow': {'type': 'systemd', 'unit': 'sovereign-deerflow', 'url': 'http://127.0.0.1:2026/api/health', 'link': 'http://127.0.0.1:2026/api/health'},
    'Mem0': {'type': 'systemd', 'unit': 'sovereign-mem0', 'url': 'http://127.0.0.1:8300/health', 'link': 'http://127.0.0.1:8300/health'},
    'Chroma': {'type': 'compose', 'service': 'chroma', 'url': 'http://127.0.0.1:8200/api/v2/heartbeat', 'link': 'http://127.0.0.1:8200/api/v2/heartbeat'},
    'Postgres': {'type': 'compose', 'service': 'postgres', 'tcp': '127.0.0.1:5432'},
    'Redis': {'type': 'compose', 'service': 'redis', 'tcp': '127.0.0.1:6380'},
    'Grafana': {'type': 'compose', 'service': 'grafana', 'url': 'http://127.0.0.1:3001/login', 'link': 'http://127.0.0.1:3001'},
    'Dashboard': {'type': 'systemd', 'unit': 'ncore-dashboard', 'url': 'http://127.0.0.1:3002/', 'link': 'http://127.0.0.1:3002'},
}


def run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


async def http_ok(url: str) -> tuple[bool, float, str]:
    import time
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
        return r.status_code < 500, (time.perf_counter() - started) * 1000, str(r.status_code)
    except Exception as e:
        return False, (time.perf_counter() - started) * 1000, str(e)


@app.get('/api/health')
async def health():
    cards = []
    for name, cfg in SERVICES.items():
        ok = True
        detail = ''
        latency = 0.0
        if 'url' in cfg:
            ok, latency, detail = await http_ok(cfg['url'])
        elif 'unit' in cfg:
            rc, out = run(['systemctl', 'is-active', cfg['unit']])
            ok, detail = rc == 0 and out.strip() == 'active', out
        elif 'service' in cfg:
            rc, out = run(['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '--env-file', str(ROOT / '.env'), 'ps', cfg['service']])
            ok, detail = rc == 0 and 'Up' in out, out.splitlines()[-1] if out else ''
        cards.append({'name': name, 'ok': ok, 'latency_ms': round(latency, 1), 'detail': detail, 'link': cfg.get('link', '')})
    return {'services': cards}


@app.get('/api/runs')
async def runs(limit: int = 30):
    safe_limit = max(1, min(limit, 200))
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f'http://127.0.0.1:8000/runs?limit={safe_limit}')
        return r.json()
    except Exception as e:
        return {'runs': [], 'error': str(e)}


@app.get('/api/logs/{name}')
async def logs(name: str, lines: int = 120):
    allowed = {
        'watchdog': LOGS / 'watchdog.log',
        'bifrost': LOGS / 'bifrost.log',
        'regression': max(LOGS.glob('regression_*.log'), default=LOGS / 'missing.log'),
    }
    path = allowed.get(name)
    if not path or not path.exists():
        return PlainTextResponse('log not found', status_code=404)
    data = path.read_text(errors='replace').splitlines()[-min(lines, 500):]
    return PlainTextResponse('\n'.join(data))


@app.post('/api/restart/{name}')
async def restart(name: str):
    svc = next((v for k, v in SERVICES.items() if k.lower().replace(' ', '-') == name), None)
    if not svc:
        raise HTTPException(404, 'unknown service')
    if 'restart' in svc:
        cmd = svc['restart']
    elif 'unit' in svc:
        cmd = ['sudo', '-n', 'systemctl', 'restart', svc['unit']]
    elif 'service' in svc:
        cmd = ['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), '--env-file', str(ROOT / '.env'), 'restart', svc['service']]
    else:
        raise HTTPException(400, 'service cannot be restarted')
    rc, out = run(cmd, timeout=60)
    return {'ok': rc == 0, 'output': out[-2000:]}


@app.get('/', response_class=HTMLResponse)
async def index():
    return HTML


HTML = r"""
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sovereign Mission Control</title>
<style>
:root{color-scheme:dark;--bg:#070a12;--panel:#0f172a;--muted:#94a3b8;--ok:#22c55e;--bad:#ef4444;--warn:#f59e0b;--text:#e5e7eb;--line:#1e293b;--accent:#8b5cf6}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#1e1b4b,#070a12 42%);font-family:Inter,ui-sans-serif,system-ui;color:var(--text)}header{padding:28px 32px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between}.title{font-size:28px;font-weight:800}.sub{color:var(--muted);margin-top:6px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;padding:24px}.card{background:linear-gradient(180deg,rgba(15,23,42,.94),rgba(15,23,42,.72));border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 10px 35px rgba(0,0,0,.25)}.card h3{margin:0 0 10px}.pill{display:inline-flex;gap:8px;align-items:center;border-radius:999px;padding:5px 10px;font-size:12px;background:#111827;color:var(--muted)}.dot{width:9px;height:9px;border-radius:999px;background:var(--bad)}.ok .dot{background:var(--ok)}button,a.btn{background:#312e81;color:white;border:1px solid #4f46e5;border-radius:10px;padding:8px 10px;text-decoration:none;cursor:pointer;margin-right:6px}button:hover,a.btn:hover{background:#4338ca}.wide{grid-column:1/-1}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}pre{white-space:pre-wrap;background:#020617;border:1px solid var(--line);border-radius:12px;padding:14px;max-height:360px;overflow:auto}.metric{font-size:32px;font-weight:800;color:#c4b5fd}.small{font-size:12px;color:var(--muted)}
</style></head><body><header><div><div class="title">Sovereign Mission Control</div><div class="sub">Local high-compliance agentic stack · localhost/Tailscale only</div></div><button onclick="loadAll()">Refresh</button></header>
<section class="grid" id="services"></section><section class="grid"><div class="card wide"><h3>Recent Task Runs</h3><table><thead><tr><th>Time</th><th>Task</th><th>Provider</th><th>Model</th><th>Fallback</th><th>Latency</th><th>Status</th></tr></thead><tbody id="runs"></tbody></table></div><div class="card wide"><h3>Logs</h3><button onclick="loadLog('watchdog')">Watchdog</button><button onclick="loadLog('regression')">Regression</button><pre id="logs">Select a log.</pre></div></section>
<script>
async function j(u,o){let r=await fetch(u,o);return await r.json()}async function loadHealth(){let d=await j('/api/health');let el=document.getElementById('services');el.innerHTML='';for(let s of d.services){let id=s.name.toLowerCase().replaceAll(' ','-');el.innerHTML+=`<div class="card ${s.ok?'ok':''}"><h3>${s.name}</h3><div class="pill"><span class="dot"></span>${s.ok?'healthy':'unhealthy'} · ${s.latency_ms||0}ms</div><p class="small">${s.detail||''}</p><a class="btn" href="${s.link||'#'}" target="_blank">Open</a><button onclick="restart('${id}')">Restart</button></div>`}}async function loadRuns(){let d=await j('/api/runs');let rows=d.runs||[];document.getElementById('runs').innerHTML=rows.map(r=>`<tr><td>${new Date((r.ts||0)*1000).toLocaleString()}</td><td>${r.task_id||''}</td><td>${r.provider||''}</td><td>${r.model||''}</td><td>${r.fallback_reason||''}${r.refusal_intercepted?' ⚑':''}</td><td>${r.latency_ms||''}ms</td><td>${r.completion_status||''}</td></tr>`).join('')}async function loadLog(n){let r=await fetch('/api/logs/'+n);document.getElementById('logs').textContent=await r.text()}async function restart(n){let d=await j('/api/restart/'+n,{method:'POST'});alert((d.ok?'Restarted':'Failed')+'\n'+(d.output||''));loadAll()}function loadAll(){loadHealth();loadRuns()}loadAll();setInterval(loadAll,10000)
</script></body></html>
"""
