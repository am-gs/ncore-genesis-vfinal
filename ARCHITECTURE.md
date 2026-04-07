# NCore Genesis vFinal — Consensus Architecture v3.2 (March 2026)

## Audit Status

| Issue | Severity | Status |
|-------|----------|--------|
| C1: httpx connection pooling | Critical | ✅ Fixed |
| C2: Async event loop unblocking | Critical | ✅ Fixed — ainvoke() + async nodes |
| C3: Bare except: in budget guard | Critical | ✅ Fixed |
| H1: moe_router.py dead code | High | ✅ Fixed — wired with NCoreModelRegistry |
| H2: Missing requirements | High | ✅ Fixed |
| H3: Qwen2.5 → Qwen3-Coder | High | ✅ Fixed |
| H4: Sync subprocess in async path | High | ✅ Fixed — asyncio.create_subprocess_exec |
| M1: No retry logic | Medium | ✅ Fixed — tenacity (3 attempts, exp backoff) |
| M2: Unstructured stdlib logging | Medium | ✅ Fixed — structlog JSON |
| M3: Missing metrics for MoE router | Medium | ✅ Fixed |
| M4: XDP port 5678 → 443 | Medium | ✅ Fixed — allows 443 for HTTPS/Caddy |
| L1: CPU affinity single core | Low | No change — acceptable for single-user |
| L2: No .env.example | Low | ✅ Fixed |
| L3: XDP redundant vs 127.0.0.1 bind | Low | Defense-in-depth intentional |

---

## OpenClaw vs NemoClaw — Resolved

| Dimension | OpenClaw | NemoClaw |
|---|---|---|
| Purpose | Developer/startup experimentation | Enterprise production + compliance |
| Stack | TypeScript / Node.js | Python / NVIDIA NeMo / NIM |
| Security | Admin-level | Policy-based OpenShell sandboxing |
| Hardware | Any (cloud-agnostic) | NVIDIA GPU-native (DGX-class) |
| Ecosystem | 5,000+ community skills | Curated enterprise toolchain |
| Cost | Free, open-source | Enterprise licensing |

**Decision:** OpenClaw — personal/experimental Oracle node, not DGX enterprise.

---

## Model Stack (Consensus v3.1)

| Tier | Model | Provider | Engine | Use Case | Est. Cost |
|---|---|---|---|---|---|
| NANO | nvidia/nemotron-nano-9b-v2 | OpenRouter | LMDeploy | Trivial Q&A | ~$0.00004 |
| SUPER | nvidia/nemotron-3-super-120b-a12b | OpenRouter | SGLang/LMDeploy | Standard reasoning | ~$0.002 |
| OPUS | anthropic/claude-opus-4.6 | OpenRouter | Claude API | Legal/medical/financial | ~$0.05–0.25 |
| CODER | Qwen/Qwen3-Coder-30B-A3B-Instruct | Vast serverless | SGLang | Code gen/debug | ~$0.001 |
| UNCENSORED | dolphin-2.9.4-llama3.1-8b | Vast serverless | SGLang | Unfiltered text | ~$0.001 |
| IMAGE | flux-1-dev | Vast pod (ephemeral) | ComfyUI | Image generation | ~$0.03 |
| VIDEO | wan-2.2-remix-nsfw | Vast pod (ephemeral) | ComfyUI | Video generation | ~$0.25 |

## 7-Tier Routing Cascade (v7.6 — April 7 2026)

