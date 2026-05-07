# ncore-genesis-vfinal
NCore Genesis vFinal: Oracle VM deployment scripts + MoE orchestrator for OpenClaw-based autonomous infra.

## Agent Zero local-fast persistence

`scripts/configure_agent_zero_local_fast.sh` reapplies the Oracle VM live Agent Zero local-fast fix. It configures Ollama systemd settings for single-model CPU-local serving, creates/updates the `ncore-fast-uncensored` Ollama model, rewrites Agent Zero model/settings JSON for the local OpenAI-compatible Ollama endpoint, disables heavy plugins, patches the running `agent-zero` container `/a0/api/api_message.py` with the fast-local Ollama path, restarts Agent Zero, and runs a token-based smoke test when `/home/ubuntu/.agent-zero-api-token` exists.

## Sovereign stack production persistence

The current production stack on `ncore-v2` is persisted under `sovereign/` and applied with:

```bash
scripts/apply_sovereign_stack.sh
```

It preserves the live VM layout and does not rebuild working services from scratch. It installs/updates:

- `sovereign-bifrost` on `127.0.0.1:8000`
- `sovereign-deerflow` on `127.0.0.1:2026`
- `sovereign-mem0` on `127.0.0.1:8300`
- `sovereign-mission-control` on `127.0.0.1:3004`
- `sovereign-watchdog`
- Docker Compose services for Postgres, Redis, Chroma, Prometheus, and Grafana

Local model lane:

1. `qwen3-8b:latest`
2. `dolphin-mistral-7b:latest`

The Bifrost shim logs provider/model/fallback/latency/completion metadata to SQLite and exposes recent runs at `/runs`. Allowed-task soft refusals, policy boilerplate, and structured-output failures fall back to the local lane. CSAM/minors and bodily harm are hard stops; ambiguous dual-use cyber tasks ask for authorization/scope.

Mission Control:

```text
http://127.0.0.1:3004/
```

Regression suite:

```bash
scripts/run_sovereign_regression.sh
```

Reports are written under `/home/ubuntu/sovereign/logs/`.

### Tailscale dashboard access

Use `scripts/configure_tailscale_access.sh` on the VM to join Tailscale and expose only the dashboard/API front doors on the Tailscale IP. The script does not store auth keys in the repo. For OAuth auth keys, provide the allowed tag explicitly:

```bash
TAILSCALE_AUTHKEY=tskey-client-... \
TAILSCALE_ADVERTISE_TAGS=tag:ncore \
scripts/configure_tailscale_access.sh
```

It proxies Mission Control `3004`, Agent Zero `8090`, legacy dashboard `3002`, Grafana `3001`, Bifrost `8000`, DeerFlow `2026`, and Mem0 `8300` from localhost to the tailnet IP only. Databases remain localhost-bound.

Known limitations:

- The live VM is Ubuntu 22.04 arm64, not Oracle Linux.
- Disk is constrained; scripts preserve existing Ollama models instead of pulling duplicate large GGUF files.
- Legacy services (`8080`, `8090`, `8888`, `11235`, `11434`) may still bind broadly; the apply script reports them so they can be tightened carefully without breaking the current stack.
