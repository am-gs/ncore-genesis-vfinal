"""NCore Genesis — Consensus Router v3.1

Audit fixes applied (March 26 2026):
  C3 — bare except: replaced with except Exception + structlog warning
  H3 — Qwen2.5-Coder-14B → Qwen3-Coder-30B-A3B (MoE, ~3B active, better quality)
  Supabase client cached at init (not re-created per call)
"""
from __future__ import annotations
import re, os, time, json, sys
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

log = structlog.get_logger()


class ModelTier(Enum):
    FAST       = "fast"
    FREE_CODER = "free_coder"
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
    engine: str
    reason: str
    estimated_cost_usd: float
    requires_pod: bool = False
    pod_spec: dict = None


class NCoreMasterRouter:
    """
    5-layer routing (v7.5):
      L0:   Media detection    → Vast pod (image / video)
      L1:   Fast heuristics    → FAST (Gemini 3.1 Flash Lite, trivial)
      L1.5: Free code routing  → FREE_CODER (Qwen3 Coder 480B, complexity < 6)
      L2:   Domain keyword     → OPUS | UNCENSORED | CODER
      L3:   Complexity score   → OPUS (≥8) | SUPER
      L4:   Engine selection   → SGLang (multi-turn) vs LMDeploy (first-call)
    """

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
    TRIVIAL_RE = [
        r"^(what is|define|who is|when was|how many|what year)",
        r"^(translate|convert|format|summarize in \d+)",
        r"^(yes or no|true or false)",
    ]
    OPUS_KW = [
        "legal", "contract", "lawsuit", "compliance", "regulation",
        "medical", "diagnosis", "treatment", "clinical", "pharmaceutical",
        "financial", "investment", "portfolio", "tax strategy", "audit",
        "analyze this entire document", "comprehensive review",
        "peer review", "research paper", "academic", "thesis",
        "extremely complex", "expert level", "red team", "adversarial"
    ]
    # H3: updated to Qwen3-Coder (30B-A3B MoE, ~3B active params, SOTA March 2026)
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
    MULTI_STEP_KW = ["then", "after that", "next", "step by step", "workflow",
                     "pipeline", "sequence", "multiple steps", "chain"]
    HIGH_STAKES_KW = ["production", "deploy", "critical", "mission", "urgent",
                      "must be correct", "cannot fail", "important"]

    def __init__(self):
        # Cache Supabase client at init (not per-call) — C3 improvement
        self._sb = None
        self._sb_init_tried = False

    def _get_sb(self):
        if self._sb is None and not self._sb_init_tried:
            self._sb_init_tried = True
            try:
                from supabase import create_client
                self._sb = create_client(
                    os.environ["SUPABASE_URL"],
                    os.environ["SUPABASE_KEY"]
                )
            except Exception as e:                          # C3: not bare except
                log.warning("ncore.router.supabase_init_failed", error=str(e))
        return self._sb

    def route(self, task: str, turns: int = 0) -> dict:
        text   = task.lower().strip()
        tokens = len(task.split()) * 1.3

        if any(kw in text for kw in self.VIDEO_KW):
            return asdict(RouteDecision(
                tier="video", model="wan-2.2-remix-nsfw",
                provider="vast-pod", endpoint="dynamic", engine="vast-native",
                reason="Video generation → Vast pod",
                estimated_cost_usd=0.25, requires_pod=True,
                pod_spec={"type":"video","image":"vastai/comfyui-wan22:latest",
                          "gpu":"RTX_4090","gpu_ram":24,"disk_gb":100,"startup_wait_sec":120}
            ))
        if any(kw in text for kw in self.IMAGE_KW):
            return asdict(RouteDecision(
                tier="image", model="flux-1-dev",
                provider="vast-pod", endpoint="dynamic", engine="vast-native",
                reason="Image generation → Vast pod",
                estimated_cost_usd=0.03, requires_pod=True,
                pod_spec={"type":"image","image":"vastai/comfyui-flux:latest",
                          "gpu":"RTX_4090","gpu_ram":24,"disk_gb":50,"startup_wait_sec":60}
            ))
        if tokens < 100:
            for pat in self.TRIVIAL_RE:
                if re.match(pat, text):
                    return self._fast("Trivial heuristic")
        if any(kw in text for kw in self.OPUS_KW):
            return self._opus("High-stakes domain keyword")
        if any(kw in text for kw in self.UNFILTERED_KW):
            return asdict(RouteDecision(
                tier="uncensored", model="dolphin-2.9.4-llama3.1-8b",
                provider="vast-serverless",
                endpoint=os.environ.get("VAST_UNCENSORED_URL", "https://openrouter.ai/api/v1"),
                engine="sglang",
                reason="Uncensored → Dolphin on Vast serverless",
                estimated_cost_usd=0.001
            ))
        if any(kw in text for kw in self.CODE_KW):
            complexity = self._complexity(text, tokens)
            if complexity < 6:
                return asdict(RouteDecision(
                    tier="free_coder",
                    model=os.environ.get("FREE_CODER_MODEL", "qwen/qwen3-coder-480b-a35b-instruct:free"),
                    provider="openrouter",
                    endpoint="https://openrouter.ai/api/v1",
                    engine="lmdeploy",
                    reason=f"Code task (complexity {complexity}/10) → FREE_CODER",
                    estimated_cost_usd=0.0
                ))
            engine = "sglang" if turns > 2 else "lmdeploy"
            return asdict(RouteDecision(
                tier="coder",
                model="Qwen/Qwen3-Coder-30B-A3B-Instruct",   # H3: updated from Qwen2.5
                provider="vast-serverless",
                endpoint=os.environ.get("VAST_CODER_URL", "https://openrouter.ai/api/v1"),
                engine=engine,
                reason=f"Code task (complexity {complexity}/10) → Qwen3-Coder ({engine})",
                estimated_cost_usd=0.001
            ))

        score = self._complexity(text, tokens)
        if score >= 8 or tokens > 4000:
            return self._opus(f"Complexity {score}/10, {int(tokens)} tokens")
        if score >= 6 and self._opus_spend_today() > 3.0:
            return self._super(f"Complexity {score}/10 — Opus over budget", turns)
        return self._super(f"Standard reasoning, complexity {score}/10", turns)

    def _super(self, reason: str, turns: int = 0) -> dict:
        engine = "sglang" if turns > 3 else "lmdeploy"
        return asdict(RouteDecision(
            tier="super", model="nvidia/nemotron-3-super-120b-a12b",
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine=engine,
            reason=f"{reason} | engine={engine}",
            estimated_cost_usd=0.002
        ))

    def _fast(self, reason: str) -> dict:
        return asdict(RouteDecision(
            tier="fast",
            model=os.environ.get("FAST_MODEL", "google/gemini-3.1-flash-lite"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="lmdeploy",
            reason=f"{reason} | FAST tier",
            estimated_cost_usd=0.00001
        ))

    def _opus(self, reason: str) -> dict:
        return asdict(RouteDecision(
            tier="opus", model="anthropic/claude-opus-4.6",
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="claude", reason=reason,
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
        sb = self._get_sb()
        if sb is None:
            return 0.0
        try:
            today = time.strftime("%Y-%m-%d")
            rows  = sb.table("cost_tracker").select("cost_usd") \
                      .eq("date", today).ilike("provider", "%opus%").execute()
            return sum(r["cost_usd"] for r in (rows.data or []))
        except Exception as e:                               # C3: not bare except
            log.warning("ncore.router.spend_check_failed", error=str(e))
            return 0.0


if __name__ == "__main__":
    import sys
    r = NCoreMasterRouter()
    task  = sys.argv[1] if len(sys.argv) > 1 else "What is 2+2?"
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(r.route(task, turns), indent=2))
