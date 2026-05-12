#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  NLLM.ING Sovereign Stack — Production Starter
#  Single-command boot: Bifrost v2 + Mission Control + Dashboard
#  No systemd required. Runs in any Linux/VM/container.
# ═══════════════════════════════════════════════════════════════════

set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

# ── Defaults ───────────────────────────────────────────────────────
BIFROST_PORT="${BIFROST_PORT:-8001}"
MC_PORT="${MC_PORT:-3004}"
DASHBOARD_PORT="${DASHBOARD_PORT:-3000}"
SOVEREIGN_HOME="${SOVEREIGN_HOME:-/home/ubuntu/sovereign}"

# ── Load .env ──────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs) 2>/dev/null || true
fi

log(){ printf '[\033[1;36mproduction\033[0m] %s\n' "$*"; }

# ── Ensure directories ───────────────────────────────────────────
mkdir -p "$SOVEREIGN_HOME/logs" "$SOVEREIGN_HOME/bifrost"

# ── Dependency check ─────────────────────────────────────────────
log "checking dependencies..."
command -v python3 >/dev/null 2>&1 || { log "error: python3 not found"; exit 1; }
command -v pnpm >/dev/null 2>&1 || { log "warning: pnpm not found — dashboard must be pre-built"; }

# ── Kill stale processes ───────────────────────────────────────────
log "cleaning stale processes..."
pkill -f 'uvicorn sovereign.bifrost_proxy' 2>/dev/null || true
pkill -f 'uvicorn sovereign.mission_control' 2>/dev/null || true
pkill -f 'python3.*production_server.py' 2>/dev/null || true
sleep 2

# ── Build dashboard if needed ────────────────────────────────────
DASHBOARD_DIST="${REPO_ROOT}/apps/mission-control/dist"
if [[ ! -d "$DASHBOARD_DIST" ]]; then
    if command -v pnpm >/dev/null 2>&1; then
        log "building Mission Control dashboard..."
        cd "${REPO_ROOT}/apps/mission-control"
        pnpm install --frozen-lockfile 2>/dev/null || pnpm install
        pnpm build
    else
        log "error: dashboard not built and pnpm unavailable"
        exit 1
    fi
fi

# ── Start Bifrost v2 ───────────────────────────────────────────────
log "starting Bifrost v2 on :${BIFROST_PORT}..."
export BIFROST_URL="http://127.0.0.1:${BIFROST_PORT}"
export SOVEREIGN_BUDGET_DB="${SOVEREIGN_HOME}/bifrost/budget.sqlite3"
export SOVEREIGN_MONTHLY_CAP="${SOVEREIGN_MONTHLY_CAP:-38.0}"
cd "$REPO_ROOT"
nohup python3 -m uvicorn sovereign.bifrost_proxy:app \
    --host 127.0.0.1 --port "${BIFROST_PORT}" \
    --no-access-log \
    > "${SOVEREIGN_HOME}/logs/bifrost.log" 2>&1 &
BIFROST_PID=$!

# ── Wait for Bifrost ───────────────────────────────────────────────
log "waiting for Bifrost..."
for i in {1..30}; do
    if curl -fsS "http://127.0.0.1:${BIFROST_PORT}/health" >/dev/null 2>&1; then
        log "Bifrost ready"
        break
    fi
    sleep 1
done

# ── Start Mission Control ──────────────────────────────────────────
log "starting Mission Control on :${MC_PORT}..."
export MISSION_CONTROL_URL="http://127.0.0.1:${MC_PORT}"
export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/sovereign"
nohup python3 -m uvicorn sovereign.mission_control:app \
    --host 127.0.0.1 --port "${MC_PORT}" \
    --no-access-log \
    > "${SOVEREIGN_HOME}/logs/mission_control.log" 2>&1 &
MC_PID=$!

# ── Wait for Mission Control ───────────────────────────────────────
log "waiting for Mission Control..."
for i in {1..30}; do
    if curl -fsS "http://127.0.0.1:${MC_PORT}/api/health" >/dev/null 2>&1; then
        log "Mission Control ready"
        break
    fi
    sleep 1
done

