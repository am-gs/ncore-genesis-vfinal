#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-ncore-v2}"
TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}"
TAILSCALE_ADVERTISE_TAGS="${TAILSCALE_ADVERTISE_TAGS:-}"

log() { printf '[ncore-tailscale] %s\n' "$*"; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }; }

if ! command -v tailscale >/dev/null 2>&1; then
  log "installing tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

need_cmd sudo
need_cmd tailscale
need_cmd curl

up_args=(--ssh --hostname "$TAILSCALE_HOSTNAME" --accept-dns=false)
if [[ -n "$TAILSCALE_AUTHKEY" ]]; then
  up_args+=(--authkey "$TAILSCALE_AUTHKEY")
fi
if [[ -n "$TAILSCALE_ADVERTISE_TAGS" ]]; then
  up_args+=(--advertise-tags "$TAILSCALE_ADVERTISE_TAGS")
fi

log "joining tailscale"
set +e
up_output="$(sudo tailscale up "${up_args[@]}" 2>&1)"
up_rc=$?
set -e
if (( up_rc != 0 )); then
  sanitized="$(sed -E 's/tskey-[A-Za-z0-9_-]+/[REDACTED]/g' <<<"$up_output")"
  printf '%s\n' "$sanitized" >&2
  if grep -qi 'require --advertise-tags' <<<"$up_output"; then
    echo "TAILSCALE_ADVERTISE_TAGS is required for this OAuth auth key, e.g. TAILSCALE_ADVERTISE_TAGS=tag:ncore" >&2
  fi
  exit "$up_rc"
fi

if ! command -v socat >/dev/null 2>&1; then
  log "installing socat"
  sudo apt-get update -qq
  sudo apt-get install -y -qq socat
fi

log "installing tailnet-only dashboard proxies"
sudo tee /usr/local/sbin/ncore-tailnet-proxies >/dev/null <<'SCRIPT'
#!/usr/bin/env bash
set -Eeuo pipefail

TSIP="$(tailscale ip -4 | head -n1)"
test -n "$TSIP"
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT

listen() {
  local port="$1"
  local target="$2"
  local listeners
  listeners="$(ss -tlnH | awk '{print $4}' | grep -E "(^|:|\])${port}$" || true)"
  if grep -Eq "(^0\.0\.0\.0:|^\*:|^\[::\]:|^:::)${port}$" <<<"$listeners"; then
    echo "port ${port} is wildcard-bound and may be publicly reachable; refusing to continue" >&2
    return 1
  fi
  if grep -Fxq "${TSIP}:${port}" <<<"$listeners"; then
    echo "port ${port} already bound on Tailscale IP; skipping proxy"
    return 0
  fi
  socat "TCP-LISTEN:${port},bind=${TSIP},fork,reuseaddr" "TCP:${target}" &
  pids+=("$!")
}

listen 3004 127.0.0.1:3004
listen 8090 127.0.0.1:8090
listen 3002 127.0.0.1:3002
listen 3001 127.0.0.1:3001
listen 8000 127.0.0.1:8000
listen 2026 127.0.0.1:2026
listen 8300 127.0.0.1:8300

wait
SCRIPT
sudo chmod 0755 /usr/local/sbin/ncore-tailnet-proxies

sudo tee /etc/systemd/system/ncore-tailnet-proxies.service >/dev/null <<'UNIT'
[Unit]
Description=NCore dashboard proxies on Tailscale IP only
After=tailscaled.service network-online.target sovereign-mission-control.service sovereign-bifrost.service sovereign-deerflow.service sovereign-mem0.service
Requires=tailscaled.service

[Service]
Type=simple
ExecStart=/usr/local/sbin/ncore-tailnet-proxies
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now ncore-tailnet-proxies
sleep 2
TSIP="$(tailscale ip -4 | head -n1)"

log "tailscale ready: $TSIP"
printf 'Mission Control: http://%s:3004/\n' "$TSIP"
printf 'Agent Zero:      http://%s:8090/\n' "$TSIP"
printf 'Legacy dash:     http://%s:3002/\n' "$TSIP"
printf 'Grafana:         http://%s:3001/\n' "$TSIP"
printf 'Bifrost:         http://%s:8000/health\n' "$TSIP"
printf 'DeerFlow:        http://%s:2026/api/health\n' "$TSIP"
printf 'Mem0:            http://%s:8300/health\n' "$TSIP"
