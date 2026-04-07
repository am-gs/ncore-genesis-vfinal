"""NCore Genesis — Heuristic Prompt Enhancement Engine v7.5

Rewrites every incoming prompt for maximum output quality before routing.
  - 11-domain fraud/ops taxonomy with weighted keyword detection
  - Indicator extraction (emails, IPs, BTC, ETH, SSNs, URLs, phones, domains)
  - Domain-specific output templates
  - 8-point quality injection directives
  - Cinematic 8-layer framework for video/image prompts
  - Async Ollama critic loop with retry
  - FastAPI standalone endpoint on :8081
"""
from __future__ import annotations

import re
import time
from typing import Any

import httpx
import structlog

log = structlog.get_logger("prompt_enhancer")

# ── 1. Domain Taxonomy (11 domains) ─────────────────────────────────────────

FRAUD_DOMAINS: dict[str, list[str]] = {
    "identity": [
        "email", "phone", "ip", "address", "name", "dob", "ssn", "identity",
        "account", "takeover", "ato", "synthetic", "credential",
    ],
    "financial": [
        "transaction", "payment", "bank", "card", "money", "transfer",
        "laundering", "chargeback", "refund", "wire", "crypto", "wallet",
    ],
    "intel": [
        "breach", "leak", "dark web", "paste", "dump", "credential", "tor",
        "onion", "threat actor", "ttp", "ioc", "malware",
    ],
    "document": [
        "passport", "license", "id card", "forged", "fake document",
        "document fraud", "kyc", "verification",
    ],
    "social": [
        "phishing", "vishing", "smishing", "social engineering", "pretexting",
        "impersonation", "romance scam", "pig butcher",
    ],
    "video": [
        "video", "generate", "nsfw", "adult", "animate", "wan", "i2v",
        "motion", "scene", "cinematic",
    ],
    "image": [
        "image", "generate", "stable diffusion", "flux", "portrait", "render",
        "face", "photo",
    ],
    "code": [
        "code", "script", "function", "implement", "build", "execute",
        "python", "bash", "api", "deploy",
    ],
    "browser": [
        "scrape", "form", "account", "login", "automate", "click", "fill",
        "browser", "playwright", "selenium",
    ],
    "osint": [
        "osint", "recon", "investigate", "whois", "dns", "subdomain",
        "fingerprint", "enumerate", "harvest",
    ],
    "deploy": [
        "deploy", "cloudflare", "nginx", "pages", "server", "website",
        "landing page", "publish",
    ],
}

# Fraud-specific terms get 2x weight
_FRAUD_HEAVY: set[str] = {
    "ato", "synthetic", "laundering", "chargeback", "breach", "dark web",
    "threat actor", "ttp", "ioc", "malware", "forged", "fake document",
    "phishing", "vishing", "smishing", "pig butcher", "romance scam",
    "pretexting", "social engineering", "document fraud", "credential",
    "takeover", "dump", "paste", "onion", "tor",
}

# Pre-compile word-boundary patterns per domain
_DOMAIN_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {}
for _domain, _keywords in FRAUD_DOMAINS.items():
    _patterns = []
    for _kw in _keywords:
        _weight = 2.0 if _kw in _FRAUD_HEAVY else 1.0
        _patterns.append((re.compile(r"\b" + re.escape(_kw) + r"\b", re.IGNORECASE), _weight))
    _DOMAIN_PATTERNS[_domain] = _patterns


# ── 2. detect_domain — weighted regex, multi-domain ─────────────────────────

def detect_domain(prompt: str) -> list[tuple[str, float]]:
    """Return top-2 domains with confidence scores.  Falls back to [("general", 0.0)]."""
    scores: dict[str, float] = {}
    for domain, patterns in _DOMAIN_PATTERNS.items():
        total = 0.0
        for pat, weight in patterns:
            hits = len(pat.findall(prompt))
            total += hits * weight
        if total > 0:
            scores[domain] = total

    if not scores:
        return [("general", 0.0)]

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    # Normalise against the top score so the leader is always 1.0
    top_score = ranked[0][1]
    result = [(d, round(s / top_score, 2)) for d, s in ranked[:2]]
    return result


# ── 3. extract_indicators ───────────────────────────────────────────────────

