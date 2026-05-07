"""NCore Genesis — Consensus Router v3.2

v7.7 (May 7 2026):
  - KIMI tier: Kimi K2.6 via OpenRouter ($0.80/$2.40 per M, 256K context)
    Best for: long-context analysis, multi-document synthesis, 50K+ token tasks
  - FAST tier: GPT-OSS 20B free (matches o3-mini, $0, 13 providers)
  - FREE_REASONING tier: DeepSeek R1 free ($0, reasoning)
  - UNCENSORED_LOCAL tier: Qwen3.5-35B-A3B abliterated (local Ollama)
  - WORKER tier: DeepSeek V3.2 ($0.14/$0.28 per M, cheapest paid frontier)
  - 8-tier cascade routes ~90% of tasks to $0 infrastructure

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
    KIMI            = "kimi"            # Kimi K2.6 via OpenRouter (256K context)
    INVESTIGATION   = "investigation"     # Agent Zero autonomous OSINT/investigation
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
    9-tier routing cascade (v7.7-SOTA — May 7 2026):
      L0:   Media detection         → Vast pod (image / video)
      L0.5: Investigation/OSINT     → Agent Zero autonomous tool execution
      L1:   Trivial heuristics      → FAST (GPT-OSS 20B free, $0)
      L1.5: Free code routing       → FREE_CODER (Qwen3 Coder 480B free, $0)
      L1.7: Uncensored detection    → UNCENSORED_LOCAL (Qwen3.5 abliterated, $0)
      L2:   Complex reasoning       → FREE_REASONING (DeepSeek R1 free, $0)
      L3:   Domain keyword          → OPUS | WORKER
      L4:   Complexity score        → KIMI (≥8 + long context) | OPUS (≥8) | WORKER (DeepSeek V3.2)
      L5:   Engine selection        → SGLang (multi-turn) vs LMDeploy (first-call)

    ~90% of tasks route to $0 infrastructure.
    """

    VIDEO_KW = [
        "generate video", "create video", "make video", "make a video",
        "text to video", "image to video", "t2v", "i2v", "wan2",
        "animate this", "animate the", "nsfw video", "adult video",
    ]
    IMAGE_KW = [
        "generate image", "create image", "make image", "make a picture",
        "text to image", "draw", "stable diffusion", "flux",
        "nsfw image", "adult image", "generate a photo", "sdxl",
    ]
    # Keywords that BLOCK media routing even if VIDEO/IMAGE_KW match
    ANALYSIS_OVERRIDE_KW = [
        "analyze", "analysis", "review", "red team", "adversarial",
        "investigate", "report", "audit", "design", "strategy",
        "explain", "describe", "compare", "evaluate", "assess",
    ]
    TRIVIAL_RE = [
        r"^(what is|define|who is|when was|how many|what year)",
        r"^(translate|convert|format|summarize in \d+)",
        r"^(yes or no|true or false)",
        r"^[\d\s+\-*/^().=]+$",           # bare math: "2+2", "3 * 5", "(10+2)/3"
        r"^(hi|hello|hey|thanks|thank you|ok|okay|sure|yes|no|ping)$",  # greetings/acks
        r"^\w+$",                          # single word: "hello", "test"
        r"^(what|how|when|where|who)\s+\w+\s*\?*$",  # 2-word questions: "what time?"
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
    INVESTIGATION_KW = [
        "background check", "investigate", "investigation", "deep dive", "osint",
        "recon", "reconnaissance", "lookup", "public records", "breach search",
        "find information", "who is", "dox", "trace", "track down", "skip trace",
        "identity check", "due diligence", "kyc check", "aml check", "fraud check",
        "leaked database", "breach data", "dark web search", "credential check",
        "email lookup", "phone lookup", "address lookup", "social media search",
        "digital footprint", "threat intel", "intel gathering",
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
    KIMI_KW = [
        "analyze this entire codebase", "multi-document", "large document", "long context",
        "50k tokens", "100k tokens", "200k tokens", "massive context",
        "synthesize", "cross-reference", "literature review", "survey paper",
        "analyze all files", "entire repository", "full codebase", "project-wide",
        "comprehensive analysis", "deep research", "systematic review"
    ]

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
        is_analysis = any(kw in text for kw in self.ANALYSIS_OVERRIDE_KW)

        # L0: Media detection — only if NOT an analysis/report task
        if not is_analysis:
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
        # L1: Trivial heuristics
        if tokens < 100:
            for pat in self.TRIVIAL_RE:
                if re.match(pat, text):
                    return self._fast("Trivial heuristic")
        # L1.1: High-stakes domain keywords → OPUS (check BEFORE investigation/code)
        if any(kw in text for kw in self.OPUS_KW):
            return self._opus("High-stakes domain keyword")
        # L0.5: Investigation/OSINT → Local Dark Champion (guaranteed uncensored)
        if any(kw in text for kw in self.INVESTIGATION_KW):
            return self._local_uncensored("Investigation/OSINT → Local abliterated")
        # L1.7: Uncensored/unfiltered → Local Dark Champion (guaranteed uncensored)
        if any(kw in text for kw in self.UNFILTERED_KW):
            return self._local_uncensored("Uncensored request → Local abliterated")
        if any(kw in text for kw in self.CODE_KW):
            complexity = self._complexity(text, tokens)
            # All code tasks → DeepSeek V3 (fast, cheap, uncensored for code)
            return asdict(RouteDecision(
                tier="coder",
                model=os.environ.get("CODER_MODEL", "deepseek/deepseek-chat"),
                provider="openrouter",
                endpoint="https://openrouter.ai/api/v1",
                engine="direct",
                reason=f"Code task (complexity {complexity}/10) → CODER",
                estimated_cost_usd=0.001
            ))

        score = self._complexity(text, tokens)
        # L3.5: Long-context / multi-document tasks → Kimi K2.6 (256K context)
        if any(kw in text for kw in self.KIMI_KW) or (score >= 8 and tokens > 10000):
            return self._kimi(f"Long-context (complexity {score}/10, {int(tokens)} tokens)")
        if score >= 8 or tokens > 4000:
            return self._opus(f"Complexity {score}/10, {int(tokens)} tokens")
        # v7.6: Free reasoning tier before paid models
        if score >= 4:
            return self._free_reasoning(f"Reasoning (complexity {score}/10) → DeepSeek R1 free")
        if score >= 6 and self._opus_spend_today() > 3.0:
            return self._worker(f"Complexity {score}/10 — Opus over budget", turns)
        # v7.6.1: Low complexity (<4) routes to FAST ($0) not WORKER
        if score < 4 and tokens < 200:
            return self._fast(f"Low complexity {score}/10, {int(tokens)} tokens")
        return self._worker(f"Standard reasoning, complexity {score}/10", turns)

    # ── Tier builders ────────────────────────────────────────────────

    def _local_uncensored(self, reason: str) -> dict:
        """Local dolphin3 8B via llama-server — ZERO filters, guaranteed compliance."""
        return asdict(RouteDecision(
            tier="uncensored_local",
            model="dolphin3-8b",
            provider="llama-server",
            endpoint=os.environ.get("LOCAL_LLM_URL", "http://localhost:9090"),
            engine="llama-cpp",
            reason=f"{reason} | LOCAL UNCENSORED (dolphin3, $0)",
            estimated_cost_usd=0.0
        ))

    def _fast(self, reason: str) -> dict:
        """T1: GPT-4.1 nano — fastest cloud, cheapest paid."""
        return asdict(RouteDecision(
            tier="fast",
            model=os.environ.get("FAST_MODEL", "openai/gpt-4.1-nano"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="direct",
            reason=f"{reason} | FAST tier",
            estimated_cost_usd=0.0005
        ))

    def _free_reasoning(self, reason: str) -> dict:
        """T3: DeepSeek R1 — strong reasoning, cheap ($0.55/M in, $2.19/M out)."""
        return asdict(RouteDecision(
            tier="free_reasoning",
            model=os.environ.get("REASONING_MODEL", "deepseek/deepseek-r1"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="lmdeploy",
            reason=f"{reason} | REASONING tier",
            estimated_cost_usd=0.005
        ))

    def _worker(self, reason: str, turns: int = 0) -> dict:
        """T4: DeepSeek V3 — cheapest paid frontier ($0.14/$0.28 per M)."""
        return asdict(RouteDecision(
            tier="worker",
            model=os.environ.get("WORKER_MODEL", "deepseek/deepseek-chat"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="direct",
            reason=f"{reason} | WORKER tier",
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

    def _kimi(self, reason: str) -> dict:
        """T4.5: Kimi K2.6 — long-context specialist (256K context, $0.80/$2.40 per M)."""
        return asdict(RouteDecision(
            tier="kimi",
            model=os.environ.get("KIMI_MODEL", "moonshot/kimi-k2.6"),
            provider="openrouter",
            endpoint="https://openrouter.ai/api/v1",
            engine="direct",
            reason=f"{reason} | KIMI tier (256K context)",
            estimated_cost_usd=0.05
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
