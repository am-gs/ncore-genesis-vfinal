#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'
	'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOVEREIGN_HOME="${SOVEREIGN_HOME:-/home/ubuntu/sovereign}"
USER_NAME="${SOVEREIGN_USER:-ubuntu}"

log(){ printf '[sovereign-start] %s\n' "$*"; }

# ── Docker Compose services ──────────────────────────────────────────
log "starting docker-compose services (Postgres, Redis, Chroma, Prometheus, Grafana)"
cd "$SOVEREIGN_HOME"
docker compose --env-file .env up -d postgres redis chroma prometheus grafana || {
    log "warning: some compose services may have failed to start"
}

# ── Bifrost v2 ───────────────────────────────────────────────────────
log "starting Bifrost v2"
if systemctl is-active --quiet sovereign-bifrost 2>/dev/null; then
    log "sovereign-bifrost already active"
else
    sudo systemctl daemon-reload
    sudo systemctl enable --now sovereign-bifrost
fi

# ── Mission Control ──────────────────────────────────────────────────
log "starting Mission Control"
if systemctl is-active --quiet sovereign-mission-control 2>/dev/null; then
    log "sovereign-mission-control already active"
else
    sudo systemctl daemon-reload
    sudo systemctl enable --now sovereign-mission-control
fi

# ── Wait for services ──────────────────────────────────────────────
log "waiting for services to come online..."
_wait_http() {
    local url="$1" label="$2" timeout_s="${3:-60}"
    local start now
    start="$(date +%s)"
    while true; do
        if curl -fsS "$url" >/dev/null 2>&1; then
            log "$label ready"
            return 0
        fi
        now="$(date +%s)"
        if (( now - start >= timeout_s )); then
            log "warning: timed out waiting for $label at $url"
            return 1
        fi
        sleep 1
    done
}

_wait_http "http://127.0.0.1:8000/health" "Bifrost v2" 60
_wait_http "http://127.0.0.1:3004/api/health" "Mission Control" 60
_wait_http "http://127.0.0.1:8200/api/v2/heartbeat" "Chroma" 30 || true

# ── Run validation ───────────────────────────────────────────────────
log "running architecture validation"
cd "$REPO_ROOT"
python3 scripts/validate_architecture.py || {
    log "warning: architecture validation had failures — check logs above"
}

# ── Startup summary ──────────────────────────────────────────────────
print_summary() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           SOVEREIGN STACK STARTUP SUMMARY                        ║"
    echo "╠══════════════════════════════════════════════════════════════════╣"

    # Compose services
    local compose_status
    compose_status="$(cd "$SOVEREIGN_HOME" && docker compose --env-file .env ps --format 'table {{.Name}}\t{{.Service}}\t{{.Status}}' 2>/dev/null || true)"
    if [[ -n "$compose_status" ]]; then
        echo "║ Docker Compose Services:                                           ║"
        while IFS= read -r line; do
            printf "║   %-62s ║\n" "$line"
        done <<<"$compose_status"
    fi

    # Systemd services
    echo "║ Systemd Services:                                                ║"
    for svc in sovereign-bifrost sovereign-mission-control; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            printf "║   %-20s %-38s ║\n" "$svc" "✓ active"
        else
            printf "║   %-20s %-38s ║\n" "$svc" "✗ inactive"
        fi
    done

    # HTTP endpoints
    echo "║ Endpoints:                                                       ║"
    for spec in \
        "Bifrost v2       http://127.0.0.1:8000/health" \
        "Mission Control  http://127.0.0.1:3004/api/health" \
        "Grafana          http://127.0.0.1:3001/login" \
        "Chroma           http://127.0.0.1:8200/api/v2/heartbeat" \
        "Prometheus       http://127.0.0.1:9090"; do
        name="${spec%% *}"
        url="${spec#* }"
        code="$(curl -sS -m 3 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || true)"
        if [[ "$code" == "200" ]]; then
            printf "║   %-20s %-38s ║\n" "$name" "✓ $code"
        else
            printf "║   %-20s %-38s ║\n" "$name" "✗ $code"
        fi
    done

    # Ollama check
    if curl -fsS "http://127.0.0.1:11434" >/dev/null 2>&1 || ss -tln | grep -q ':11434 '; then
        printf "║   %-20s %-38s ║\n" "Ollama" "⚠ running (should not be)"
    else
        printf "║   %-20s %-38s ║\n" "Ollama" "✓ not running"
    fi

    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
}

print_summary

log "sovereign stack startup complete"
