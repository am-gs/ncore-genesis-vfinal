"""
NCore Critic — Tri-layer verification pipeline.

Layer 1: Semantic validation (does output match the stated intent?)
Layer 2: Technical validation (code compiles / syntax check via Ollama local models)
Layer 3: Policy validation (hard-stop content, dual-use authorization)

Uses Bifrost client for remote model calls; falls back to Ollama
ncore-reasoning:21b for local validation.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
import structlog

log = structlog.get_logger()

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LOCAL_FALLBACK_MODEL = os.environ.get("LOCAL_CRITIC_MODEL", "ncore-reasoning:21b")


# ---------------------------------------------------------------------------
# Validation Result Model
# ---------------------------------------------------------------------------

@dataclass
class CriticResult:
    overall: str  # "pass" | "fail" | "warn"
    layer1_semantic: str = ""
    layer2_technical: str = ""
    layer3_policy: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "layer1_semantic": self.layer1_semantic,
            "layer2_technical": self.layer2_technical,
            "layer3_policy": self.layer3_policy,
            "details": self.details,
            "latency_ms": self.latency_ms,
        }


# ---------------------------------------------------------------------------
# Policy Patterns (mirrors Bifrost proxy enforcement)
# ---------------------------------------------------------------------------

HARD_STOP_PATTERNS = [
    "csam", "child sexual", "minor sexual", "underage sexual",
    "sexual content involving minors", "hurt someone", "kill someone",
    "bodily harm", "make a bomb", "assassinate",
]

DUAL_USE_AUTH_PATTERNS = [
    "phish real", "steal credentials", "credential theft", "deploy malware",
    "persistence", "evasion", "exploit this ip", "hack this", "unauthorized",
    "bypass detection", "exfiltrate",
]

DUAL_USE_WHITELIST = [
    "authorized", "owned", "lab", "ctf", "sandbox", "tabletop",
    "simulation", "defensive",
]


def _contains_any(text: str, patterns: List[str]) -> bool:
    low = text.lower()
    return any(p in low for p in patterns)


def _hard_stop(text: str) -> bool:
    return _contains_any(text, HARD_STOP_PATTERNS)


def _dual_use_needs_auth(text: str) -> bool:
    low = text.lower()
    if any(w in low for w in DUAL_USE_WHITELIST):
        return False
    return _contains_any(text, DUAL_USE_AUTH_PATTERNS)


# ---------------------------------------------------------------------------
# LLM Backend
# ---------------------------------------------------------------------------

async def _local_chat(messages: List[dict], model: str = LOCAL_FALLBACK_MODEL, temperature: float = 0.1) -> str:
    """Chat via local Ollama endpoint."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": 512},
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        if r.status_code == 200:
            data = r.json()
            return data.get("message", {}).get("content", "")
        log.warning("critic.local_chat_error", status=r.status_code, body=r.text[:200])
        return ""
    except Exception as e:
        log.warning("critic.local_chat_exception", error=str(e))
        return ""


