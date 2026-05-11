#!/usr/bin/env bash
set -euo pipefail

NCORE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$NCORE_DIR/core/venv/bin"
ENV_FILE="$NCORE_DIR/core/.env"

echo "================================================================"
echo "  NCore Genesis v7.6 — Production Deploy"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================"

# ── Pre-flight checks ─────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    echo "[ERROR] Missing $ENV_FILE — copy from .env.example and fill in API keys"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "[ERROR] Docker not installed. Run deploy-ncore-vfinal.sh first."
    exit 1
fi

source "$ENV_FILE" 2>/dev/null || true

echo ""
echo "[Phase 1/5] Deploying Agent Zero v1.7..."
echo "─────────────────────────────────────────"
if docker ps -a --format '{{.Names}}' | grep -q agent-zero; then
    echo "[INFO] Stopping existing Agent Zero container..."
    docker stop agent-zero 2>/dev/null || true
    docker rm agent-zero 2>/dev/null || true
fi

docker pull agent0ai/agent-zero 2>/dev/null
docker run -d --name agent-zero \
    -p 8090:80 \
    -v ~/agent-zero-data:/a0/usr \
    --restart unless-stopped \
    agent0ai/agent-zero && echo "[OK] Agent Zero v1.7 running on :8090" || echo "[WARN] Agent Zero deployment failed"

echo ""
echo "[Phase 2/5] Installing ZeroClaw..."
echo "───────────────────────────────────"
if ! command -v zeroclaw &>/dev/null; then
    curl -fsSL https://install.zeroclaw.net | bash 2>/dev/null && echo "[OK] ZeroClaw installed" || echo "[WARN] ZeroClaw install failed — optional component"
else
    echo "[OK] ZeroClaw already installed"
fi

echo ""
echo "[Phase 3/5] Installing Python dependencies..."
echo "──────────────────────────────────────────────"
"$VENV/pip" install -q -r "$NCORE_DIR/core/requirements.txt" 2>&1 | tail -3
echo "[OK] Python deps installed"
"$VENV/pip" install -q litellm gptcache redisvl 2>&1 | tail -2
echo "[OK] LiteLLM gateway + semantic cache installed"

echo ""
echo "[Phase 3.5/5] Installing core skill stack..."
echo "─────────────────────────────────────────────"
if [ -f "$NCORE_DIR/core/preinstalled_skills.sh" ]; then
    chmod +x "$NCORE_DIR/core/preinstalled_skills.sh"
    bash "$NCORE_DIR/core/preinstalled_skills.sh" || echo "[WARN] Some skills failed to install — will be discovered at runtime"
else
    echo "[SKIP] preinstalled_skills.sh not found"
fi

echo ""
echo "[Phase 4/5] Installing systemd services..."
echo "────────────────────────────────────────────"

# Gateway
sudo tee /etc/systemd/system/ncore-gateway.service > /dev/null << SEOF
[Unit]
Description=NCore Genesis v7.6 — Gateway
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$NCORE_DIR/core
EnvironmentFile=$ENV_FILE
Environment="PATH=$VENV:$PATH"
Environment="LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2:$NCORE_DIR/libs/force_nodelay.so"
Environment="OMP_NUM_THREADS=1"
Environment="OPENBLAS_NUM_THREADS=1"
ExecStart=$VENV/python -m uvicorn orchestrator:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SEOF

# Watchdog
sudo tee /etc/systemd/system/ncore-watchdog.service > /dev/null << SEOF
[Unit]
Description=NCore Genesis v7.6 — Self-Healing Watchdog
After=ncore-gateway.service
Wants=ncore-gateway.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$NCORE_DIR/core
EnvironmentFile=$ENV_FILE
Environment="PATH=$VENV:$PATH"
ExecStart=$VENV/python watchdog.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SEOF

# Prompt Enhancer
sudo tee /etc/systemd/system/ncore-enhancer.service > /dev/null << SEOF
[Unit]
Description=NCore Genesis v7.6 — Prompt Enhancer
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$NCORE_DIR/core
EnvironmentFile=$ENV_FILE
Environment="PATH=$VENV:$PATH"
ExecStart=$VENV/python prompt_enhancer.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SEOF

# Dashboard (optional standalone — primary access is via gateway at :8080/dashboard)
sudo tee /etc/systemd/system/ncore-dashboard.service > /dev/null << SEOF
[Unit]
Description=NCore Genesis v7.6 — Mission Control Dashboard
After=ncore-gateway.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$NCORE_DIR/dashboard
ExecStart=/usr/bin/python3 -m http.server 3002 --bind 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SEOF

sudo systemctl daemon-reload
sudo systemctl enable ncore-gateway ncore-watchdog ncore-enhancer ncore-dashboard 2>/dev/null
sudo systemctl restart ncore-gateway
sudo systemctl restart ncore-watchdog
sudo systemctl restart ncore-enhancer
sudo systemctl restart ncore-dashboard
echo "[OK] All 4 systemd services enabled and started"

echo ""
echo "[Phase 5/5] Waiting for services to stabilize..."
echo "──────────────────────────────────────────────────"
sleep 8

echo ""
echo "[Phase 5/5] Running health checks..."
echo "─────────────────────────────────────"

# Check each service
for svc in ncore-gateway ncore-watchdog ncore-enhancer ncore-dashboard; do
    if systemctl is-active --quiet "$svc"; then
        echo "  ✅ $svc — running"
    else
        echo "  ❌ $svc — FAILED (check: journalctl -u $svc -n 20)"
    fi
done

# Check Agent Zero
if docker ps --format '{{.Names}}' | grep -q agent-zero; then
    echo "  ✅ agent-zero — running (Docker)"
else
    echo "  ❌ agent-zero — not running"
fi

# Gateway health
echo ""
HEALTH=$(curl -sf http://127.0.0.1:8080/health 2>/dev/null || echo '{"status":"error"}')
echo "  Gateway: $HEALTH"

# Quick routing test
echo ""
echo "  Quick routing test (GPT-OSS 20B free)..."
RESULT=$(curl -sf -X POST http://127.0.0.1:8080/run \
    -d '{"task":"ping"}' \
    -H 'Content-Type: application/json' 2>/dev/null || echo '{"route":{"tier":"error"}}')
TIER=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['route']['tier'])" 2>/dev/null || echo "error")
MODEL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['route']['model'])" 2>/dev/null || echo "error")
echo "  Routed to: $TIER → $MODEL"

echo ""
echo "================================================================"
echo "  NCore Genesis v7.6 — Production Deploy Complete"
echo ""
echo "  Services:"
echo "    Gateway:        http://127.0.0.1:8080"
echo "    Dashboard:      http://127.0.0.1:8080/dashboard (primary) | http://127.0.0.1:3002 (standalone)"
echo "    Prompt Enhancer: http://127.0.0.1:8081"
echo "    Agent Zero:     http://127.0.0.1:8090"
echo ""
echo "  Via Tailscale:"
echo "    ssh ncore"
echo "    http://ncore-v2:8080/dashboard"
echo "    http://ncore-v2:8090  (agent zero)"
echo ""
echo "  Logs:"
echo "    journalctl -u ncore-gateway -f"
echo "    journalctl -u ncore-watchdog -f"
echo "    docker logs agent-zero -f"
echo "================================================================"
