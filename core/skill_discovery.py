"""NCore Genesis — Skill Auto-Discovery Agent v7.5

Searches ClawHub, PyPI, and GitHub for tools/skills relevant to a given task,
inspects source for supply-chain safety, and installs missing dependencies.

All subprocess calls are fully async.  Discoveries are persisted in Redis.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog

# ── structlog JSON logging ───────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# ── Constants ────────────────────────────────────────────────────────────────
REDIS_UDS = "/var/run/redis/redis-server.sock"
PYPI_SEARCH_URL = "https://pypi.org/simple/"
DANGEROUS_PATTERNS = ["curl", "wget", "eval(", "exec(", "base64", "subprocess", ".env", "api_key"]


# ── Redis helper ─────────────────────────────────────────────────────────────
def _redis() -> aioredis.Redis:
    return aioredis.Redis(unix_socket_path=REDIS_UDS, decode_responses=True)


# ── Subprocess helper ────────────────────────────────────────────────────────
async def _run_cmd(*args: str, timeout: float = 30) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "timeout"
    return proc.returncode, stdout.decode(), stderr.decode()


# ── Source-level supply-chain inspection ─────────────────────────────────────
async def _inspect_skill_source(skill_name: str) -> bool:
    """Return True if the skill source looks safe, False if suspicious."""
    code, source, stderr = await _run_cmd(
        "openclaw", "skill", "inspect", skill_name, "--show-source"
    )
    if code != 0:
        log.warning("skill.inspect_failed", name=skill_name, stderr=stderr)
        return False

    source_lower = source.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in source_lower:
            log.warning(
                "skill.suspicious",
                name=skill_name,
                reason=f"Dangerous pattern in source: {pattern}",
            )
            return False

    log.info("skill.source_safe", name=skill_name)
    return True


# ── Discovery sources ───────────────────────────────────────────────────────
async def _search_clawhub(query: str) -> list[dict]:
    code, stdout, _ = await _run_cmd("openclaw", "skill", "search", query)
    if code != 0:
        return []

    results = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        name = parts[0]
        desc = parts[1] if len(parts) > 1 else ""
        results.append({
            "name": name,
            "source": "clawhub",
            "description": desc,
            "install_command": f"openclaw skill install {name}",
            "confidence": 0.8,
        })
    return results


async def _search_pypi(query: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://pypi.org/pypi/{query}/json",
            )
            if resp.status_code == 200:
                data = resp.json()
                info = data.get("info", {})
                return [{
                    "name": info.get("name", query),
                    "source": "pypi",
                    "description": info.get("summary", ""),
                    "install_command": f"pip install {info.get('name', query)}",
                    "confidence": 0.7,
                }]

            # Fallback: search simple index for partial matches
            resp = await client.get(PYPI_SEARCH_URL)
            if resp.status_code != 200:
                return []

            matches = []
            query_lower = query.lower().replace(" ", "-")
            for line in resp.text.splitlines():
                if query_lower in line.lower():
                    # Extract package name from <a href="...">name</a>
                    start = line.find(">")
                    end = line.find("</")
                    if start != -1 and end != -1:
                        pkg = line[start + 1 : end].strip()
                        if pkg:
                            matches.append({
                                "name": pkg,
                                "source": "pypi",
                                "description": "",
                                "install_command": f"pip install {pkg}",
                                "confidence": 0.5,
                            })
                    if len(matches) >= 5:
                        break
            return matches
    except Exception as exc:
        log.warning("pypi.search_failed", error=str(exc))
        return []


async def _search_github(query: str) -> list[dict]:
    code, stdout, _ = await _run_cmd(
        "gh", "search", "repos", query, "--limit=5", "--json=fullName,description,url",
    )
    if code != 0:
        return []

    try:
        repos = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return []

    results = []
    for repo in repos:
        full_name = repo.get("fullName", "")
        results.append({
            "name": full_name.split("/")[-1] if "/" in full_name else full_name,
            "source": "github",
            "description": repo.get("description", ""),
            "install_command": f"git clone https://github.com/{full_name}.git",
            "confidence": 0.5,
        })
    return results


# ── Public API ───────────────────────────────────────────────────────────────
async def discover_tools(task_description: str) -> list[dict]:
    """Search all sources for tools relevant to *task_description*."""
    clawhub, pypi, github = await asyncio.gather(
        _search_clawhub(task_description),
        _search_pypi(task_description),
        _search_github(task_description),
    )
    all_tools = clawhub + pypi + github
    # Deduplicate by name
    seen: set[str] = set()
    unique: list[dict] = []
    for tool in all_tools:
        if tool["name"] not in seen:
            seen.add(tool["name"])
            unique.append(tool)
    return sorted(unique, key=lambda t: t["confidence"], reverse=True)


async def check_installed(tool_name: str) -> bool:
    """Check whether *tool_name* is already available on the system."""
    # pip
    code, _, _ = await _run_cmd("pip", "show", tool_name)
    if code == 0:
        return True

    # system binary
    code, _, _ = await _run_cmd("which", tool_name)
    if code == 0:
        return True

    # openclaw skill
    code, _, _ = await _run_cmd("openclaw", "skill", "list")
    if code == 0:
        code2, stdout, _ = await _run_cmd("openclaw", "skill", "list")
        if code2 == 0 and tool_name in stdout:
            return True

    return False


async def auto_install(tool: dict) -> bool:
    """Install *tool* if not already present. Returns success/failure."""
    name = tool["name"]
    source = tool["source"]

    if await check_installed(name):
        log.info("tool.already_installed", name=name)
        return True

    # Anti-supply-chain: inspect ClawHub skills before installation
    if source == "clawhub":
        if not await _inspect_skill_source(name):
            log.warning("tool.install_blocked", name=name, reason="suspicious source")
            return False

    log.info("tool.installing", name=name, source=source)
    install_cmd = tool["install_command"]
    code, stdout, stderr = await _run_cmd(*install_cmd.split(), timeout=120)

    if code == 0:
        log.info("tool.installed", name=name, source=source)
        return True

    log.error("tool.install_failed", name=name, stderr=stderr)
    return False


async def discover_and_equip(task: str) -> list[dict]:
    """Main entry: discover tools for *task*, install missing, persist to Redis."""
    tools = await discover_tools(task)
    if not tools:
        log.info("discovery.no_tools_found", task=task)
        return []

    newly_installed: list[dict] = []
    r = _redis()
    try:
        for tool in tools:
            already = await check_installed(tool["name"])
            if already:
                continue

            success = await auto_install(tool)
            if success:
                newly_installed.append(tool)
                await r.sadd("ncore:skills:installed", tool["name"])
                log.info("discovery.equipped", name=tool["name"], source=tool["source"])
    finally:
        await r.aclose()

    log.info(
        "discovery.complete",
        task=task,
        found=len(tools),
        installed=len(newly_installed),
    )
    return newly_installed
