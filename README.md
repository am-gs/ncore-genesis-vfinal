# ncore-genesis-vfinal
NCore Genesis vFinal: Oracle VM deployment scripts + MoE orchestrator for OpenClaw-based autonomous infra.

## Agent Zero local-fast persistence

`scripts/configure_agent_zero_local_fast.sh` reapplies the Oracle VM live Agent Zero local-fast fix. It configures Ollama systemd settings for single-model CPU-local serving, creates/updates the `ncore-fast-uncensored` Ollama model, rewrites Agent Zero model/settings JSON for the local OpenAI-compatible Ollama endpoint, disables heavy plugins, patches the running `agent-zero` container `/a0/api/api_message.py` with the fast-local Ollama path, restarts Agent Zero, and runs a token-based smoke test when `/home/ubuntu/.agent-zero-api-token` exists.