| Tier | Model | Provider | Cost | Use Case |
|---|---|---|---|---|
| T0 LOCAL | Dark Champion V2 21B + Qwen3.5 abliterated | Ollama | $0 | Critic, uncensored fallback |
| T1 FAST | openai/gpt-oss-20b:free | OpenRouter | $0 | Trivial tasks — matches o3-mini, 13 providers |
| T2 FREE_CODER | qwen3-coder-480b:free | OpenRouter | $0 | Code tasks, complexity < 6 |
| T3 FREE_REASONING | deepseek/deepseek-r1:free | OpenRouter | $0 | Reasoning, complexity 4-7 |
| T4 WORKER | deepseek/deepseek-chat (V3.2) | OpenRouter | $0.14/$0.28/M | Standard tasks, complexity < 8 |
| T5 OPUS | anthropic/claude-opus-4.6 | OpenRouter | $5/$25/M | Budget-gated, complexity ≥ 8 only |
| GPU | Wan 2.2 / Flux / vLLM | Vast.ai | $0.30-1.80/hr | Video, image, heavy inference |

~90% of tasks route to $0 infrastructure. Paid tiers only activate for genuine complexity.

---

## Routing Architecture (Two-Layer)

```
Request
  │
  ▼
NCoreMasterRouter (5-layer)
  │  L0: Media detection → pod spec
  │  L1: Trivial heuristic → Nano
  │  L2: Domain keyword → Opus | Uncensored | Coder
  │  L3: Complexity score → Opus | Super
  │  L4: Engine selection → SGLang vs LMDeploy
  │
  ├─ tier=vast-serverless →  AthenaMoERouter
  │                             (ONNX INT8 classifier + FAISS + Redis cache)
  │                             → picks exact model + endpoint on Vast
  │
  └─ tier=openrouter/vast-pod → direct to provider
```

---

## Inference Engines

| Engine | Throughput | Best For | When Used |
|---|---|---|---|
| SGLang | ~16,200 tok/s | Multi-turn, RadixAttention (85-95% cache) | turns > 3 |
| LMDeploy | ~16,100 tok/s | First-call, quantized, lowest TTFT | First call / single-turn |
| vLLM | ~12,500 tok/s | NOT USED — 29% slower | — |

---

## Vast.ai Latency Strategy

### Serverless (Coder + Uncensored)
- Reserve pool: 1–2 warm workers (cold start ~200ms with reserve)
- Set `VAST_CODER_URL` and `VAST_UNCENSORED_URL` in `.env`

### Pods (Image + Video — ephemeral)
- Spin up → run → destroy (guaranteed in `finally` block)
- Pre-warm: set `VAST_RESERVE_VIDEO_ID` / `VAST_RESERVE_IMAGE_ID`
  to skip 120s Wan 2.2 cold start on repeat video requests
- RTX 4090 ~$0.17/hr; a 3-min video job ≈ $0.008 compute

### Latency Targets
| Task | Target |
|---|---|
| Nano (trivial) | < 500ms |
| Super, LMDeploy (first call) | 1–3s TTFT |
| Super, SGLang (multi-turn cached) | 0.5–1.5s |
| Coder, Vast serverless | 2–5s |
| Image, pre-warmed pod | 30–60s |
| Video, pre-warmed pod | 90–180s |

---

## Service Layout on Oracle VM

```
ncore-gateway.service     ← FastAPI orchestrator (port 8080, 127.0.0.1)
openclaw-gateway.service  ← OpenClaw skill daemon (port 3000)
redis.service             ← Session/cache store
tailscaled.service        ← Zero-trust network
```

## Deployment Checklist

- [ ] `git pull origin main` on Oracle VM
- [ ] `pip install -r core/requirements.txt` (in venv)
- [ ] Fill in `~/.ncore/.env` (OpenRouter + Vast.ai keys minimum)
- [ ] `sudo systemctl restart ncore-gateway`
- [ ] Test: `curl -s -X POST http://127.0.0.1:8080/run -d '{"task":"what is 2+2"}' -H 'Content-Type: application/json' | jq .route.tier`
- [ ] Set up Vast.ai serverless workers → add URLs to .env
- [ ] Authenticate Tailscale: `sudo tailscale up --authkey=tskey-...`
- [ ] Optional: pre-warm Vast pods → set VAST_RESERVE_* IDs
