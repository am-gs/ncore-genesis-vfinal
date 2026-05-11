#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

NCORE_SSH_HOST="${NCORE_SSH_HOST:-ubuntu@144.24.4.143}"
NCORE_SSH_KEY="${NCORE_SSH_KEY:-/home/id_ed25519.pem}"
NCORE_REMOTE_REPO="${NCORE_REMOTE_REPO:-/tmp/ncore-sovereign-repo}"
NCORE_PUBLIC_HOST="${NCORE_PUBLIC_HOST:-144.24.4.143}"
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=10)

if [[ -n "$NCORE_SSH_KEY" ]]; then
  SSH_OPTS=(-i "$NCORE_SSH_KEY" "${SSH_OPTS[@]}")
fi

usage() {
  cat <<'USAGE'
Usage: scripts/ncore_operator.sh <command>

Commands:
  doctor       Full live health, ports, recent failures, and tailnet URLs
  health       HTTP health checks for live sovereign services
  status       systemd/docker/tailscale status summary
  urls         Print Tailscale dashboard/API URLs
  ports        Show managed listeners and public exposure check
  logs [unit]  Tail systemd logs for a sovereign unit (default: sovereign-bifrost)
  regress      Run live sovereign regression suite
  apply        Rsync repo scripts/sovereign to VM and run apply_sovereign_stack.sh
  tailnet      Re-run configure_tailscale_access.sh on the VM
USAGE
}

ssh_live() {
  ssh "${SSH_OPTS[@]}" "$NCORE_SSH_HOST" "$@"
}

rsync_live() {
  rsync -az --delete -e "ssh ${SSH_OPTS[*]}" "$@"
}

validate_remote_repo() {
  if [[ ! "$NCORE_REMOTE_REPO" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
    echo "NCORE_REMOTE_REPO must be an absolute path containing only letters, numbers, dot, underscore, slash, or dash" >&2
    return 2
  fi
}

health() {
  ssh_live 'set -Eeuo pipefail
for spec in \
  "Mission-Control http://127.0.0.1:3004/api/health" \
  "Agent-Zero http://127.0.0.1:8090/api/health" \
  "Legacy-Dashboard http://127.0.0.1:3002/" \
  "Grafana http://127.0.0.1:3001/login" \
  "Bifrost http://127.0.0.1:8000/health" \
  "DeerFlow http://127.0.0.1:2026/api/health" \
  "Mem0 http://127.0.0.1:8300/health" \

  "Chroma http://127.0.0.1:8200/api/v2/heartbeat"; do
  name=${spec%% *}; url=${spec#* }
  code=$(curl -sS -m 8 -o /dev/null -w "%{http_code}" "$url" || true)
  printf "%-18s %s %s\n" "$name" "$code" "$url"
done'
}

status() {
  ssh_live 'set -Eeuo pipefail
echo "== systemd =="
systemctl --no-pager --plain --type=service --state=running | grep -E "sovereign-|tailscale|ncore-tailnet" || true
echo
echo "== compose =="
cd /home/ubuntu/sovereign 2>/dev/null && docker compose --env-file .env ps || true
echo
echo "== tailscale =="
tailscale status --self || true'
}

urls() {
  ssh_live 'TSIP=$(tailscale ip -4 2>/dev/null | head -n1 || true); test -n "$TSIP" || { echo "not joined to tailscale" >&2; exit 1; }
printf "Mission Control: http://%s:3004/\n" "$TSIP"
printf "Agent Zero:      http://%s:8090/\n" "$TSIP"
printf "Legacy dash:     http://%s:3002/\n" "$TSIP"
printf "Grafana:         http://%s:3001/login\n" "$TSIP"
printf "Bifrost:         http://%s:8000/health\n" "$TSIP"
printf "DeerFlow:        http://%s:2026/api/health\n" "$TSIP"
printf "Mem0:            http://%s:8300/health\n" "$TSIP"'
}

ports() {
  ssh_live bash -s -- "$NCORE_PUBLIC_HOST" <<'REMOTE'
set -Eeuo pipefail
NCORE_PUBLIC_HOST="$1"
TSIP=$(tailscale ip -4 2>/dev/null | head -n1 || true)
echo "tailscale_ip=${TSIP:-none}"
ss -tlnp | grep -E ":(3004|8090|3002|3001|8000|2026|8300|5432|6380|8200|9090)" || true
echo
echo "public_probe"
for p in 3004 3001 8000 2026 8300; do
  code=$(curl -sS -m 3 -o /dev/null -w "%{http_code}" "http://$NCORE_PUBLIC_HOST:${p}/" || true)
  printf "%s %s\n" "$p" "$code"
done
REMOTE
}

logs() {
  local unit="${1:-sovereign-bifrost}"
  if [[ ! "$unit" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
    echo "invalid systemd unit: $unit" >&2
    return 2
  fi
  ssh_live "journalctl -u '$unit' -n 160 --no-pager"
}

regress() {
  validate_remote_repo
  ssh_live bash -s -- "$NCORE_REMOTE_REPO" <<'REMOTE'
set -Eeuo pipefail
repo="$1"
cd /home/ubuntu/sovereign
"$repo/scripts/run_sovereign_regression.sh"
REMOTE
}

apply_stack() {
  validate_remote_repo
  rsync_live sovereign scripts "$NCORE_SSH_HOST:$NCORE_REMOTE_REPO/"
  ssh_live bash -s -- "$NCORE_REMOTE_REPO" <<'REMOTE'
set -Eeuo pipefail
repo="$1"
cd "$repo"
./scripts/apply_sovereign_stack.sh
REMOTE
}

tailnet() {
  validate_remote_repo
  rsync_live scripts/configure_tailscale_access.sh "$NCORE_SSH_HOST:$NCORE_REMOTE_REPO/scripts/"
  ssh_live bash -s -- "$NCORE_REMOTE_REPO" <<'REMOTE'
set -Eeuo pipefail
repo="$1"
cd "$repo"
./scripts/configure_tailscale_access.sh
REMOTE
}

doctor() {
  echo "# NCore live doctor $(date -u +%FT%TZ)"
  echo
  echo "## URLs"; urls || true
  echo
  echo "## Health"; health || true
  echo
  echo "## Status"; status || true
  echo
  echo "## Ports"; ports || true
  echo
  echo "## Recent watchdog/bifrost logs"
  logs sovereign-watchdog | tail -80 || true
  logs sovereign-bifrost | tail -80 || true
}

cmd="${1:-}"
shift || true
case "$cmd" in
  doctor) doctor "$@" ;;
  health) health "$@" ;;
  status) status "$@" ;;
  urls) urls "$@" ;;
  ports) ports "$@" ;;
  logs) logs "$@" ;;
  regress) regress "$@" ;;
  apply) apply_stack "$@" ;;
  tailnet) tailnet "$@" ;;
  -h|--help|help|"") usage ;;
  *) usage >&2; exit 2 ;;
esac
