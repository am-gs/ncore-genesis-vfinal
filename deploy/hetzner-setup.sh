#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  NLLM.ING — Hetzner CX21 Cloud Deploy Script ($50/month budget)
# ═══════════════════════════════════════════════════════════════════
#  VPS: Hetzner CX21 (2 vCPU, 8 GB RAM, 80 GB NVMe) = ~$6/mo
#  Domain: Cloudflare (free tier)
#  Dashboard: Vercel Hobby (free tier)
#  SSL: Let's Encrypt (free)
#  Total infra: ~$6/mo + LLM API usage ~$10-30/mo
# ═══════════════════════════════════════════════════════════════════
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="/tmp/nllm-deploy-$(date +%Y%m%d-%H%M%S).log"

log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
warn() { echo "[$(date '+%H:%M:%S')] WARN: $*" | tee -a "$LOG_FILE"; }
fail() { echo "[$(date '+%H:%M:%S')] FAIL: $*" | tee -a "$LOG_FILE"; exit 1; }

# ── 0. Pre-flight checks ────────────────────────────────────────────
log "=== NLLM.ING Cloud Deploy ==="
log "Log: $LOG_FILE"

if [[ $EUID -ne 0 ]]; then
    fail "Run as root: sudo ./deploy/hetzner-setup.sh"
fi

if [[ ! -f "$REPO_ROOT/.env" ]]; then
    fail "Missing $REPO_ROOT/.env — copy from .env.example and fill in API keys"
fi

# ── 1. System update + Docker install ─────────────────────────────
log "[1/7] Updating system and installing Docker..."
apt-get update -qq
apt-get install -y -qq \
    apt-transport-https ca-certificates curl gnupg lsb-release \
    git wget ufw certbot python3-certbot-nginx \
    unzip jq 2>&1 | tee -a "$LOG_FILE"

if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "${SUDO_USER:-$USER}" 2>/dev/null || true
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

DOCKER_CMD="docker compose"
if ! $DOCKER_CMD version &>/dev/null; then
    DOCKER_CMD="docker-compose"
fi

# ── 2. Firewall ────────────────────────────────────────────────────
log "[2/7] Configuring UFW..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
# Internal only: 3001 (backend), 8080 (bifrost), 5432 (postgres), 6379 (redis)
ufw allow from 127.0.0.1 to any port 3001
ufw allow from 127.0.0.1 to any port 8080
ufw --force enable
log "UFF configured"

# ── 3. SSL certificates ───────────────────────────────────────────
log "[3/7] Setting up SSL..."
DOMAIN="${NLLM_DOMAIN:-}"
if [[ -n "$DOMAIN" ]]; then
    if [[ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]]; then
        certbot certonly --standalone --non-interactive --agree-tos \
            --email "${NLLM_EMAIL:-admin@$DOMAIN}" -d "$DOMAIN"
    fi
    mkdir -p "$REPO_ROOT/deploy/ssl"
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$REPO_ROOT/deploy/ssl/"
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$REPO_ROOT/deploy/ssl/"
    chmod 600 "$REPO_ROOT/deploy/ssl/privkey.pem"
    log "SSL certs ready for $DOMAIN"
else
    warn "No NLLM_DOMAIN set — generating self-signed cert"
    mkdir -p "$REPO_ROOT/deploy/ssl"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$REPO_ROOT/deploy/ssl/privkey.pem" \
        -out "$REPO_ROOT/deploy/ssl/fullchain.pem" \
        -subj "/CN=nllm.local/O=NLLM.ING" 2>/dev/null
    log "Self-signed cert generated"
fi

# ── 4. Build and deploy ────────────────────────────────────────────
log "[4/7] Building and deploying NLLM.ING..."
cd "$REPO_ROOT"

# Pull latest images
$DOCKER_CMD pull maximhq/bifrost:latest
$DOCKER_CMD pull postgres:17-alpine
$DOCKER_CMD pull redis:7-alpine

# Build backend
$DOCKER_CMD build -f Dockerfile.backend -t nllm-backend:latest .

# Start stack
$DOCKER_CMD down 2>/dev/null || true
$DOCKER_CMD up -d --wait

# ── 5. Health checks ───────────────────────────────────────────────
log "[5/7] Health checks..."
sleep 10

HEALTH_URLS=(
    "http://localhost:3001/health"
    "http://localhost:8080/health"
)
for url in "${HEALTH_URLS[@]}"; do
    for i in {1..5}; do
        if curl -fs "$url" &>/dev/null; then
            log "  ✓ $url"
            break
        fi
        sleep 3
    done
done

# ── 6. Auto-renewal cron ──────────────────────────────────────────
log "[6/7] Setting up certbot auto-renewal..."
if ! crontab -l 2>/dev/null | grep -q certbot; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && $DOCKER_CMD restart nginx") | crontab -
    log "Certbot auto-renewal configured"
fi

# ── 7. Summary ────────────────────────────────────────────────────
log "[7/7] Deploy complete!"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  NLLM.ING is LIVE"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "  Backend API:    http://localhost:3001"
echo "  Bifrost Gateway: http://localhost:8080"
echo "  Dashboard:      Deploy to Vercel with:"
echo "                  cd apps/nllm-dashboard && vercel --prod"
echo ""
echo "  Docker status:"
$DOCKER_CMD ps

echo ""
echo "  Next steps:"
echo "    1. Deploy dashboard: cd apps/nllm-dashboard && vercel --prod"
echo "    2. Point domain DNS to this server's IP"
echo "    3. Set NLLM_DOMAIN in .env and re-run SSL setup"
echo "    4. Monitor: docker compose logs -f backend"
echo ""
echo "  Budget: ~$6/mo VPS + ~$10-30/mo LLM APIs (with Bifrost caching)"
echo "═══════════════════════════════════════════════════════════════════"
