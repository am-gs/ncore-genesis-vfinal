"""NCore Genesis — Consensus Router v3.0

Model stack (March 2026 consensus):
  NANO       → nvidia/nemotron-nano-9b-v2          (trivial, ~$0.00004/req)
  SUPER      → nvidia/nemotron-3-super-120b-a12b   (standard, ~$0.002/req)
  OPUS       → anthropic/claude-opus-4.6            (high-stakes, ~$0.05–0.25/req)
  CODER      → Qwen/Qwen2.5-Coder-14B             (code, ~$0.001/req)
  UNCENSORED → dolphin-2.9.4-llama3.1-8b          (no-filter text, ~$0.001/req)
  IMAGE_GEN  → flux-1-dev (Vast pod)               (~$0.03/image)
  VIDEO_GEN  → wan-2.2-remix-nsfw (Vast pod)       (~$0.25/video)

Inference engines:
  SGLang  → multi-turn / RadixAttention cache (85-95% cache-hit target)
  LMDeploy→ first-call / quantized serving / lowest TTFT
  (vLLM is 29% slower — not used)

Vast.ai usage:
  SERVERLESS → for Coder + Uncensored text (always-warm reserve pool)
  POD        → for Image/Video gen (spin up → run → destroy)
"""
from __future__ import annotations
import re, os, time, json, sys
from dataclasses import dataclass, asdict
from enum import Enum


class ModelTier(Enum):
    NANO       = "nano"
    SUPER      = "super"
    OPUS       = "opus"
    CODER      = "coder"
    UNCENSORED = "uncensored"
    IMAGE_GEN  = "image"
    VIDEO_GEN  = "video"


@dataclass
class RouteDecision:
    tier: str
    model: str
    provider: str
    endpoint: str
    engine: str          # sglang | lmdeploy | claude | vast-native
    reason: str
    estimated_cost_usd: float
    requires_pod: bool = False
    pod_spec: dict = None