_RE_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_RE_PHONE = re.compile(r"\+?\d[\d\-.\s]{7,}\d")
_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_DOMAIN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
_RE_BTC = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")
_RE_ETH = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_RE_URL = re.compile(r"https?://[^\s\"'>]+")
_RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Named entity patterns (heuristic — covers most Western names and US addresses)
_RE_US_ADDRESS = re.compile(
    r'\b(\d{1,6}\s+(?:[NSEW]\.?\s+)?(?:[A-Z][a-z]+\s*){1,4}'
    r'(?:St|Ave|Blvd|Dr|Rd|Ln|Ct|Way|Pl|Cir|Pkwy|Ter|Loop)'
    r'(?:\s*(?:#|Apt|Suite|Unit)\s*\w+)?)'
    r'(?:\s*,?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*([A-Z]{2})\s*(\d{5})?)?',
    re.IGNORECASE
)

# Simple name detection: 2-3 capitalized words after common prepositions/keywords
_RE_NAME_CONTEXT = re.compile(
    r'(?:on|about|for|named?|person|subject|target|check)\s+'
    r'["\']?([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)["\']?',
    re.MULTILINE
)


def extract_indicators(prompt: str) -> dict[str, list[str]]:
    """Extract IOCs, PII patterns, and named entities from the prompt text."""
    indicators = {
        "emails": _RE_EMAIL.findall(prompt),
        "phones": _RE_PHONE.findall(prompt),
        "ips": _RE_IPV4.findall(prompt),
        "domains": [d for d in _RE_DOMAIN.findall(prompt) if "." in d and not _RE_IPV4.match(d)],
        "btc_addresses": _RE_BTC.findall(prompt),
        "eth_addresses": _RE_ETH.findall(prompt),
        "urls": _RE_URL.findall(prompt),
        "ssns": _RE_SSN.findall(prompt),
    }

    # Entity extraction — names and addresses
    addresses = _RE_US_ADDRESS.findall(prompt)
    names = _RE_NAME_CONTEXT.findall(prompt)

    # Also try to extract name from "on [Name]" pattern at end of prompt
    on_name = re.findall(r'on\s+["\']?([A-Z][a-z]+\s+[A-Z][a-z]+)', prompt)
    if on_name and not names:
        names = on_name

    indicators["addresses"] = [a[0].strip() for a in addresses if a[0].strip()] if addresses else []
    indicators["names"] = list(set(names)) if names else []
    indicators["city_state"] = [(a[1].strip(), a[2].strip()) for a in addresses if len(a) > 2 and a[1]] if addresses else []

    return indicators


# ── 4. Output Templates ────────────────────────────────────────────────────

