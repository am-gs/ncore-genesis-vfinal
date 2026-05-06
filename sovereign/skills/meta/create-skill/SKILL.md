---
name: create-new-skill
description: Write a new SKILL.md bundle when no existing skill covers the current task.
version: 1.0.0
tags: [meta, skill-creation, self-improvement]
---
# Create New Skill

## Purpose
Create a reusable skill under `~/sovereign/skills/custom/` and reindex the skill corpus.

## Steps
1. Pick a kebab-case skill name.
2. Create `~/sovereign/skills/custom/<skill>/scripts`.
3. Write `SKILL.md` with YAML frontmatter, purpose, numbered steps, scripts, and one example.
4. Make helper scripts executable.
5. Run `python3 ~/sovereign/skills/reindex.py`.
6. Log the skill creation through Mem0 at `http://localhost:8300/memories`.
