# NCore Genesis vFinal — Consensus Architecture (March 2026)

## The OpenClaw vs NemoClaw Question — Resolved

| Dimension | OpenClaw | NemoClaw |
|---|---|---|
| Purpose | Developer experimentation, personal/startup use | Enterprise production, compliance, team use |
| Stack | TypeScript / Node.js | Python / NVIDIA NeMo / NIM |
| Security | Admin-level (high risk in prod) | Policy-based sandboxing (OpenShell) |
| Hardware | Any (local/cloud agnostic) | GPU-accelerated, NVIDIA-native |
| Ecosystem | 5,000+ community skills | Curated enterprise toolchain |
| Cost | Free, open-source | Enterprise licensing |

**Decision for this setup:** We use **OpenClaw** as the gateway daemon (Node.js, runs as a systemd service, handles skill routing and context) because:
1. The Oracle VM is a personal/experimental node, not an enterprise compliance environment
2. OpenClaw's 5,000+ community skills ecosystem is broader for our use case
3. NemoClaw's GPU-acceleration is targeted at NVIDIA DGX infrastructure we don't have
4. OpenClaw = flexible glue; NemoClaw = hardened enterprise runtime

The **Python orchestrator (FastAPI + LangGraph)** runs *alongside* OpenClaw as a separate systemd service, handling all AI routing and model calls. OpenClaw handles skills/context; the orchestrator handles inference routing.

---

## Model Stack (Consensus)

| Tier | Model | Provider | Engine | Use Case | Est. Cost |
|---|---|---|---|---|---|
| NANO | nvidia/nemotron-nano-9b-v2 | OpenRouter | LMDeploy | Trivial Q&A | ~$0.00004 |
| SUPER | nvidia/nemotron-3-super-120b-a12b | OpenRouter | SGLang/LMDeploy | Standard reasoning | ~$0.002 |
| OPUS | anthropic/claude-opus-4.6 | OpenRouter | Claude API | Legal/medical/financial | ~$0.05–0.25 |
| CODER | Qwen/Qwen2.5-Coder-14B | Vast serverless | SGLang | Code gen/debug | ~$0.001 |
| UNCENSORED | dolphin-2.9.4-llama3.1-8b | Vast serverless | SGLang | Unfiltered text | ~$0.001 |
| IMAGE | flux-1-dev | Vast pod | ComfyUI | Image generation | ~$0.03 |
| VIDEO | wan-2.2-remix-nsfw | Vast pod | ComfyUI | Video generation | ~$0.25 |

**Why Nemotron 3 Super over Dolphin/Dark-Champion for standard tasks:**
- 120B params, 12B active (MoE), hybrid Mamba-Transformer architecture
- 50%+ higher token generation vs comparable open models
- Available free tier on OpenRouter (`nvidia/nemotron-3-super-120b-a12b:free`)
- Best open model for multi-agent orchestration per NVIDIA benchmarks

---

## Inference Engines (Consensus)

| Engine | Throughput (H100) | Best For | Used When |
|---|---|---|---|
| SGLang | ~16,200 tok/s | Multi-turn, RadixAttention cache | turns > 3 |
| LMDeploy | ~16,100 tok/s | Quantized models, lowest TTFT | First call / single-turn |
| vLLM | ~12,500 tok/s | NOT USED — 29% slower | — |

SGLang's RadixAttention achieves **85-95% cache-hit rate** on multi-turn sessions, dramatically reducing compute cost. LMDeploy's TurboMind C++ kernel delivers lowest time-to-first-token for cold/first calls.

---

## Vast.ai Usage Strategy (Minimal Latency)

### Serverless (for Coder + Uncensored)
- Always-warm reserve pool: 1-2 workers kept hot
- Vast.ai predictive optimization pre-provisions based on usage patterns
- Cold-start: ~200ms–4s for small models with reserve pool enabled
- Billing: per-request only

### Pods (for Image + Video)
- Spin up → run job → destroy immediately
- Use `VAST_RESERVE_VIDEO_ID` / `VAST_RESERVE_IMAGE_ID` env vars to pre-warm a pod
  and reuse it across requests (set to `vastai create instance ...` output)
- RTX 4090 ~$0.17/hr; a 4-sec video at 2-min runtime = ~$0.006 compute cost
- Destroy is called in `finally` block — guaranteed even on exception

### Latency targets
| Task | Target latency |
|---|---|
| Trivial (Nano) | < 500ms |
| Standard (Super, LMDeploy, first call) | 1–3s TTFT |
| Standard (Super, SGLang, multi-turn) | 0.5–1.5s (cached) |
| Code (Qwen, Vast serverless) | 2–5s |
| Image (FLUX, Vast pod, pre-warmed) | 30–60s |
| Video (Wan 2.2, Vast pod, pre-warmed) | 90–180s |

---

## Service Layout on Oracle VM

```
ncore-gateway.service     ← FastAPI orchestrator (port 8080)
openclaw-gateway.service  ← OpenClaw skill daemon (port 3000)
redis.service             ← Session/cache store
tailscaled.service        ← Zero-trust network
```

## Next Steps Checklist

- [ ] Fill in `~/.ncore/.env` with real API keys (OpenRouter, Vast.ai, Supabase, Telegram)
- [ ] `sudo systemctl restart ncore-gateway` after git pull
- [ ] Test: `curl -s -X POST http://127.0.0.1:8080/run -H 'Content-Type: application/json' -d '{"task":"what is 2+2"}'`
- [ ] Set up Vast.ai serverless endpoints for Coder + Uncensored, add URLs to .env
- [ ] Optional: pre-warm a Vast pod and set `VAST_RESERVE_VIDEO_ID` for zero-cold-start video
- [ ] Authenticate Tailscale: `sudo tailscale up --authkey=tskey-...`
- [ ] Wire Telegram bot for mobile C2