OUTPUT_TEMPLATES: dict[str, str] = {
    "identity": (
        "## Identity Analysis Report\n"
        "### Subject Summary\n- Full name / aliases:\n- DOB / age range:\n- Known emails:\n- Known phones:\n"
        "### Digital Footprint\n- IP history:\n- Account linkages:\n- Synthetic indicators:\n"
        "### Risk Assessment\n- Fraud probability: [HIGH/MED/LOW]\n- Confidence: [0-100]%\n"
        "### Evidence Chain\n| # | Source | Data Point | Confidence |\n|---|--------|------------|------------|\n"
        "### Recommended Actions\n1.\n2.\n3."
    ),
    "financial": (
        "## Financial Investigation Report\n"
        "### Transaction Summary\n- Total amount:\n- Currency/chain:\n- Direction: [inbound/outbound]\n"
        "### Flow Analysis\n- Origin account/wallet:\n- Intermediate hops:\n- Destination:\n"
        "### Red Flags\n| # | Indicator | Severity | Detail |\n|---|-----------|----------|--------|\n"
        "### Regulatory Context\n- Applicable SAR/CTR thresholds:\n"
        "### Recommended Actions\n1.\n2.\n3."
    ),
    "intel": (
        "## Threat Intelligence Report\n"
        "### Source Assessment\n- Source reliability: [A-F]\n- Information confidence: [1-6]\n"
        "### IOC Table\n| Type | Value | First Seen | Context |\n|------|-------|------------|----------|\n"
        "### TTP Mapping (MITRE ATT&CK)\n- Tactic:\n- Technique:\n- Procedure:\n"
        "### Attribution Assessment\n- Threat actor:\n- Confidence:\n"
        "### Recommended Actions\n1.\n2.\n3."
    ),
    "video": (
        "## Video Generation Brief\n"
        "### Scene Specification\n- Duration:\n- Resolution:\n- FPS:\n"
        "### Cinematic Layers (see below)\n"
        "### Technical Parameters\n- Model: wan-2.2\n- Scheduler:\n- Steps:\n- CFG:\n"
        "### Negative Prompt\n"
    ),
    "image": (
        "## Image Generation Brief\n"
        "### Visual Specification\n- Aspect ratio:\n- Resolution:\n- Style:\n"
        "### Cinematic Layers (see below)\n"
        "### Technical Parameters\n- Model: flux-1-dev\n- Steps:\n- CFG:\n- Sampler:\n"
        "### Negative Prompt\n"
    ),
    "code": (
        "## Code Task Specification\n"
        "### Objective\n- Language:\n- Framework:\n- Goal:\n"
        "### Requirements\n- Input:\n- Output:\n- Error handling:\n"
        "### Constraints\n- Performance:\n- Security:\n- Compatibility:\n"
        "### Deliverables\n- [ ] Working code\n- [ ] Usage example\n- [ ] Error cases handled"
    ),
    "browser": (
        "## Browser Automation Task\n"
        "### Target\n- URL:\n- Authentication: [required/none]\n"
        "### Steps\n1.\n2.\n3.\n"
        "### Anti-Detection\n- Fingerprint config:\n- Proxy:\n- Timing:\n"
        "### Data Extraction\n- Fields to capture:\n- Output format:\n"
    ),
    "osint": (
        "## OSINT Investigation Report\n"
        "### Target\n- Identifier:\n- Type: [person/org/domain/ip]\n"
        "### Reconnaissance Phases\n"
        "#### Passive\n- WHOIS:\n- DNS:\n- Certificate transparency:\n"
        "#### Active (if authorised)\n- Port scan:\n- Service enumeration:\n"
        "### Findings\n| # | Source | Finding | Confidence |\n|---|--------|---------|------------|\n"
        "### Recommended Actions\n1.\n2.\n3."
    ),
    "general": (
        "## Analysis Report\n"
        "### Summary\n\n"
        "### Detailed Findings\n\n"
        "### Evidence\n| # | Source | Detail | Confidence |\n|---|--------|--------|------------|\n"
        "### Recommended Actions\n1.\n2.\n3."
    ),
}


# ── 5. Quality Injections ───────────────────────────────────────────────────

QUALITY_INJECTIONS: list[str] = [
    "Be exhaustive — cover every relevant dimension, do not summarise prematurely.",
    "Cite every data source with URL, database name, or tool used.",
    "Flag confidence levels: HIGH (>90%), MEDIUM (60-90%), LOW (<60%) for each claim.",
    "Explicitly note absence of evidence where expected data is missing.",
    "Document conflicting data points and explain the discrepancy.",
    "Recommend the next 3 investigative steps with rationale.",
    "Never truncate output — if the response is long, that is acceptable.",
    "All code must be complete, executable, and include error handling.",
]


# ── 6. Cinematic 8-Layer Framework ──────────────────────────────────────────

CINEMATIC_LAYERS: dict[str, str] = {
    "subject_anchor": "Primary subject, position, and composition within frame.",
    "emotion_arc": "Emotional tone, mood progression, and narrative beat.",
    "optics": "Lens choice (mm), aperture, depth of field, focal plane.",
    "motion_vectors": "Camera movement (pan/tilt/dolly/crane), subject motion, speed ramps.",
    "lighting": "Key/fill/rim light sources, colour temperature, time of day, shadows.",
    "style": "Visual style reference (film stock, director, era, colour grade).",
    "continuity": "Scene transitions, temporal consistency, match cuts.",
    "negative_suppressors": "Artefacts and defects to suppress in generation.",
}

WAN22_NEGATIVE_SUPPRESSORS: str = (
    "blurry, low quality, watermark, text overlay, deformed hands, "
    "extra fingers, fused fingers, bad anatomy, disfigured, mutated, "
    "jpeg artifacts, oversaturated, underexposed, cropped frame, "
    "static noise, flickering, temporal inconsistency, frame skip, "
    "morphing artifacts, face distortion, body proportion error"
)