async def _bifrost_chat(
    model: str,
    messages: List[dict],
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """Chat via Bifrost client (imported lazily to avoid circular deps)."""
    from core.bifrost_client import get_bifrost
    try:
        bc = get_bifrost()
        resp = await bc.chat_completion(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        return resp.get("content", "")
    except Exception as e:
        log.warning("critic.bifrost_chat_exception", error=str(e))
        return ""


async def _llm_ask(messages: List[dict], use_local_fallback: bool = True) -> str:
    """Prefer Bifrost remote; fall back to Ollama local.

    If Bifrost returns empty (refusal/format failure), retry via OpenRouter
    free-tier before local fallback, per sovereign stack policy.
    """
    remote = await _bifrost_chat("deepseek/deepseek-chat", messages)
    if remote.strip():
        return remote

    # OpenRouter free-tier lane for soft refusals / structured-output failures
    or_free = await _bifrost_chat("openrouter/free", messages)
    if or_free.strip():
        log.info("critic.openrouter_free_fallback")
        return or_free

    if use_local_fallback:
        local = await _local_chat(messages)
        return local
    return ""


# ---------------------------------------------------------------------------
# Layer 1: Semantic Validation
# ---------------------------------------------------------------------------

async def _layer1_semantic(intent: str, output: str) -> tuple[str, str]:
    """Return (verdict, explanation)."""
    system = (
        "You are a strict semantic validator. Given a user's original intent and an output, "
        "reply with ONLY one of these verdicts on its own line: PASS, WARN, or FAIL. "
        "Then add a 1-sentence explanation. No markdown fences."
    )
    user = f"Intent:\n{intent}\n\nOutput:\n{output}\n\nVerdict:"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    raw = await _llm_ask(messages)
    first = raw.strip().splitlines()[0].strip().upper()
    if "PASS" in first:
        return "pass", raw.strip()
    if "FAIL" in first:
        return "fail", raw.strip()
    return "warn", raw.strip()


# ---------------------------------------------------------------------------
# Layer 2: Technical Validation
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)


def _extract_code(output: str) -> List[tuple[str, str]]:
    """Extract (lang, code) tuples from markdown fences."""
    results = []
    for match in _CODE_BLOCK_RE.finditer(output):
        lang = (match.group(1) or "").strip().lower()
        code = match.group(2)
        results.append((lang, code))
    return results


def _quick_syntax_check(lang: str, code: str) -> Optional[str]:
    """Try a lightweight compile for Python/JS. Return error string or None."""
    if lang in ("python", "py"):
        try:
            compile(code, "<string>", "exec")
            return None
        except SyntaxError as e:
            return f"Python syntax error: {e}"
    if lang in ("javascript", "js", "node"):
        # node --check via subprocess if available
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
                f.write(code)
                f.flush()
                p = subprocess.run(
                    ["node", "--check", f.name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                os.unlink(f.name)
                if p.returncode != 0:
                    return f"JS check error: {p.stderr.strip()[:200]}"
                return None
        except FileNotFoundError:
            return "node not available for JS syntax check"
        except Exception as e:
            return f"JS check exception: {e}"
    # Unsupported language — skip strict check
    return None


async def _layer2_technical(output: str) -> tuple[str, str, List[str]]:
    """Return (verdict, explanation, errors)."""
    blocks = _extract_code(output)
    if not blocks:
        return "pass", "No code blocks found; nothing to validate.", []

    errors: List[str] = []
    for lang, code in blocks:
        err = _quick_syntax_check(lang, code)
        if err:
            errors.append(err)

    if errors:
        return "fail", f"Technical validation failed with {len(errors)} error(s).", errors
    return "pass", f"All {len(blocks)} code block(s) passed syntax checks.", []


# ---------------------------------------------------------------------------
# Layer 3: Policy Validation
# ---------------------------------------------------------------------------

async def _layer3_policy(output: str) -> tuple[str, str]:
    """Return (verdict, explanation)."""
    if _hard_stop(output):
        return "fail", "Hard-stop content detected (CSAM / bodily harm)."
    if _dual_use_needs_auth(output):
        return "warn", "Dual-use content detected; requires explicit authorization/scope."
    return "pass", "No policy violations detected."


# ---------------------------------------------------------------------------
# Public Entrypoint
# ---------------------------------------------------------------------------

async def critic_validate(intent: str, output: str) -> CriticResult:
    """Run the full tri-layer critic on an intent/output pair."""
    started = asyncio.get_event_loop().time()

    l1_verdict, l1_exp = await _layer1_semantic(intent, output)
    l2_verdict, l2_exp, l2_errors = await _layer2_technical(output)
    l3_verdict, l3_exp = await _layer3_policy(output)

    overall = "pass"
    if l1_verdict == "fail" or l2_verdict == "fail" or l3_verdict == "fail":
        overall = "fail"
    elif l1_verdict == "warn" or l3_verdict == "warn":
        overall = "warn"

    latency = (asyncio.get_event_loop().time() - started) * 1000

    result = CriticResult(
        overall=overall,
        layer1_semantic=l1_exp,
        layer2_technical=l2_exp,
        layer3_policy=l3_exp,
        details={"layer2_errors": l2_errors},
        latency_ms=round(latency, 2),
    )

    log.info(
        "critic.result",
        overall=overall,
        l1=l1_verdict,
        l2=l2_verdict,
        l3=l3_verdict,
        latency_ms=result.latency_ms,
    )
    return result
