"""
NCore Genesis vFinal — Prometheus metrics + helpers

All Prometheus objects are defined here so that both moe_router.py and
orchestrator.py import from a single source of truth.

increment_metric_safe() swallows any exception so a metrics failure
never takes down the hot path.

mark_event_loop_thread() tags the current thread so uvloop can be
verified as the active loop implementation at startup.
"""
import threading
import asyncio
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
TASKS_TOTAL = Counter(
    "ncore_tasks_total",
    "Total routed tasks",
    ["model", "role"],
)

CACHE_HITS = Counter(
    "ncore_cache_hits_total",
    "Redis cache hits",
)

CACHE_MISSES = Counter(
    "ncore_cache_misses_total",
    "Redis cache misses",
)

SUMMARISATION_TOTAL = Counter(
    "ncore_summarisation_total",
    "Times the summarisation node was triggered",
)

SUMMARISATION_ERRORS = Counter(
    "ncore_summarisation_errors_total",
    "Summarisation failures",
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------
ROUTING_LATENCY = Histogram(
    "ncore_routing_latency_seconds",
    "End-to-end latency of the MoE routing decision",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------
ACTIVE_REQUESTS = Gauge(
    "ncore_active_requests",
    "In-flight /run requests",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "ncore_circuit_breaker_state",
    "1 = open/tripped, 0 = closed/healthy",
    ["endpoint"],
)

# ---------------------------------------------------------------------------
# Thread-local event-loop marker
# ---------------------------------------------------------------------------
_EVENT_LOOP_THREAD: Optional[int] = None


def mark_event_loop_thread() -> None:
    """Call once from the ASGI startup handler to tag the event-loop thread."""
    global _EVENT_LOOP_THREAD
    _EVENT_LOOP_THREAD = threading.get_ident()
    loop = asyncio.get_event_loop()
    impl = type(loop).__name__
    if "uvloop" not in impl.lower():
        import warnings
        warnings.warn(
            f"[NCore] Expected uvloop event loop, got {impl}. "
            "Check that uvloop.install() ran before uvicorn started."
        )


# ---------------------------------------------------------------------------
# Safe increment helper
# ---------------------------------------------------------------------------
def increment_metric_safe(metric, *label_values) -> None:
    """Increment a Counter (with optional labels) without ever raising."""
    try:
        if label_values:
            metric.labels(*label_values).inc()
        else:
            metric.inc()
    except Exception:
        pass
