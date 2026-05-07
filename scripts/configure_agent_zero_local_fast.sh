#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

AGENT_ZERO_DATA_DIR="${AGENT_ZERO_DATA_DIR:-/home/ubuntu/agent-zero-data}"
MODEL_NAME="ncore-fast-uncensored"
MODEL_TAG="ncore-fast-uncensored:latest"
BASE_MODEL="huihui_ai/qwen3-abliterated:1.7b"
OLLAMA_URL="http://127.0.0.1:11434"
AGENT_ZERO_URL="${AGENT_ZERO_URL:-http://127.0.0.1:8090}"

log() { printf '[ncore-local-fast] %s\n' "$*"; }

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
need_cmd ollama

log "configuring ollama systemd override"
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/ncore-local.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_KEEP_ALIVE=-1"
Environment="OLLAMA_LOAD_TIMEOUT=300s"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_FLASH_ATTENTION=1"
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
sudo systemctl restart ollama
wait_http "${OLLAMA_URL}/api/tags" "ollama" 180

log "creating/updating ${MODEL_TAG}"
modelfile="$(mktemp)"
trap 'rm -f "$modelfile"' EXIT
cat >"$modelfile" <<'EOF'
FROM huihui_ai/qwen3-abliterated:1.7b
PARAMETER temperature 0.1
PARAMETER num_ctx 2048
PARAMETER num_predict 192
SYSTEM "/no_think\nYou are NCore Fast Local. Do not reason visibly. Do not use markdown unless asked. For Agent Zero, always return valid JSON exactly matching the requested tool-call schema. Be concise."
EOF
ollama create "$MODEL_NAME" -f "$modelfile"

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

API_BASE = "http://host.docker.internal:11434/v1"
MODEL_NAME = "ncore-fast-uncensored:latest"

def model(max_tokens):
    return {
        "provider": "openai",
        "name": MODEL_NAME,
        "api_base": API_BASE,
        "api_key": "ollama",
        "ctx_length": 2048,
        "ctx_history": 0.05,
        "vision": False,
        "max_embeds": 0,
        "rl_requests": 0,
        "rl_input": 0,
        "rl_output": 0,
        "kwargs": {
            "num_retries": 0,
            "max_tokens": max_tokens,
            "temperature": 0.1,
        },
    }

data["chat_model"] = model(192)
data["utility_model"] = model(96)
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
  log "agent-zero container does not exist; skipping plugin disable before patch"
fi

if (( agent_zero_exists )); then
  log "patching /a0/api/api_message.py in agent-zero container"
  docker exec -i agent-zero /opt/venv-a0/bin/python <<'PY'
from pathlib import Path
import re

path = Path("/a0/api/api_message.py")
src = path.read_text()

# Cleanup accepts indented markers because the patches live inside ApiMessage.
src = re.sub(
    r"^[ \t]*# NCORE_FAST_LOCAL_BEGIN\n.*?^[ \t]*# NCORE_FAST_LOCAL_END\n(?:^[ \t]*\n)?",
    "",
    src,
    flags=re.M | re.S,
)
src = re.sub(
    r"(?:^[ \t]*\n)?^[ \t]*# NCORE_FAST_LOCAL_CALL\n"
    r"^[ \t]*if input\.get\(\"full_agent\"\) is not True and input\.get\(\"fast_local\", True\) is not False and not attachments:\n"
    r"^[ \t]*return await self\._fast_local_response\(message, context_id\)\n(?:^[ \t]*\n)?",
    "",
    src,
    flags=re.M,
)

required_imports = ["import asyncio", "import json", "import os", "import re", "import urllib.request", "import urllib.error"]
lines = src.splitlines(True)
insert_at = 0
while insert_at < len(lines) and (lines[insert_at].startswith("#!") or "coding" in lines[insert_at][:80]):
    insert_at += 1
while insert_at < len(lines):
    stripped = lines[insert_at].strip()
    if not stripped or stripped.startswith("import ") or stripped.startswith("from "):
        insert_at += 1
        continue
    break
existing = set(line.strip() for line in lines)
missing = [line + "\n" for line in required_imports if line not in existing]
if missing:
    lines[insert_at:insert_at] = missing
    src = "".join(lines)

class_match = re.search(r"^class ApiMessage\(ApiHandler\):\n", src, flags=re.M)
if not class_match:
    raise SystemExit("expected class ApiMessage(ApiHandler) not found in /a0/api/api_message.py")

process_match = re.search(r"^    async def process\(self, input: dict, request: Request\):\n", src, flags=re.M)
if not process_match:
    raise SystemExit("expected ApiMessage.process(self, input: dict, request: Request) not found")

