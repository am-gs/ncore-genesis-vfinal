#!/usr/bin/env python3
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

LOG = Path('/home/ubuntu/sovereign/logs/watchdog.log')
LOG.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [WATCHDOG] %(message)s', handlers=[logging.FileHandler(LOG), logging.StreamHandler()])
log = logging.getLogger(__name__)


@dataclass
class Check:
    name: str
    urls: list[str] = field(default_factory=list)
    systemd: str | None = None
    compose: str | None = None
    docker: str | None = None
    failures: int = 0
    last_restart: float = 0.0


CHECKS = [
    Check('agent-zero', urls=['http://127.0.0.1:8090/api/health'], docker='agent-zero'),
    Check('llm', urls=['http://127.0.0.1:11434/v1/models'], systemd='ollama'),
    Check('sovereign-llm', systemd='sovereign-llm'),
    Check('bifrost', urls=['http://127.0.0.1:8000/health'], systemd='sovereign-bifrost'),
    Check('deerflow', urls=['http://127.0.0.1:2026/api/health'], systemd='sovereign-deerflow'),
    Check('mem0', urls=['http://127.0.0.1:8300/health'], systemd='sovereign-mem0'),
    Check('mission-control', urls=['http://127.0.0.1:3004/api/health'], systemd='sovereign-mission-control'),
    Check('dashboard', urls=['http://127.0.0.1:3002/'], systemd='ncore-dashboard'),
    Check('chroma', urls=['http://127.0.0.1:8200/api/v2/heartbeat', 'http://127.0.0.1:8200/api/v1/heartbeat'], compose='chroma'),
    Check('postgres', compose='postgres'),
    Check('redis', compose='redis'),
    Check('grafana', urls=['http://127.0.0.1:3001/login'], compose='grafana'),
]


def sh(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def url_ok(url: str) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=5)
        return r.status_code < 500, f'{url} -> {r.status_code}'
    except Exception as e:
        return False, f'{url} -> {type(e).__name__}: {e}'


def systemd_ok(unit: str) -> tuple[bool, str]:
    rc, out = sh(['systemctl', 'is-active', unit], timeout=10)
    return rc == 0 and out.strip() == 'active', f'{unit} is {out}'


def compose_ok(service: str) -> tuple[bool, str]:
    rc, out = sh(['docker', 'compose', '-f', '/home/ubuntu/sovereign/docker-compose.yml', '--env-file', '/home/ubuntu/sovereign/.env', 'ps', service], timeout=20)
    return rc == 0 and 'Up' in out, out.splitlines()[-1] if out else f'{service} missing'


def docker_ok(name: str) -> tuple[bool, str]:
    rc, out = sh(['docker', 'inspect', '-f', '{{.State.Running}} {{.State.Status}}', name], timeout=10)
    return rc == 0 and out.startswith('true'), out


def healthy(check: Check) -> tuple[bool, str]:
    details = []
    if check.urls:
        for url in check.urls:
            ok, detail = url_ok(url)
            details.append(detail)
            if ok:
                return True, '; '.join(details)
        return False, '; '.join(details)
    if check.systemd:
        return systemd_ok(check.systemd)
    if check.compose:
        return compose_ok(check.compose)
    if check.docker:
        return docker_ok(check.docker)
    return True, 'no check configured'


def restart(check: Check) -> None:
    now = time.time()
    if now - check.last_restart < 180:
        log.warning('%s unhealthy but restart suppressed to avoid crash loop', check.name)
        return
    check.last_restart = now
    if check.systemd:
        cmd = ['sudo', '-n', 'systemctl', 'restart', check.systemd]
    elif check.compose:
        cmd = ['docker', 'compose', '-f', '/home/ubuntu/sovereign/docker-compose.yml', '--env-file', '/home/ubuntu/sovereign/.env', 'restart', check.compose]
    elif check.docker:
        cmd = ['docker', 'restart', check.docker]
    else:
        return
    log.warning('restarting %s via %s', check.name, ' '.join(cmd))
    rc, out = sh(cmd, timeout=90)
    if rc:
        log.error('restart failed for %s rc=%s output=%s', check.name, rc, out[-1500:])
    else:
        log.info('restart issued for %s output=%s', check.name, out[-1000:])


def main() -> None:
    log.info('Sovereign Watchdog started')
    while True:
        for check in CHECKS:
            ok, detail = healthy(check)
            if ok:
                if check.failures:
                    log.info('%s recovered: %s', check.name, detail)
                check.failures = 0
                continue
            check.failures += 1
            log.warning('%s failed health %s/2: %s', check.name, check.failures, detail)
            if check.failures >= 2:
                restart(check)
                check.failures = 0
        time.sleep(30)


if __name__ == '__main__':
    main()
