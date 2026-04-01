"""NCore Genesis — Self-Healing Watchdog v7.5

Monitors all NCore services, recovers failures, cleans orphaned Vast.ai
instances, and watches system resources.  Designed for the Oracle Always-Free
ARM64 control plane (24 GB RAM).

Runs as a long-lived asyncio loop (60-second cadence) and can also generate
its own systemd unit file for hands-free startup.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path

import httpx
import psutil
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
CHECK_INTERVAL = 60  # seconds
MAX_RESTART_ATTEMPTS = 3
RESTART_WAIT = 10  # seconds between restart and re-check
ORPHAN_THRESHOLD_MIN = 30  # minutes before a Vast instance is considered orphaned
RAM_WARN_PCT = 90
DISK_WARN_PCT = 85
QUANTIZED_CACHE = Path("/tmp/ncore_quantized")
CACHE_STALE_HOURS = 24

SERVICES = [
    {
        "name": "ollama",
        "url": "http://localhost:11434/api/tags",
        "systemd_unit": "ollama",
    },
    {
        "name": "ncore-gateway",
        "url": "http://localhost:8080/health",
        "systemd_unit": "ncore-gateway",
    },
    {
        "name": "redis",
        "check": "redis_ping",
        "systemd_unit": "redis",
    },
    {
        "name": "openclaw",
        "url": "http://localhost:3000/health",
        "systemd_unit": "openclaw",
    },
]


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


# ── Service health checks ───────────────────────────────────────────────────
async def _check_http(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


async def _check_redis_ping() -> bool:
    try:
        r = _redis()
        try:
            return await r.ping()
        finally:
            await r.aclose()
    except Exception:
        return False


async def _is_healthy(svc: dict) -> bool:
    if svc.get("check") == "redis_ping":
        return await _check_redis_ping()
    return await _check_http(svc["url"])


async def _restart_service(unit: str) -> bool:
    code, _, stderr = await _run_cmd("systemctl", "restart", unit)
    if code != 0:
        log.error("service.restart_failed", unit=unit, stderr=stderr)
        return False
    return True


async def _record_failure(r: aioredis.Redis, name: str) -> None:
    ts = str(time.time())
    await r.hset("ncore:health:failures", name, ts)


async def check_services() -> None:
    r = _redis()
    try:
        for svc in SERVICES:
            name = svc["name"]
            unit = svc["systemd_unit"]

            if await _is_healthy(svc):
                log.debug("service.healthy", name=name)
                continue

            log.warning("service.unhealthy", name=name)
            recovered = False

            for attempt in range(1, MAX_RESTART_ATTEMPTS + 1):
                log.info("service.restarting", name=name, attempt=attempt)
                await _restart_service(unit)
                await asyncio.sleep(RESTART_WAIT)

                if await _is_healthy(svc):
                    log.info("service.recovered", name=name, attempt=attempt)
                    recovered = True
                    break

            if not recovered:
                log.critical(
                    "service.unrecoverable",
                    name=name,
                    attempts=MAX_RESTART_ATTEMPTS,
                )
                await _record_failure(r, name)
    finally:
        await r.aclose()


# ── Vast.ai orphan cleanup ──────────────────────────────────────────────────
async def check_orphan_pods() -> None:
    code, stdout, stderr = await _run_cmd("vastai", "show", "instances", "--raw", timeout=30)
    if code != 0:
        log.error("vastai.list_failed", stderr=stderr)
        return

    try:
        instances = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        log.error("vastai.parse_failed", raw=stdout[:200])
        return

    now = time.time()
    for inst in instances:
        inst_id = str(inst.get("id", ""))
        start_ts = inst.get("start_date")
        status = inst.get("actual_status", "")
        cur_state = inst.get("cur_state", "")

        if not start_ts:
            continue

        running_min = (now - start_ts) / 60
        has_active_job = cur_state == "running" and status == "running"

        if running_min > ORPHAN_THRESHOLD_MIN and not has_active_job:
            log.warning(
                "vastai.orphan_detected",
                instance_id=inst_id,
                running_minutes=round(running_min, 1),
            )
            d_code, _, d_err = await _run_cmd("vastai", "destroy", "instance", inst_id)
            if d_code == 0:
                log.info("vastai.orphan_destroyed", instance_id=inst_id)
            else:
                log.error("vastai.destroy_failed", instance_id=inst_id, stderr=d_err)


# ── System resource checks ──────────────────────────────────────────────────
async def check_resources() -> None:
    # RAM
    mem = psutil.virtual_memory()
    if mem.percent > RAM_WARN_PCT:
        log.warning(
            "resource.ram_high",
            used_pct=mem.percent,
            available_gb=round(mem.available / (1024**3), 2),
        )

    # Disk
    disk = psutil.disk_usage("/")
    if disk.percent > DISK_WARN_PCT:
        log.warning(
            "resource.disk_high",
            used_pct=disk.percent,
            free_gb=round(disk.free / (1024**3), 2),
        )
        # Clean stale quantized model cache
        if QUANTIZED_CACHE.exists():
            stale_cutoff = time.time() - (CACHE_STALE_HOURS * 3600)
            for entry in QUANTIZED_CACHE.iterdir():
                try:
                    if entry.stat().st_mtime < stale_cutoff:
                        if entry.is_dir():
                            shutil.rmtree(entry)
                        else:
                            entry.unlink()
                        log.info("cache.cleaned", path=str(entry))
                except OSError as exc:
                    log.warning("cache.clean_failed", path=str(entry), error=str(exc))


# ── systemd unit generator ───────────────────────────────────────────────────
def generate_systemd_unit(
    python_bin: str = "/usr/bin/python3",
    working_dir: str | None = None,
) -> str:
    wd = working_dir or str(Path(__file__).resolve().parent.parent)
    unit = f"""\
[Unit]
Description=NCore Genesis Self-Healing Watchdog
After=network.target redis.service

[Service]
Type=simple
ExecStart={python_bin} {Path(__file__).resolve()}
WorkingDirectory={wd}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    return unit


def install_systemd_unit(
    python_bin: str = "/usr/bin/python3",
    working_dir: str | None = None,
) -> str:
    unit_path = "/etc/systemd/system/ncore-watchdog.service"
    content = generate_systemd_unit(python_bin, working_dir)
    Path(unit_path).write_text(content)
    log.info("systemd.unit_installed", path=unit_path)
    return unit_path


# ── Main loop ────────────────────────────────────────────────────────────────
async def run_watchdog() -> None:
    log.info("watchdog.starting", interval=CHECK_INTERVAL)
    while True:
        await check_services()
        await check_orphan_pods()
        await check_resources()
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_watchdog())