class NCoreMasterRouter:
    """
    5-layer routing:
      L0: Media detection  → Vast pod (image / video)
      L1: Fast heuristics  → NANO (trivial)
      L2: Domain keyword   → OPUS (legal/medical/financial) | UNCENSORED | CODER
      L3: Complexity score → OPUS (score≥8) | SUPER
      L4: Engine selection → SGLang (multi-turn) vs LMDeploy (first-call)
    """

    # ── L0 keywords ────────────────────────────────────────────────────────
    VIDEO_KW = [
        "video", "animate", "animation", "motion", "footage", "clip",
        "text to video", "image to video", "t2v", "i2v", "wan", "wan2",
        "nsfw video", "adult video", "generate video"
    ]
    IMAGE_KW = [
        "image", "picture", "photo", "illustration", "artwork", "render",
        "generate image", "text to image", "stable diffusion", "flux",
        "nsfw image", "adult image", "nude", "explicit image", "sdxl"
    ]

    # ── L1 trivial patterns ────────────────────────────────────────────────
    TRIVIAL_RE = [
        r"^(what is|define|who is|when was|how many|what year)",
        r"^(translate|convert|format|summarize in \d+)",
        r"^(yes or no|true or false)",
    ]

    # ── L2 domain keywords ─────────────────────────────────────────────────
    OPUS_KW = [
        "legal", "contract", "lawsuit", "compliance", "regulation",
        "medical", "diagnosis", "treatment", "clinical", "pharmaceutical",
        "financial", "investment", "portfolio", "tax strategy", "audit",
        "analyze this entire document", "comprehensive review",
        "peer review", "research paper", "academic", "thesis",
        "extremely complex", "expert level", "red team", "adversarial"
    ]
    CODE_KW = [
        "code", "script", "function", "class", "debug", "refactor",
        "implement", "program", "algorithm", "sql", "bash", "python",
        "javascript", "typescript", "api endpoint", "unit test", "dockerfile"
    ]
    UNFILTERED_KW = [
        "no filter", "uncensored", "unrestricted", "without restrictions",
        "ignore safety", "nsfw text", "adult content", "explicit text",
        "roleplay", "erotic", "mature content"
    ]

    # ── L3 complexity signals ──────────────────────────────────────────────
    MULTI_STEP_KW = ["then", "after that", "next", "step by step", "workflow",
                     "pipeline", "sequence", "multiple steps", "chain"]
    HIGH_STAKES_KW = ["production", "deploy", "critical", "mission", "urgent",
                      "must be correct", "cannot fail", "important"]

    def route(self, task: str, turns: int = 0) -> dict:
        text = task.lower().strip()
        tokens = len(task.split()) * 1.3

        # ── LAYER 0: Media Detection ───────────────────────────────────────
        if any(kw in text for kw in self.VIDEO_KW):
            return asdict(RouteDecision(
                tier="video",
                model="wan-2.2-remix-nsfw",
                provider="vast-pod",
                endpoint="dynamic",
                engine="vast-native",
                reason="Video generation detected → Vast pod (spin-up / destroy)",
                estimated_cost_usd=0.25,
                requires_pod=True,
                pod_spec={
                    "type": "video",
                    "image": "vastai/comfyui-wan22:latest",
                    "gpu": "RTX_4090", "gpu_ram": 24, "disk_gb": 100,
                    "startup_wait_sec": 120
                }
            ))

        if any(kw in text for kw in self.IMAGE_KW):
            return asdict(RouteDecision(
                tier="image",
                model="flux-1-dev",
                provider="vast-pod",
                endpoint="dynamic",
                engine="vast-native",
                reason="Image generation detected → Vast pod",
                estimated_cost_usd=0.03,
                requires_pod=True,
                pod_spec={
                    "type": "image",
                    "image": "vastai/comfyui-flux:latest",
                    "gpu": "RTX_4090", "gpu_ram": 24, "disk_gb": 50,
                    "startup_wait_sec": 60
                }
            ))

        # ── LAYER 1: Trivial ───────────────────────────────────────────────
        if tokens < 100:
            for pat in self.TRIVIAL_RE:
                if re.match(pat, text):
                    return asdict(RouteDecision(
                        tier="nano",
                        model="nvidia/nemotron-nano-9b-v2",
                        provider="openrouter",
                        endpoint="https://openrouter.ai/api/v1",
                        engine="lmdeploy",
                        reason="Trivial heuristic — Nemotron Nano",
                        estimated_cost_usd=0.00004
                    ))

        # ── LAYER 2: Domain keywords ───────────────────────────────────────
        if any(kw in text for kw in self.OPUS_KW):
            return self._opus("High-stakes domain keyword")

        if any(kw in text for kw in self.UNFILTERED_KW):
            return asdict(RouteDecision(
                tier="uncensored",
                model="dolphin-2.9.4-llama3.1-8b",
                provider="vast-serverless",
                endpoint=os.environ.get("VAST_UNCENSORED_URL", "https://openrouter.ai/api/v1"),
                engine="sglang",
                reason="Uncensored content → Dolphin on Vast serverless",
                estimated_cost_usd=0.001
            ))

        if any(kw in text for kw in self.CODE_KW):
            engine = "sglang" if turns > 2 else "lmdeploy"
            return asdict(RouteDecision(
                tier="coder",
                model="Qwen/Qwen2.5-Coder-14B-Instruct",
                provider="vast-serverless",
                endpoint=os.environ.get("VAST_CODER_URL", "https://openrouter.ai/api/v1"),
                engine=engine,
                reason=f"Code task → Qwen Coder ({engine})",
                estimated_cost_usd=0.001
            ))

        # ── LAYER 3: Complexity Score ──────────────────────────────────────
        score = self._complexity(text, tokens)
        if score >= 8 or tokens > 4000:
            return self._opus(f"Complexity {score}/10, {int(tokens)} tokens")

        # Budget guard: if Opus daily spend > $3 → fallback to Super
        if score >= 6 and self._opus_spend_today() > 3.0:
            return self._super(f"Complexity {score}/10 — Opus over budget, using Super", turns)

        # ── LAYER 4 (L3 default): Engine selection for Nemotron Super ────
        return self._super(f"Standard reasoning, complexity {score}/10", turns)

    # ── helpers ─────────────────────────────────────────────────────────────

    def _super(self, reason: str, turns: int = 0) -> dict:
        # Multi-turn → SGLang RadixAttention for 85-95% cache reuse
        # First-call  → LMDeploy for lowest TTFT
        engine = "sglang" if turns > 3 else "lmdeploy"
        return asdict(RouteDecision(
            tier="super",
            model="nvidia/nemotron-3-super-120b-a12b",
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine=engine,
            reason=f"{reason} | engine={engine} (turns={turns})",
            estimated_cost_usd=0.002
        ))

    def _opus(self, reason: str) -> dict:
        return asdict(RouteDecision(
            tier="opus",
            model="anthropic/claude-opus-4.6",
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="claude",
            reason=reason,
            estimated_cost_usd=0.10
        ))

    def _complexity(self, text: str, tokens: float) -> int:
        score = 0
        if tokens > 500:  score += 2
        if tokens > 1500: score += 2
        score += min(sum(1 for kw in self.MULTI_STEP_KW  if kw in text), 2)
        score += min(sum(1 for kw in self.HIGH_STAKES_KW if kw in text), 2)
        score += min(text.count("?"), 1)
        return min(score, 10)

    def _opus_spend_today(self) -> float:
        try:
            from supabase import create_client
            sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
            today = time.strftime("%Y-%m-%d")
            rows = sb.table("cost_tracker").select("cost_usd") \
                     .eq("date", today).ilike("provider", "%opus%").execute()
            return sum(r["cost_usd"] for r in (rows.data or []))
        except:
            return 0.0


if __name__ == "__main__":
    r = NCoreMasterRouter()
    task  = sys.argv[1] if len(sys.argv) > 1 else "What is 2+2?"
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(r.route(task, turns), indent=2))
