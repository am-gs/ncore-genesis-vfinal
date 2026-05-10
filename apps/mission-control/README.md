# Mission Control — Manus-Powered Sovereign Dashboard

Next.js frontend for the sovereign AI orchestration stack. Serves the Manus execution environment, terminal, and task stream UI.

## Quick Start

### Dev Mode (no nginx)
```bash
cd apps/mission-control
cp .env.local.example .env.local
pnpm install
pnpm dev        # http://localhost:3000
```
In dev mode the frontend proxies API calls via `NEXT_PUBLIC_API_URL`. See `.env.local.example` for the required variables.

### Production / Full Stack
```bash
# One-shot deploy on the sovereign VM
./scripts/deploy_manus.sh
```
This installs nginx, builds the static export, starts systemd services, and brings up docker compose.

## Architecture

```
┌─────────────────┐
│   Browser       │
│  (localhost:80) │
└────────┬────────┘
         │
    ┌────┴────┐
    │  nginx  │  SPA fallback + API proxy
    └────┬────┘
         │
    ┌────┴────┬────────────┐
    │         │            │
┌───┴───┐ ┌───┴────┐ ┌───┴────┐
│ /api/ │ │/bifrost│ │  /ws/  │
│ 3004  │ │  8000  │ │  3004  │
└───┬───┘ └───┬────┘ └───┬────┘
    │         │          │
┌───┴─────────┴──────────┴──────┐
│      Mission Control          │  FastAPI (port 3004)
│  - Task orchestration         │
│  - SSE stream (/api/tasks/...)│
│  - Terminal WebSocket         │
└───────────────────────────────┘
         │
    ┌────┴────┐
    │ Docker  │  Postgres, Redis, Chroma, Grafana, Prometheus
    └─────────┘
```

## Manus Execution Flow

1. User submits a task via the dashboard (`POST /api/tasks`).
2. Mission Control pushes the task to the Manus runtime.
3. Browser subscribes to `GET /api/tasks/stream` (SSE) for real-time updates.
4. Manus spins up a headless browser (Playwright) or shell session as needed.
5. Results stream back via SSE; terminal output arrives via WebSocket (`/ws/`).

## Terminal Usage

The in-dashboard terminal connects over WebSocket to Mission Control. Supported commands:
- `bash` — standard shell inside the sovereign environment
- `python` — REPL with access to the same `PYTHONPATH`
- Task-specific contextual commands injected by the Manus runtime

## Browser Automation Notes

- Playwright Chromium is installed by `deploy_manus.sh`.
- Browser sessions run headless inside the VM; VNC/screenshots can be exposed via Mission Control endpoints.
- `bifrost` (port 8000) proxies LLM calls; the Manus agent routes reasoning through it for cost-capped inference.

## Environment Variables

Copy `.env.local.example` to `.env.local` and adjust for your environment:
- `NEXT_PUBLIC_API_URL` — Mission Control FastAPI backend
- `NEXT_PUBLIC_DEERFLOW_URL` — DeerFlow shim endpoint
- `NEXT_PUBLIC_WS_URL` — WebSocket base URL

> **Note:** `output: 'export'` in `next.config.ts` means Next.js generates a static site (`dist/`). Rewrites are not available in static-export mode; production routing is handled by nginx. Dev mode uses `NEXT_PUBLIC_API_URL` directly in the client.
