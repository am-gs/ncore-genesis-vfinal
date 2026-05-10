#!/usr/bin/env bash
set -euo pipefail

# Local health check for Manus Mission Control stack.
# Run this on the sovereign VM.

check_http() {
  local name=$1 url=$2
  local code
  code=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" "$url" || true)
  printf "%-22s %s %s\n" "$name" "$code" "$url"
}

check_service() {
  local name=$1
  if systemctl is-active --quiet "$name" 2>/dev/null; then
    printf "%-22s %s\n" "$name" "active"
  else
    printf "%-22s %s\n" "$name" "INACTIVE"
  fi
}

echo "== systemd =="
check_service nginx
check_service manus-mission-control
check_service bifrost
check_service sovereign-bifrost || true
check_service sovereign-mission-control || true

echo ""
echo "== HTTP =="
check_http "nginx"          "http://127.0.0.1:80/"
check_http "mission-control" "http://127.0.0.1:3004/api/health"
check_http "bifrost"        "http://127.0.0.1:8000/health"

echo ""
echo "== docker compose =="
cd /home/ubuntu/sovereign 2>/dev/null && docker compose --env-file .env ps || true
