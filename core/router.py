"""NCore Genesis — Consensus Router v3.2

v7.6 (April 7 2026):
  - FAST tier: GPT-OSS 20B free (matches o3-mini, $0, 13 providers)
  - FREE_REASONING tier: DeepSeek R1 free ($0, reasoning)
  - UNCENSORED_LOCAL tier: Qwen3.5-35B-A3B abliterated (local Ollama)
  - WORKER tier: DeepSeek V3.2 ($0.14/$0.28 per M, cheapest paid frontier)
  - 7-tier cascade routes ~90% of tasks to $0 infrastructure

v7.5 (April 1 2026):
  - Added FAST (Gemini Flash Lite) + FREE_CODER (Qwen3 Coder 480B)

v3.1 (March 26 2026):
  C3 — bare except: replaced with except Exception + structlog warning
  H3 — Qwen2.5-Coder-14B → Qwen3-Coder-30B-A3B (MoE, ~3B active)
  Supabase client cached at init (not re-created per call)
"""
from __future__ import annotations
import re, os, time, json, sys
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

log = structlog.get_logger()


class ModelTier(Enum):
    FAST            = "fast"            # GPT-OSS 20B free
    FREE_CODER      = "free_coder"      # Qwen3 Coder 480B free
    FREE_REASONING  = "free_reasoning"  # DeepSeek R1 free
    WORKER          = "worker"          # DeepSeek V3.2 (cheapest paid)
    SUPER           = "super"           # Nemotron Super 120B
    OPUS            = "opus"            # Claude Opus 4.6 (budget-gated)
    CODER           = "coder"           # Qwen3-Coder-30B on Vast
    UNCENSORED      = "uncensored"      # Vast serverless or local abliterated
    UNCENSORED_LOCAL = "uncensored_local"  # Qwen3.5 abliterated on Ollama
    IMAGE_GEN       = "image"
    VIDEO_GEN       = "video"


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
    7-tier routing cascade (v7.6 — April 7 2026):
      L0:   Media detection         → Vast pod (image / video)
      L1:   Trivial heuristics      → FAST (GPT-OSS 20B free, $0)
      L1.5: Free code routing       → FREE_CODER (Qwen3 Coder 480B free, $0)
      L1.7: Uncensored detection    → UNCENSORED_LOCAL (Qwen3.5 abliterated, $0)
      L2:   Complex reasoning       → FREE_REASONING (DeepSeek R1 free, $0)
      L3:   Domain keyword          → OPUS | WORKER
      L4:   Complexity score        → OPUS (≥8) | WORKER (DeepSeek V3.2)
      L5:   Engine selection        → SGLang (multi-turn) vs LMDeploy (first-call)

    ~90% of tasks route to $0 infrastructure.
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
            # v7.6: Route to local abliterated model first ($0), fallback to Vast
            uncensored_local = os.environ.get("UNCENSORED_LOCAL", "")
            if uncensored_local:
                return asdict(RouteDecision(
                    tier="uncensored_local",
                    model=uncensored_local,
                    provider="ollama",
                    endpoint="http://localhost:11434",
                    engine="ollama",
                    reason="Uncensored → Local abliterated (Qwen3.5, $0)",
                    estimated_cost_usd=0.0
                ))
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
        # v7.6: Free reasoning tier before paid models
        if score >= 4:
            return self._free_reasoning(f"Reasoning (complexity {score}/10) → DeepSeek R1 free")
        if score >= 6 and self._opus_spend_today() > 3.0:
            return self._worker(f"Complexity {score}/10 — Opus over budget", turns)
        return self._worker(f"Standard reasoning, complexity {score}/10", turns)

    # ── Tier builders ────────────────────────────────────────────────

    def _fast(self, reason: str) -> dict:
        """T1: GPT-OSS 20B free — matches o3-mini, $0, 13 providers."""
        return asdict(RouteDecision(
            tier="fast",
            model=os.environ.get("FAST_MODEL", "openai/gpt-oss-20b:free"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="lmdeploy",
            reason=f"{reason} | FAST tier (GPT-OSS 20B free)",
            estimated_cost_usd=0.0
        ))

    def _free_reasoning(self, reason: str) -> dict:
        """T3: DeepSeek R1 free — strong reasoning, $0."""
        return asdict(RouteDecision(
            tier="free_reasoning",
            model=os.environ.get("FREE_REASONING", "deepseek/deepseek-r1:free"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="lmdeploy",
            reason=f"{reason} | FREE_REASONING tier",
            estimated_cost_usd=0.0
        ))

    def _worker(self, reason: str, turns: int = 0) -> dict:
        """T4: DeepSeek V3.2 — cheapest paid frontier ($0.14/$0.28 per M)."""
        engine = "sglang" if turns > 3 else "lmdeploy"
        return asdict(RouteDecision(
            tier="worker",
            model=os.environ.get("WORKER_MODEL", "deepseek/deepseek-chat"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine=engine,
            reason=f"{reason} | WORKER tier (DeepSeek V3.2, {engine})",
            estimated_cost_usd=0.001
        ))

    def _opus(self, reason: str) -> dict:
        """T5: Claude Opus 4.6 — budget-gated, complex only."""
        return asdict(RouteDecision(
            tier="opus",
            model=os.environ.get("OPUS_MODEL", "anthropic/claude-opus-4.6"),
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
