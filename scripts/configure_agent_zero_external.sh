#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

AGENT_ZERO_DATA_DIR="${AGENT_ZERO_DATA_DIR:-/home/ubuntu/agent-zero-data}"
AGENT_ZERO_URL="${AGENT_ZERO_URL:-http://127.0.0.1:8090}"
API_BASE="http://host.docker.internal:8000/v1"
MODEL_NAME="llama-3.3-70b"

log() { printf '[ncore-external] %s\n' "$*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }
}

backup_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    local stamp
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    cp -a "$path" "${path}.bak.${stamp}"
  fi
}

wait_http() {
  local url="$1"
  local label="$2"
  local timeout_s="${3:-120}"
  local start now
  start="$(date +%s)"
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$label ready"
      return 0
    fi
    now="$(date +%s)"
    if (( now - start >= timeout_s )); then
      echo "timed out waiting for $label at $url" >&2
      return 1
    fi
    sleep 2
  done
}

need_cmd sudo
need_cmd curl
need_cmd python3
need_cmd docker

log "updating Agent Zero data dir: ${AGENT_ZERO_DATA_DIR}"
mkdir -p "${AGENT_ZERO_DATA_DIR}/plugins/_model_config"
model_config="${AGENT_ZERO_DATA_DIR}/plugins/_model_config/config.json"
settings_json="${AGENT_ZERO_DATA_DIR}/settings.json"
[[ -f "$model_config" ]] || printf '{}\n' >"$model_config"
[[ -f "$settings_json" ]] || printf '{}\n' >"$settings_json"
backup_file "$model_config"
backup_file "$settings_json"

python3 - "$model_config" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text() or "{}")
if not isinstance(data, dict):
    data = {}

API_BASE = "http://host.docker.internal:8000/v1"
MODEL_NAME = "llama-3.3-70b"

def model(max_tokens):
    return {
        "provider": "openai",
        "name": MODEL_NAME,
        "api_base": API_BASE,
        "api_key": "bifrost",
        "ctx_length": 8192,
        "ctx_history": 0.05,
        "vision": False,
        "max_embeds": 0,
        "rl_requests": 0,
        "rl_input": 0,
        "rl_output": 0,
        "kwargs": {
            "num_retries": 2,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
    }

data["chat_model"] = model(900)
data["utility_model"] = model(256)
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY

python3 - "$settings_json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text() or "{}")
if not isinstance(data, dict):
    data = {}

for key in (
    "mcp_timeout",
    "mcp_init_timeout",
    "mcp_connect_timeout",
    "mcp_tool_timeout",
    "work_dir_show",
    "workdir_max_depth",
    "workdir_max_chars",
    "workdir_max_file_chars",
    "workdir_max_file_size",
):
    data.pop(key, None)

data.update({
    "workdir_show": False,
    "workdir_max_files": 20,
    "workdir_max_folders": 5,
    "workdir_max_lines": 200,
    "mcp_servers": '{"mcpServers": {}}',
    "mcp_client_init_timeout": 2,
    "mcp_client_tool_timeout": 5,
})
path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
PY

agent_zero_exists=0
if docker ps -a --format '{{.Names}}' | grep -Fxq agent-zero; then
  agent_zero_exists=1
  if ! docker ps --format '{{.Names}}' | grep -Fxq agent-zero; then
    log "starting agent-zero container"
    docker start agent-zero >/dev/null
  fi
fi

if (( agent_zero_exists )); then
  log "disabling heavy Agent Zero plugins"
  docker exec -i agent-zero /opt/venv-a0/bin/python <<'PY'
plugins = [
    "_memory",
    "_skills",
    "_browser_agent",
    "_chat_compaction",
    "_email_integration",
    "_whatsapp_integration",
    "_telegram_integration",
    "autoresearch",
    "camofox_browser",
    "langfuse_observability",
    "_a0_connector",
]
try:
    from helpers.plugins import toggle_plugin
except Exception as exc:
    raise SystemExit(f"could not import helpers.plugins.toggle_plugin: {exc}")

for plugin in plugins:
    last_error = None
    variants = (
        lambda: toggle_plugin(plugin, False),
        lambda: toggle_plugin(plugin, enabled=False),
        lambda: toggle_plugin(plugin_name=plugin, enabled=False),
        lambda: toggle_plugin(name=plugin, enabled=False),
        lambda: toggle_plugin(plugin, False, None),
    )
    for variant in variants:
        try:
            variant()
            print(f"disabled {plugin}")
            break
        except TypeError as exc:
            last_error = exc
    else:
        raise SystemExit(f"could not disable {plugin}: {last_error}")
PY
else
  log "agent-zero container does not exist; skipping plugin disable"
fi

if (( agent_zero_exists )); then
  log "restarting agent-zero"
  docker restart agent-zero >/dev/null
  wait_http "${AGENT_ZERO_URL}/api/health" "agent-zero" 180
fi

if (( agent_zero_exists )); then
  log "syncing Agent Zero API token file"
  token="$(docker exec -w /a0 agent-zero /opt/venv-a0/bin/python -c 'from helpers.settings import create_auth_token; print(create_auth_token())')"
  install -m 600 /dev/null /home/ubuntu/.agent-zero-api-token
  printf '%s' "$token" >/home/ubuntu/.agent-zero-api-token
  chown ubuntu:ubuntu /home/ubuntu/.agent-zero-api-token 2>/dev/null || true
fi

if [[ -f /home/ubuntu/.agent-zero-api-token ]]; then
  log "running external-provider smoke test"
  python3 <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

token = Path("/home/ubuntu/.agent-zero-api-token").read_text().strip()
body = json.dumps({"message": "Reply with exactly BIFROST_V2_OK."}).encode("utf-8")
request = urllib.request.Request(
    "http://127.0.0.1:8090/api/api_message",
    data=body,
    headers={"Content-Type": "application/json", "X-API-KEY": token},
    method="POST",
)
start = time.perf_counter()
try:
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read().decode("utf-8", errors="replace")
        elapsed = time.perf_counter() - start
        status = response.status
except urllib.error.HTTPError as exc:
    elapsed = time.perf_counter() - start
    status = exc.code
    payload = exc.read().decode("utf-8", errors="replace")
    print(f"smoke_status={status} smoke_seconds={elapsed:.2f} response={payload[:500]}")
    raise

print(f"smoke_status={status} smoke_seconds={elapsed:.2f} response={payload[:500]}")
if "BIFROST_V2_OK" not in payload:
    print("smoke assertion failed: response did not contain BIFROST_V2_OK", file=sys.stderr)
    sys.exit(1)
PY
else
  log "no /home/ubuntu/.agent-zero-api-token found; skipping smoke test"
fi

log "done"