# ── Start unified dashboard server ─────────────────────────────────
log "starting unified dashboard server on :${DASHBOARD_PORT}..."
nohup python3 "${REPO_ROOT}/scripts/production_server.py" \
    --static-dir "$DASHBOARD_DIST" \
    --api-port "${MC_PORT}" \
    --bifrost-port "${BIFROST_PORT}" \
    --port "${DASHBOARD_PORT}" \
    > "${SOVEREIGN_HOME}/logs/dashboard.log" 2>&1 &
DASH_PID=$!

# ── Wait for dashboard ───────────────────────────────────────────
log "waiting for dashboard..."
for i in {1..15}; do
    if curl -fsS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${DASHBOARD_PORT}/" 2>/dev/null | grep -q '200\|301\|302'; then
        log "dashboard ready"
        break
    fi
    sleep 1
done

# ── Health check ───────────────────────────────────────────────────
log "running health checks..."
BF_STATUS=$(curl -fsS "http://127.0.0.1:${BIFROST_PORT}/health" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'))" || echo "error")
BF_PROVIDERS=$(curl -fsS "http://127.0.0.1:${BIFROST_PORT}/health" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('available_providers',[])))" || echo "0")
MC_STATUS=$(curl -fsS "http://127.0.0.1:${MC_PORT}/api/health" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('ok' if [s for s in d.get('services',[]) if s['name']=='Bifrost' and s['ok']] else 'degraded')" 2>/dev/null || echo "error")
DASH_STATUS=$(curl -fsS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${DASHBOARD_PORT}/" 2>/dev/null || echo "error")

# ── Quick prompt test ──────────────────────────────────────────────
log "testing inference with a live prompt..."
TEST_RESULT=$(curl -fsS "http://127.0.0.1:${BIFROST_PORT}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{"model":"openrouter/free","messages":[{"role":"user","content":"Count from 1 to 5"}],"max_tokens":32}' 2>/dev/null | \
    python3 -c "import json,sys; d=json.load(sys.stdin); c=d['choices'][0]['message'].get('content','') if 'choices' in d else str(d); print(c.strip()[:60])" || echo "FAILED")

# ── Summary ────────────────────────────────────────────────────────
cat <<EOF

╔══════════════════════════════════════════════════════════════════╗
║           SOVEREIGN STACK — PRODUCTION READY                     ║
╠══════════════════════════════════════════════════════════════════╣
║ Dashboard:   http://127.0.0.1:${DASHBOARD_PORT}/                    ║
║ Bifrost:     http://127.0.0.1:${BIFROST_PORT}/health               ║
║ Mission Ctrl http://127.0.0.1:${MC_PORT}/api/health               ║
╠══════════════════════════════════════════════════════════════════╣
║ Health:                                                          ║
║   Bifrost v2      ${BF_STATUS} (${BF_PROVIDERS} providers configured)              ║
║   Mission Control ${MC_STATUS}                                     ║
║   Dashboard       ${DASH_STATUS}                                   ║
╠══════════════════════════════════════════════════════════════════╣
║ Prompt test: "Count from 1 to 5"                                 ║
║   → ${TEST_RESULT}
╠══════════════════════════════════════════════════════════════════╣
║ PIDs:  Bifrost=${BIFROST_PID}  MC=${MC_PID}  Dashboard=${DASH_PID}         ║
╚══════════════════════════════════════════════════════════════════╝

Commands:
  curl http://127.0.0.1:${BIFROST_PORT}/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"openrouter/free","messages":[{"role":"user","content":"Hello"}]}'

  curl http://127.0.0.1:${MC_PORT}/api/tasks \
    -H "Content-Type: application/json" \
    -d '{"name":"Demo","description":"Test task","agent":"manus"}'

Logs: ${SOVEREIGN_HOME}/logs/
EOF

# ── Save PID file ──────────────────────────────────────────────────
cat > "${SOVEREIGN_HOME}/sovereign-stack.pid" <<EOF
BIFROST_PID=${BIFROST_PID}
MC_PID=${MC_PID}
DASH_PID=${DASH_PID}
EOF

log "all services started. Press Ctrl+C to keep them running in background."
wait