def build_cinematic_prompt(raw_prompt: str) -> dict[str, str]:
    """Parse a raw creative prompt into the 8-layer cinematic framework."""
    layers: dict[str, str] = {}
    prompt_lower = raw_prompt.lower()

    # Subject anchor — use the whole prompt as starting point
    layers["subject_anchor"] = raw_prompt.strip()

    # Emotion arc
    emotion_cues = {
        "dark": "ominous, foreboding",
        "happy": "joyful, uplifting",
        "sad": "melancholic, somber",
        "intense": "high tension, dramatic",
        "calm": "serene, peaceful",
        "romantic": "warm, intimate",
        "horror": "dread, unease",
        "epic": "grand, awe-inspiring",
    }
    detected_emotions = [v for k, v in emotion_cues.items() if k in prompt_lower]
    layers["emotion_arc"] = ", ".join(detected_emotions) if detected_emotions else "neutral, observational"

    # Optics
    if any(w in prompt_lower for w in ["close", "closeup", "close-up", "macro"]):
        layers["optics"] = "85mm f/1.4, shallow depth of field, bokeh background"
    elif any(w in prompt_lower for w in ["wide", "landscape", "establishing"]):
        layers["optics"] = "24mm f/8, deep focus, wide establishing frame"
    elif any(w in prompt_lower for w in ["portrait", "face"]):
        layers["optics"] = "50mm f/2.0, medium depth of field, subject isolation"
    else:
        layers["optics"] = "35mm f/2.8, natural perspective, balanced depth of field"

    # Motion vectors
    motion_map = {
        "pan": "smooth horizontal pan",
        "tilt": "vertical tilt",
        "dolly": "dolly push-in",
        "crane": "crane shot rising",
        "tracking": "lateral tracking shot",
        "static": "locked-off static frame",
        "slow motion": "120fps slow motion",
        "timelapse": "timelapse compression",
    }
    detected_motion = [v for k, v in motion_map.items() if k in prompt_lower]
    layers["motion_vectors"] = ", ".join(detected_motion) if detected_motion else "subtle handheld drift"

    # Lighting
    light_map = {
        "golden hour": "warm golden hour, low sun angle, long shadows",
        "night": "moonlit, cool blue ambient, practical light sources",
        "neon": "neon-lit, high contrast, cyan-magenta split",
        "studio": "three-point studio lighting, soft key, controlled fill",
        "natural": "natural available light, soft diffusion",
        "dramatic": "hard key light, deep shadows, chiaroscuro",
    }
    detected_light = [v for k, v in light_map.items() if k in prompt_lower]
    layers["lighting"] = ", ".join(detected_light) if detected_light else "soft natural ambient light"

    # Style
    style_map = {
        "anime": "anime cel-shaded, vibrant palette",
        "noir": "film noir, high contrast B&W, venetian blind shadows",
        "cyberpunk": "cyberpunk aesthetic, rain-slicked streets, holographic HUD",
        "cinematic": "anamorphic cinematic, 2.39:1 aspect, film grain",
        "realistic": "photorealistic, ARRI Alexa look, natural grade",
        "vintage": "vintage 16mm, warm grain, muted tones",
    }
    detected_style = [v for k, v in style_map.items() if k in prompt_lower]
    layers["style"] = ", ".join(detected_style) if detected_style else "cinematic realism, subtle film grain"

    # Continuity
    layers["continuity"] = "single continuous take, consistent lighting and colour temperature"

    # Negative suppressors
    layers["negative_suppressors"] = WAN22_NEGATIVE_SUPPRESSORS

    return layers


# ── 7. enhance() — main entry point ────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "ncore-critic"
CRITIC_MAX_RETRIES = 2


