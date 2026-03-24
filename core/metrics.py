"""
NCore Genesis vFinal — Singularity Prometheus Metrics

Fix applied vs. submitted code:
  call_soon() used when already on the event loop thread;
  call_soon_threadsafe() reserved for cross-thread callers only.
  mark_event_loop_thread() must be called once from the ASGI startup event.
"""
import asyncio
import threading

from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)

# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
TASKS_TOTAL = Counter(
    "ncore_tasks_total",
    "Total tasks received by the orchestrator",
    ["model", "role"],
)

ROUTING_LATENCY = Histogram(
    "ncore_routing_latency_seconds",
    "Time spent in the INT8 vector search path",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

SUMMARISATION_TOTAL = Counter(
    "ncore_summarisation_total",
    "Number of times the sliding-window summariser fired",
)

SUMMARISATION_ERRORS = Counter(
    "ncore_summarisation_errors_total",
    "Number of times summarisation fell back to hard truncation",
)

CACHE_HITS = Counter(
    "ncore_cache_hits_total",
    "Semantic cache hits (task hash matched Redis)",
)

CACHE_MISSES = Counter(
    "ncore_cache_misses_total",
    "Semantic cache misses (full routing required)",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "ncore_circuit_breaker_open",
    "1 if downstream endpoint circuit breaker is open, 0 otherwise",
    ["endpoint"],
)

ACTIVE_REQUESTS = Gauge(
    "ncore_active_requests",
    "Number of /run requests currently in-flight",
)

# ---------------------------------------------------------------------------
# Event-loop thread registration
# ---------------------------------------------------------------------------
_EVENT_LOOP_THREAD_ID: int = 0


def mark_event_loop_thread() -> None:
    """
    Record the OS thread ID of the uvloop worker.
    Call exactly once from the FastAPI startup event.
    """
    global _EVENT_LOOP_THREAD_ID
    _EVENT_LOOP_THREAD_ID = threading.get_ident()


# ---------------------------------------------------------------------------
# Asynchronous Metric Injection
# ---------------------------------------------------------------------------
def increment_metric_safe(metric, *label_args) -> None:
    """
    Fire-and-forget metric increment that never blocks the ASGI event loop.

    Strategy:
      - From within the event-loop thread  -> loop.call_soon()          (zero overhead)
      - From a background/worker thread    -> loop.call_soon_threadsafe() (thread-safe wakeup)
      - No running loop (startup / tests)  -> direct synchronous .inc()
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop active — safe to increment synchronously
        if label_args:
            metric.labels(*label_args).inc()
        else:
            metric.inc()
        return

    def _do_inc() -> None:
        if label_args:
            metric.labels(*label_args).inc()
        else:
            metric.inc()

    if threading.get_ident() == _EVENT_LOOP_THREAD_ID:
        loop.call_soon(_do_inc)
    else:
        loop.call_soon_threadsafe(_do_inc)
