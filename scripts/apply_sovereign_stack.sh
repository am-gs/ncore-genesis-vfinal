#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOVEREIGN_HOME="${SOVEREIGN_HOME:-/home/ubuntu/sovereign}"
USER_NAME="${SOVEREIGN_USER:-ubuntu}"
LOG_DIR="$SOVEREIGN_HOME/logs"

log(){ printf '[sovereign-apply] %s\n' "$*"; }
install_file(){ install -D -m "${3:-0644}" "$1" "$2"; }

log "installing sovereign files to $SOVEREIGN_HOME"
mkdir -p "$SOVEREIGN_HOME" "$LOG_DIR" "$SOVEREIGN_HOME/bifrost" "$SOVEREIGN_HOME/supervisor" "$SOVEREIGN_HOME/skills"
rsync -a --exclude '.env' "$REPO_ROOT/sovereign/" "$SOVEREIGN_HOME/"
chmod 644 "$SOVEREIGN_HOME/prometheus.yml" 2>/dev/null || true
chmod +x "$SOVEREIGN_HOME/supervisor/watchdog.py" "$SOVEREIGN_HOME/skills/reindex.py" 2>/dev/null || true

if [[ ! -f "$SOVEREIGN_HOME/.env" ]]; then
  umask 077
  cat > "$SOVEREIGN_HOME/.env" <<ENV
POSTGRES_PASSWORD=$(openssl rand -hex 24)
OPENAI_API_KEY=sovereign
ANTHROPIC_API_KEY=sovereign
GRAFANA_PASSWORD=$(openssl rand -hex 16)
ENV
fi

if [[ ! -x "$SOVEREIGN_HOME/venv/bin/python" ]]; then
  python3 -m venv "$SOVEREIGN_HOME/venv"
fi
"$SOVEREIGN_HOME/venv/bin/pip" install -q --upgrade pip
"$SOVEREIGN_HOME/venv/bin/pip" install -q fastapi uvicorn httpx requests chromadb pyyaml

log "installing systemd units"
sudo tee /etc/systemd/system/sovereign-bifrost.service >/dev/null <<UNIT
[Unit]
Description=Sovereign Bifrost Gateway Shim
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SOVEREIGN_HOME
Environment=SOVEREIGN_MONTHLY_CAP=38.0
ExecStart=$SOVEREIGN_HOME/venv/bin/uvicorn bifrost_proxy:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/sovereign-deerflow.service >/dev/null <<UNIT
[Unit]
Description=Sovereign DeerFlow Shim
After=network.target sovereign-bifrost.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SOVEREIGN_HOME
ExecStart=$SOVEREIGN_HOME/venv/bin/uvicorn deerflow_shim:app --host 127.0.0.1 --port 2026
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/sovereign-mem0.service >/dev/null <<UNIT
[Unit]
Description=Sovereign Mem0 Shim
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SOVEREIGN_HOME
ExecStart=$SOVEREIGN_HOME/venv/bin/uvicorn mem0_shim:app --host 127.0.0.1 --port 8300
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/sovereign-mission-control.service >/dev/null <<UNIT
[Unit]
Description=Sovereign Mission Control
After=network.target sovereign-bifrost.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SOVEREIGN_HOME
ExecStart=$SOVEREIGN_HOME/venv/bin/uvicorn mission_control:app --host 127.0.0.1 --port 3004
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo tee /etc/systemd/system/sovereign-watchdog.service >/dev/null <<UNIT
[Unit]
Description=Sovereign Stack Watchdog
After=docker.service sovereign-llm.service sovereign-bifrost.service
Requires=docker.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SOVEREIGN_HOME
ExecStart=$SOVEREIGN_HOME/venv/bin/python $SOVEREIGN_HOME/supervisor/watchdog.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now sovereign-bifrost sovereign-deerflow sovereign-mem0 sovereign-mission-control sovereign-watchdog
sudo systemctl restart sovereign-bifrost sovereign-deerflow sovereign-mem0 sovereign-mission-control sovereign-watchdog

log "starting compose services"
cd "$SOVEREIGN_HOME"
docker compose --env-file .env up -d postgres redis chroma prometheus grafana

log "warnings for broad legacy binds"
ss -tlnp | grep -E '0\.0\.0\.0:(8080|8090|8888|11235)' || true
log "done"