async def _call_critic(enhanced_prompt: str) -> tuple[int, str]:
    """Call local Ollama critic model for quality scoring.

    Returns (score, feedback).  Returns (-1, "") if Ollama is unavailable.
    """
    scoring_prompt = (
        "You are an expert prompt quality evaluator. Score the following enhanced prompt "
        "from 0 to 100 on: specificity, actionability, completeness, and clarity.\n\n"
        f"PROMPT:\n{enhanced_prompt}\n\n"
        "Respond ONLY with JSON: {\"score\": <int>, \"feedback\": \"<text>\"}"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": scoring_prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns the full text in "response" field
            import json as _json
            raw_text = data.get("response", "")
            # Try to extract JSON from the response text
            json_match = re.search(r"\{[^}]+\}", raw_text)
            if json_match:
                parsed = _json.loads(json_match.group())
                return int(parsed.get("score", 0)), str(parsed.get("feedback", ""))
            return 50, "Could not parse critic response"
    except (httpx.HTTPError, httpx.ConnectError, OSError, ValueError) as exc:
        log.warning("ollama_critic_unavailable", error=str(exc))
        return -1, ""


async def enhance(
    raw_prompt: str,
    context: str = "",
    task_id: str = "",
) -> dict[str, Any]:
    """Enhance a raw prompt through domain detection, templating, and critic loop.

    Returns dict with: enhanced, domains, indicators, original, timestamp,
    critic_score, and cinematic_layers (if video/image domain).
    """
    ts = time.time()
    log.info("enhance_start", task_id=task_id, prompt_len=len(raw_prompt))

    # (a) Detect domains
    domains = detect_domain(raw_prompt)
    primary_domain = domains[0][0]

    # (b) Extract indicators
    indicators = extract_indicators(raw_prompt)

    # (c) Select output template
    template = OUTPUT_TEMPLATES.get(primary_domain, OUTPUT_TEMPLATES["general"])

    # (d) Build enhanced prompt
    parts: list[str] = []
    parts.append(f"### TASK\n{raw_prompt}")

    if context:
        parts.append(f"\n### CONTEXT\n{context}")

    # Append extracted indicators if any were found
    found_indicators = {k: v for k, v in indicators.items() if v}
    if found_indicators:
        indicator_lines = "\n".join(f"- **{k}**: {', '.join(v)}" for k, v in found_indicators.items())
        parts.append(f"\n### EXTRACTED INDICATORS\n{indicator_lines}")

    parts.append(f"\n### REQUIRED OUTPUT FORMAT\n{template}")

    # (e) Cinematic layers for video/image
    cinematic_layers: dict[str, str] | None = None
    if primary_domain in ("video", "image"):
        cinematic_layers = build_cinematic_prompt(raw_prompt)
        layer_text = "\n".join(f"- **{k}**: {v}" for k, v in cinematic_layers.items())
        parts.append(f"\n### CINEMATIC LAYERS\n{layer_text}")

    # (d continued) Append quality injections
    injection_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(QUALITY_INJECTIONS))
    parts.append(f"\n### QUALITY DIRECTIVES\n{injection_text}")

    enhanced_prompt = "\n".join(parts)

    # (f/g) Critic loop
    critic_score = -1
    for attempt in range(1 + CRITIC_MAX_RETRIES):
        score, feedback = await _call_critic(enhanced_prompt)
        critic_score = score

        if score == -1:
            log.info("critic_skipped", reason="ollama_unavailable", task_id=task_id)
            break
        if score >= 70:
            log.info("critic_passed", score=score, attempt=attempt, task_id=task_id)
            break

        # Re-enhance with critic feedback
        log.info("critic_retry", score=score, attempt=attempt, task_id=task_id)
        enhanced_prompt += (
            f"\n\n### CRITIC FEEDBACK (attempt {attempt + 1}, score {score}/100)\n"
            f"{feedback}\n"
            "Address every point of feedback above to improve specificity and completeness."
        )

    result: dict[str, Any] = {
        "enhanced": enhanced_prompt,
        "domains": domains,
        "indicators": indicators,
        "original": raw_prompt,
        "timestamp": ts,
        "critic_score": critic_score,
    }
    if cinematic_layers is not None:
        result["cinematic_layers"] = cinematic_layers

    log.info(
        "enhance_done",
        task_id=task_id,
        primary_domain=primary_domain,
        critic_score=critic_score,
        elapsed=round(time.time() - ts, 3),
    )
    return result


# ── 8. FastAPI standalone endpoint ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(title="NCore Prompt Enhancer")

    @app.post("/enhance")
    async def enhance_endpoint(body: dict):
        result = await enhance(
            body["prompt"],
            body.get("context", ""),
            body.get("task_id", ""),
        )
        return result

    uvicorn.run(app, host="0.0.0.0", port=8081)