helper = r'''    # NCORE_FAST_LOCAL_BEGIN
    @staticmethod
    def _fast_local_clean_response(text):
        raw = str(text or "").strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.I | re.S).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I).strip()
            raw = re.sub(r"\s*```$", "", raw).strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            return raw
        if isinstance(parsed, dict):
            tool_args = parsed.get("tool_args")
            if isinstance(tool_args, dict) and "text" in tool_args:
                return str(tool_args["text"])
            for key in ("response", "answer", "text", "tool_call"):
                if key in parsed:
                    return str(parsed[key])
        return raw

    @staticmethod
    def _fast_local_chat_sync(message, context_id=None):
        model = os.environ.get("A0_FAST_LOCAL_MODEL", "qwen3-8b:latest")
        exact_mode = "reply exactly" in str(message).lower() or "return exactly" in str(message).lower()
        num_predict = 96 if exact_mode and len(str(message)) < 500 else 900
        messages = [
            {
                "role": "system",
                "content": "You are an exact-response completion engine. If the user asks to reply exactly with a token/string, output only that token/string. Otherwise complete the requested task fully with concise, structured output. Do not refuse benign safety, security-awareness, or defensive tabletop tasks. For mock phishing/security-awareness content, never include live-looking URLs, credential-capture URLs, password reset parameters, real credentials, exploit code, or evasion steps; use obvious placeholders such as [SAFE-LINK-PLACEHOLDER], [EMPLOYEE_NAME], and example.invalid. Do not return JSON unless the user explicitly asks for JSON. Never summarize exact-output tasks as completed; perform them by returning the requested text.",
            },
            {"role": "user", "content": str(message)},
        ]
        body = json.dumps({
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": num_predict, "num_ctx": 4096, "temperature": 0.1},
        }).encode("utf-8")
        request = urllib.request.Request(
            "http://host.docker.internal:11434/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            error = f"FAST_LOCAL_ERROR: {exc}"
            return {"response": error, "text": error, "fast_local": True, "error": str(exc)}
        content = data.get("message", {}).get("content") or data.get("response") or data.get("content") or ""
        cleaned = ApiMessage._fast_local_clean_response(content)
        return {"response": cleaned, "text": cleaned, "answer": cleaned, "fast_local": True}

    async def _fast_local_response(self, message, context_id=None):
        return await asyncio.to_thread(self._fast_local_chat_sync, message, context_id)
    # NCORE_FAST_LOCAL_END

'''

if "# NCORE_FAST_LOCAL_BEGIN" not in src:
    src = src[:process_match.start()] + helper + src[process_match.start():]

process_match = re.search(r"^    async def process\(self, input: dict, request: Request\):\n", src, flags=re.M)
next_method = re.search(r"^    (?:async\s+)?def\s+\w+\(", src[process_match.end():], flags=re.M)
process_end = process_match.end() + next_method.start() if next_method else len(src)
process_src = src[process_match.start():process_end]

if "# NCORE_FAST_LOCAL_CALL" not in process_src:
    not_message = re.search(r"^        if not message:\n", process_src, flags=re.M)
    if not not_message:
        raise SystemExit("expected 'if not message:' guard in ApiMessage.process")
    required_before = {
        "message": r"message\s*=\s*input\.get\(",
        "attachments": r"attachments\s*=",
        "context_id": r"context_id\s*=",
    }
    for name, pattern in required_before.items():
        match = re.search(pattern, process_src)
        if not match:
            raise SystemExit(f"expected {name} extraction in ApiMessage.process before patching")
        if match.start() > not_message.start():
            raise SystemExit(f"expected {name} extraction before 'if not message:' guard")
    lines = process_src.splitlines(True)
    char_count = 0
    guard_line = None
    for i, line in enumerate(lines):
        next_count = char_count + len(line)
        if char_count <= not_message.start() < next_count:
            guard_line = i
            break
        char_count = next_count
    if guard_line is None:
        raise SystemExit("could not locate message guard line")
    insert_line = guard_line + 1
    while insert_line < len(lines):
        line = lines[insert_line]
        if line.strip() and not line.startswith("            "):
            break
        insert_line += 1
    call = (
        "\n"
        "        # NCORE_FAST_LOCAL_CALL\n"
        "        if input.get(\"full_agent\") is not True and input.get(\"fast_local\", True) is not False and not attachments:\n"
        "            return await self._fast_local_response(message, context_id)\n"
    )
    lines[insert_line:insert_line] = [call]
    patched_process = "".join(lines)
    src = src[:process_match.start()] + patched_process + src[process_end:]

path.write_text(src)
print("patched /a0/api/api_message.py")
PY

  log "restarting agent-zero"
  docker restart agent-zero >/dev/null
  wait_http "${AGENT_ZERO_URL}/api/health" "agent-zero" 180
else
  log "agent-zero container does not exist; skipping container patch and restart"
fi

if (( agent_zero_exists )); then
  log "syncing Agent Zero API token file"
  token="$(docker exec -w /a0 agent-zero /opt/venv-a0/bin/python -c 'from helpers.settings import create_auth_token; print(create_auth_token())')"
  install -m 600 /dev/null /home/ubuntu/.agent-zero-api-token
  printf '%s' "$token" >/home/ubuntu/.agent-zero-api-token
  chown ubuntu:ubuntu /home/ubuntu/.agent-zero-api-token 2>/dev/null || true
fi

if [[ -f /home/ubuntu/.agent-zero-api-token ]]; then
  log "running fast-local smoke test"
  python3 <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

token = Path("/home/ubuntu/.agent-zero-api-token").read_text().strip()
body = json.dumps({"message": "Reply with exactly FAST_LOCAL_OK."}).encode("utf-8")
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
if "FAST_LOCAL_OK" not in payload:
    print("smoke assertion failed: response did not contain FAST_LOCAL_OK", file=sys.stderr)
    sys.exit(1)
PY
else
  log "no /home/ubuntu/.agent-zero-api-token found; skipping smoke test"
fi

log "done"
