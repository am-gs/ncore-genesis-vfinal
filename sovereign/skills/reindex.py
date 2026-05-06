#!/usr/bin/env python3
import sys, yaml
from pathlib import Path
import chromadb
SKILLS_ROOT = Path.home() / 'sovereign' / 'skills'
client = chromadb.HttpClient(host='localhost', port=8200)
collection = client.get_or_create_collection('skills')
skills=[]
for skill_md in SKILLS_ROOT.rglob('SKILL.md'):
    text=skill_md.read_text(errors='replace')
    meta={}; body=text
    if text.startswith('---'):
        parts=text.split('---',2)
        if len(parts)>=3:
            meta=yaml.safe_load(parts[1]) or {}; body=parts[2].strip()
    skills.append({'id':str(skill_md.parent.relative_to(SKILLS_ROOT)), 'document':f"{meta.get('name','')} {meta.get('description','')} {body[:1000]}", 'metadata':{'name':meta.get('name',''), 'description':meta.get('description',''), 'path':str(skill_md), 'tags':','.join(meta.get('tags',[]) or [])}})
if skills:
    collection.upsert(ids=[s['id'] for s in skills], documents=[s['document'] for s in skills], metadatas=[s['metadata'] for s in skills])
print(f'Indexed {len(skills)} skills into Chroma.')
