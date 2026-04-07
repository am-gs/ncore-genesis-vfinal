#!/usr/bin/env bash
# NCore Genesis v7.6 — Pre-installed Skill Stack
# Installs verified, fraud-domain ClawHub skills so the system never starts cold.
# Sources: ClawHub registry, VoltAgent/awesome-openclaw-skills, DataCamp guide
set -euo pipefail

echo "═══════════════════════════════════════════════════"
echo "  NCore v7.6 — Installing Core Skill Stack"
echo "═══════════════════════════════════════════════════"

# Check if openclaw CLI is available
if ! command -v openclaw &>/dev/null; then
    echo "[SKIP] OpenClaw CLI not found — skills will be discovered at runtime"
    exit 0
fi

# ── SELF-EVOLUTION (install first — makes everything else better) ──────────
echo ""
echo "[1/7] Self-Evolution & Learning..."
openclaw skill install capability-evolver 2>/dev/null && echo "  ✅ capability-evolver (35K+ installs — self-evolution engine)" || echo "  ⚠️ capability-evolver skipped"
openclaw skill install self-improving-agent 2>/dev/null && echo "  ✅ self-improving-agent (15K+ installs — logs errors/corrections, promotes to skills)" || echo "  ⚠️ self-improving-agent skipped"
openclaw skill install agent-memory 2>/dev/null && echo "  ✅ agent-memory (persistent file-based memory)" || echo "  ⚠️ agent-memory skipped"
openclaw skill install openclaw-memory-enhancer 2>/dev/null && echo "  ✅ openclaw-memory-enhancer (RAG-style persistent memory)" || echo "  ⚠️ openclaw-memory-enhancer skipped"
openclaw skill install task-decomposer 2>/dev/null && echo "  ✅ task-decomposer (complex request decomposition)" || echo "  ⚠️ task-decomposer skipped"
openclaw skill install agent-self-reflection 2>/dev/null && echo "  ✅ agent-self-reflection (periodic session self-assessment)" || echo "  ⚠️ agent-self-reflection skipped"

# ── OSINT & RECONNAISSANCE ────────────────────────────────────────────────
echo ""
echo "[2/7] OSINT & Reconnaissance..."
openclaw skill install tavily-web-search 2>/dev/null && echo "  ✅ tavily-web-search (AI-optimized search)" || echo "  ⚠️ tavily-web-search skipped"
openclaw skill install exa-web-search-free 2>/dev/null && echo "  ✅ exa-web-search-free (free AI web search)" || echo "  ⚠️ exa-web-search-free skipped"
openclaw skill install brightdata 2>/dev/null && echo "  ✅ brightdata (anti-bot web scraping)" || echo "  ⚠️ brightdata skipped"
openclaw skill install agent-browser 2>/dev/null && echo "  ✅ agent-browser (11K+ installs — browser automation)" || echo "  ⚠️ agent-browser skipped"
openclaw skill install web-scraper 2>/dev/null && echo "  ✅ web-scraper (structured data extraction)" || echo "  ⚠️ web-scraper skipped"

# ── FRAUD & FINANCIAL INVESTIGATION ───────────────────────────────────────
echo ""
echo "[3/7] Fraud & Financial Investigation..."
openclaw skill install penclaw 2>/dev/null && echo "  ✅ penclaw (pentest orchestration — recon, exploit chaining)" || echo "  ⚠️ penclaw skipped"
openclaw skill install audit-code 2>/dev/null && echo "  ✅ audit-code (security code review — secrets, vuln detection)" || echo "  ⚠️ audit-code skipped"
openclaw skill install agentic-security-audit 2>/dev/null && echo "  ✅ agentic-security-audit (codebase + infra + AI system audit)" || echo "  ⚠️ agentic-security-audit skipped"

# ── DATA ANALYSIS & PROCESSING ────────────────────────────────────────────
echo ""
echo "[4/7] Data Analysis & Processing..."
openclaw skill install duckdb 2>/dev/null && echo "  ✅ duckdb (fast analytics on CSV/Parquet/JSON)" || echo "  ⚠️ duckdb skipped"
openclaw skill install csv-toolkit 2>/dev/null && echo "  ✅ csv-toolkit (Miller + csvkit + xsv)" || echo "  ⚠️ csv-toolkit skipped"

# ── MEDIA GENERATION ──────────────────────────────────────────────────────
echo ""
echo "[5/7] Media Generation..."
openclaw skill install creative-toolkit 2>/dev/null && echo "  ✅ creative-toolkit (1300+ prompts, ComfyUI support, image gen)" || echo "  ⚠️ creative-toolkit skipped"
openclaw skill install comfyui 2>/dev/null && echo "  ✅ comfyui (ComfyUI workflow API bridge)" || echo "  ⚠️ comfyui skipped"
openclaw skill install ai-video-gen 2>/dev/null && echo "  ✅ ai-video-gen (end-to-end video generation)" || echo "  ⚠️ ai-video-gen skipped"

# ── AUTOMATION & ORCHESTRATION ────────────────────────────────────────────
echo ""
echo "[6/7] Automation & Orchestration..."
openclaw skill install agent-weave 2>/dev/null && echo "  ✅ agent-weave (master-worker parallel task execution)" || echo "  ⚠️ agent-weave skipped"
openclaw skill install agent-task-manager 2>/dev/null && echo "  ✅ agent-task-manager (multi-step stateful orchestration)" || echo "  ⚠️ agent-task-manager skipped"
openclaw skill install advanced-skill-creator 2>/dev/null && echo "  ✅ advanced-skill-creator (auto-create new skills)" || echo "  ⚠️ advanced-skill-creator skipped"

# ── SECURITY & TRUST ──────────────────────────────────────────────────────
echo ""
echo "[7/7] Security & Trust..."
openclaw skill install aegis-shield 2>/dev/null && echo "  ✅ aegis-shield (prompt injection + data exfiltration screening)" || echo "  ⚠️ aegis-shield skipped"
openclaw skill install arc-trust-verifier 2>/dev/null && echo "  ✅ arc-trust-verifier (skill provenance + trust scoring)" || echo "  ⚠️ arc-trust-verifier skipped"
openclaw skill install arc-security-audit 2>/dev/null && echo "  ✅ arc-security-audit (full skill stack security audit)" || echo "  ⚠️ arc-security-audit skipped"

echo ""
echo "═══════════════════════════════════════════════════"
INSTALLED=$(openclaw skill list 2>/dev/null | wc -l || echo "?")
echo "  Core skill stack installed: ~$INSTALLED skills ready"
echo "  + 44,000+ available on ClawHub for runtime discovery"
echo "═══════════════════════════════════════════════════"
