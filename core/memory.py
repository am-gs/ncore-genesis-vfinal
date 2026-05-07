"""NLLM.ING Persistent Memory Layer — Cross-Session Context & Learning v1.0

Manus.im pattern: persistent memory that accumulates across sessions,
tracks domain-specific performance, and suggests improvements.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

DB_PATH = Path(os.environ.get("NLLM_MEMORY_DB", "/tmp/nllm-workspace/memory.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class MemoryStore:
    """SQLite-backed persistent memory for NLLM.ING.

    Tables:
    - sessions: task sessions with metadata
    - task_patterns: recurring task types and their success rates
    - domain_stats: per-domain performance (cost, latency, success rate)
    - user_prefs: user preferences (format, verbosity, tone)
    - routing_history: which routes succeeded for which task types
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    task_id TEXT PRIMARY KEY,
                    task_description TEXT,
                    status TEXT,
                    created REAL,
                    completed REAL,
                    total_cost REAL DEFAULT 0,
                    total_latency REAL DEFAULT 0,
                    model_used TEXT,
                    execution_mode TEXT,
                    success INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS task_patterns (
                    pattern_hash TEXT PRIMARY KEY,
                    domain TEXT,
                    pattern TEXT,
                    count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    avg_cost REAL DEFAULT 0,
                    avg_latency REAL DEFAULT 0,
                    best_model TEXT,
                    best_mode TEXT,
                    last_used REAL
                );

                CREATE TABLE IF NOT EXISTS domain_stats (
                    domain TEXT PRIMARY KEY,
                    total_tasks INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    total_cost REAL DEFAULT 0,
                    total_latency REAL DEFAULT 0,
                    avg_cost REAL DEFAULT 0,
                    avg_latency REAL DEFAULT 0,
                    success_rate REAL DEFAULT 0,
                    last_updated REAL
                );

                CREATE TABLE IF NOT EXISTS user_prefs (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated REAL
                );

                CREATE TABLE IF NOT EXISTS routing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_pattern TEXT,
                    model TEXT,
                    mode TEXT,
                    success INTEGER,
                    cost REAL,
                    latency REAL,
                    timestamp REAL
                );
                """
            )

    # ── Session tracking ────────────────────────────────────────────────────────

    def save_session(
        self,
        task_id: str,
        task: str,
        status: str,
        cost: float = 0,
        latency: float = 0,
        model: str = "",
        mode: str = "llm",
        success: bool = False,
    ):
        now = time.time()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (task_id, task_description, status, created, completed, total_cost, total_latency, model_used, execution_mode, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task[:500],
                    status,
                    now,
                    now if status in ("completed", "failed") else 0,
                    cost,
                    latency,
                    model,
                    mode,
                    1 if success else 0,
                ),
            )
        log.info("memory.session_saved", task_id=task_id, status=status, cost=cost)

    def get_session(self, task_id: str) -> dict | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_sessions(self, limit: int = 50) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Pattern learning ──────────────────────────────────────────────────────

    def record_pattern(
        self,
        domain: str,
        pattern: str,
        success: bool,
        cost: float,
        latency: float,
        model: str,
        mode: str,
    ):
        """Learn from a task execution to improve future routing."""
        pattern_hash = f"{domain}:{hash(pattern) % 10000000}"
        now = time.time()

        with sqlite3.connect(str(self.db_path)) as conn:
            existing = conn.execute(
                "SELECT * FROM task_patterns WHERE pattern_hash = ?",
                (pattern_hash,),
            ).fetchone()

            if existing:
                # Update averages incrementally
                old_count = existing[3]
                old_success = existing[4]
                old_cost = existing[5]
                old_latency = existing[6]

                new_count = old_count + 1
                new_success = old_success + (1 if success else 0)
                new_avg_cost = (old_cost * old_count + cost) / new_count
                new_avg_latency = (old_latency * old_count + latency) / new_count

                conn.execute(
                    """
                    UPDATE task_patterns SET
                    count = ?, success_count = ?, avg_cost = ?, avg_latency = ?,
                    last_used = ?
                    WHERE pattern_hash = ?
                    """,
                    (
                        new_count,
                        new_success,
                        new_avg_cost,
                        new_avg_latency,
                        now,
                        pattern_hash,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO task_patterns
                    (pattern_hash, domain, pattern, count, success_count, avg_cost, avg_latency, best_model, best_mode, last_used)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pattern_hash,
                        domain,
                        pattern[:500],
                        1 if success else 0,
                        cost,
                        latency,
                        model,
                        mode,
                        now,
                    ),
                )

            # Update domain stats
            self._update_domain_stats(conn, domain, success, cost, latency)

            # Record routing history
            conn.execute(
                """
                INSERT INTO routing_history
                (task_pattern, model, mode, success, cost, latency, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (pattern[:200], model, mode, 1 if success else 0, cost, latency, now),
            )

        log.info(
            "memory.pattern_recorded",
            domain=domain,
            success=success,
            model=model,
            mode=mode,
        )

    def suggest_route(self, domain: str, pattern: str) -> dict:
        """Suggest the best model/mode for a given domain/pattern."""
        pattern_hash = f"{domain}:{hash(pattern) % 10000000}"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row

            # Exact pattern match
            exact = conn.execute(
                "SELECT * FROM task_patterns WHERE pattern_hash = ?",
                (pattern_hash,),
            ).fetchone()

            if exact and exact["count"] >= 3:
                return {
                    "confidence": "high",
                    "model": exact["best_model"],
                    "mode": exact["best_mode"],
                    "avg_cost": exact["avg_cost"],
                    "avg_latency": exact["avg_latency"],
                    "success_rate": exact["success_count"] / exact["count"],
                }

            # Domain-level fallback
            domain_row = conn.execute(
                "SELECT * FROM domain_stats WHERE domain = ?", (domain,)
            ).fetchone()

            if domain_row and domain_row["total_tasks"] >= 3:
                # Find best model for this domain from routing history
                best = conn.execute(
                    """
                    SELECT model, mode, AVG(success) as sr, AVG(cost) as ac, AVG(latency) as al
                    FROM routing_history
                    WHERE task_pattern LIKE ?
                    GROUP BY model, mode
                    HAVING COUNT(*) >= 2
                    ORDER BY sr DESC, ac ASC
                    LIMIT 1
                    """,
                    (f"%{domain}%",),
                ).fetchone()

                if best:
                    return {
                        "confidence": "medium",
                        "model": best["model"],
                        "mode": best["mode"],
                        "avg_cost": best["ac"],
                        "avg_latency": best["al"],
                        "success_rate": best["sr"],
                    }

        return {"confidence": "low", "model": None, "mode": None}

    def _update_domain_stats(
        self,
        conn: sqlite3.Connection,
        domain: str,
        success: bool,
        cost: float,
        latency: float,
    ):
        existing = conn.execute(
            "SELECT * FROM domain_stats WHERE domain = ?", (domain,)
        ).fetchone()

        now = time.time()
        if existing:
            old_total = existing[1]
            old_success = existing[2]
            old_cost = existing[3]
            old_latency = existing[4]

            new_total = old_total + 1
            new_success = old_success + (1 if success else 0)
            new_cost = old_cost + cost
            new_latency = old_latency + latency

            conn.execute(
                """
                UPDATE domain_stats SET
                total_tasks = ?, success_count = ?, total_cost = ?, total_latency = ?,
                avg_cost = ?, avg_latency = ?, success_rate = ?, last_updated = ?
                WHERE domain = ?
                """,
                (
                    new_total,
                    new_success,
                    new_cost,
                    new_latency,
                    new_cost / new_total,
                    new_latency / new_total,
                    new_success / new_total,
                    now,
                    domain,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO domain_stats
                (domain, total_tasks, success_count, total_cost, total_latency, avg_cost, avg_latency, success_rate, last_updated)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (domain, 1 if success else 0, cost, latency, cost, latency, 1.0 if success else 0.0, now),
            )

    # ── User preferences ────────────────────────────────────────────────────────

    def set_pref(self, key: str, value: Any):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_prefs (key, value, updated) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time()),
            )

    def get_pref(self, key: str, default: Any = None) -> Any:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM user_prefs WHERE key = ?", (key,)
            ).fetchone()
            return json.loads(row[0]) if row else default

    def get_all_prefs(self) -> dict[str, Any]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT key, value FROM user_prefs").fetchall()
            return {k: json.loads(v) for k, v in rows}

    # ── Context building ──────────────────────────────────────────────────────

    def build_context(self, task_id: str, task: str) -> dict:
        """Build rich context for a model prompt from memory."""
        # Extract domain heuristic
        domain = self._guess_domain(task)

        # Get similar past tasks
        similar = self._find_similar(domain, task)

        # Get user preferences
        prefs = self.get_all_prefs()

        # Get routing suggestion
        route_suggestion = self.suggest_route(domain, task)

        # Get system stats
        stats = self._get_system_stats()

        return {
            "task_id": task_id,
            "domain": domain,
            "similar_tasks": similar,
            "user_prefs": prefs,
            "suggested_route": route_suggestion,
            "system_stats": stats,
        }

    def _guess_domain(self, task: str) -> str:
        t = task.lower()
        if any(k in t for k in ["image", "picture", "photo", "draw", "flux", "sdxl"]):
            return "image_generation"
        if any(k in t for k in ["video", "animate", "wan", "motion"]):
            return "video_generation"
        if any(k in t for k in ["code", "script", "function", "debug", "program"]):
            return "coding"
        if any(k in t for k in ["search", "research", "find", "investigate", "osint"]):
            return "research"
        if any(k in t for k in ["write", "essay", "blog", "article", "content"]):
            return "writing"
        if any(k in t for k in ["data", "analyze", "chart", "csv", "excel"]):
            return "data_analysis"
        return "general"

    def _find_similar(self, domain: str, task: str, limit: int = 3) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE task_description LIKE ? AND success = 1
                ORDER BY created DESC
                LIMIT ?
                """,
                (f"%{domain}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def _get_system_stats(self) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*), SUM(success), AVG(total_cost), AVG(total_latency) FROM sessions"
            ).fetchone()
            return {
                "total_tasks": total[0] or 0,
                "total_successes": total[1] or 0,
                "avg_cost": total[2] or 0,
                "avg_latency": total[3] or 0,
            }
