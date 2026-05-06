import httpx
from fastapi import FastAPI, Request
app=FastAPI(title='Sovereign DeerFlow Shim')
@app.get('/api/health')
async def health(): return {'status':'ok','mode':'shim'}
@app.post('/api/chat')
async def chat(request: Request):
    data=await request.json()
    messages=data.get('messages') or []
    payload={'model':'qwen3-8b','messages':messages,'max_tokens':data.get('max_tokens',512)}
    async with httpx.AsyncClient(timeout=180) as client:
        r=await client.post('http://127.0.0.1:8000/v1/chat/completions', json=payload, headers={'X-Task-ID':data.get('thread_id','deerflow')})
    out=r.json()
    content=out.get('choices',[{}])[0].get('message',{}).get('content','')
    return {'content':content,'raw':out}
