"""NLLM.ING Sandbox Manager — Persistent Workspaces v1.0

Manus.im pattern: each task gets a persistent workspace where files, scripts,
outputs, and intermediate results accumulate across agent iterations.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

WORKSPACE_ROOT = Path(os.environ.get("NLLM_WORKSPACE", "/tmp/nllm-workspace"))
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DIR = WORKSPACE_ROOT / ".checkpoints"
CHECKPOINT_DIR.mkdir(exist_ok=True)


class SandboxManager:
    """Manages persistent task workspaces with checkpoint/restore."""

    def __init__(self, root: Path | None = None, max_age_days: int = 7):
        self.root = root or WORKSPACE_ROOT
        self.max_age_days = max_age_days

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def create(self, task_id: str) -> Path:
        ws = self.root / task_id
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "scripts").mkdir(exist_ok=True)
        (ws / "outputs").mkdir(exist_ok=True)
        (ws / "data").mkdir(exist_ok=True)
        log.info("sandbox.created", task_id=task_id, path=str(ws))
        return ws

    def get(self, task_id: str) -> Path | None:
        ws = self.root / task_id
        return ws if ws.exists() else None

    def destroy(self, task_id: str):
        ws = self.get(task_id)
        if ws:
            shutil.rmtree(ws, ignore_errors=True)
            log.info("sandbox.destroyed", task_id=task_id)

    # ── File operations ───────────────────────────────────────────────────────

    def read_file(self, task_id: str, rel_path: str) -> str:
        ws = self.get(task_id)
        if not ws:
            return ""
        p = ws / rel_path
        return p.read_text() if p.exists() else ""

    def write_file(self, task_id: str, rel_path: str, content: str | bytes):
        ws = self.create(task_id)
        p = ws / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)

    def list_files(self, task_id: str) -> list[dict]:
        ws = self.get(task_id)
        if not ws:
            return []
        files = []
        for p in sorted(ws.rglob("*")):
            if p.is_file():
                files.append(
                    {
                        "path": str(p.relative_to(ws)),
                        "size": p.stat().st_size,
                        "modified": p.stat().st_mtime,
                    }
                )
        return files

    def get_size(self, task_id: str) -> int:
        ws = self.get(task_id)
        if not ws:
            return 0
        total = 0
        for p in ws.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    # ── Checkpoint / Restore ─────────────────────────────────────────────────

    def checkpoint(self, task_id: str, metadata: dict | None = None) -> dict:
        """Serialize workspace state for recovery."""
        ws = self.get(task_id)
        if not ws:
            return {}

        files: dict[str, str] = {}
        for p in ws.rglob("*"):
            if p.is_file() and p.stat().st_size < 1_000_000:
                try:
                    files[str(p.relative_to(ws))] = p.read_text()
                except UnicodeDecodeError:
                    files[str(p.relative_to(ws))] = "[binary]"

        cp = {
            "task_id": task_id,
            "timestamp": time.time(),
            "metadata": metadata or {},
            "files": files,
        }

        cp_path = CHECKPOINT_DIR / f"{task_id}-{int(time.time())}.json"
        cp_path.write_text(json.dumps(cp, indent=2, default=str))
        log.info("sandbox.checkpoint", task_id=task_id, files=len(files), path=str(cp_path))
        return cp

    def restore(self, task_id: str, checkpoint: dict | None = None) -> bool:
        """Restore workspace from checkpoint (latest if none provided)."""
        ws = self.create(task_id)

        if checkpoint is None:
            # Find latest checkpoint for this task_id
            candidates = sorted(
                CHECKPOINT_DIR.glob(f"{task_id}-*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                log.warning("sandbox.restore_no_checkpoint", task_id=task_id)
                return False
            checkpoint = json.loads(candidates[0].read_text())

        for rel_path, content in checkpoint.get("files", {}).items():
            p = ws / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

        log.info(
            "sandbox.restored",
            task_id=task_id,
            files=len(checkpoint.get("files", {})),
        )
        return True

    # ── Maintenance ───────────────────────────────────────────────────────────

    def cleanup_old(self):
        """Remove workspaces older than max_age_days."""
        cutoff = time.time() - (self.max_age_days * 86400)
        removed = 0
        for entry in self.root.iterdir():
            if entry.is_dir() and entry.name.startswith("."):
                continue
            if entry.is_dir():
                mtime = max(
                    (f.stat().st_mtime for f in entry.rglob("*") if f.is_file()),
                    default=entry.stat().st_mtime,
                )
                if mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
        if removed:
            log.info("sandbox.cleanup", removed=removed, max_age_days=self.max_age_days)

    def list_all(self) -> list[dict]:
        """List all workspaces with metadata."""
        workspaces = []
        for entry in sorted(self.root.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            files = self.list_files(entry.name)
            total_size = sum(f["size"] for f in files)
            workspaces.append(
                {
                    "task_id": entry.name,
                    "created": entry.stat().st_ctime,
                    "modified": entry.stat().st_mtime,
                    "file_count": len(files),
                    "total_size": total_size,
                }
            )
        return workspaces
