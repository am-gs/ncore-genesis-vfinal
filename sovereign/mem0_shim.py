import json, time, os
from pathlib import Path
from fastapi import FastAPI, Request
app=FastAPI(title='Sovereign Mem0 Shim')
STORE=Path('/home/ubuntu/sovereign/mem0/memories.jsonl')
STORE.parent.mkdir(parents=True, exist_ok=True)
@app.get('/health')
async def health(): return {'status':'ok'}
@app.post('/memories')
async def memories(request: Request):
    data=await request.json()
    with STORE.open('a') as f: f.write(json.dumps({'ts':time.time(), **data})+'\n')
    return {'status':'ok'}
@app.get('/memories')
async def list_memories():
    if not STORE.exists(): return {'memories':[]}
    return {'memories':[json.loads(x) for x in STORE.read_text().splitlines()[-100:] if x.strip()]}
