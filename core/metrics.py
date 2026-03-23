"""
NCore Genesis vFinal — Prometheus Metrics
Exposes counters, histograms and gauges for the MoE orchestrator.
Mount /metrics on the FastAPI app to allow Prometheus scraping.
"""
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)
from fastapi import Response

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
    "Time spent in route_node selecting a model",
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
    "1 if any downstream vLLM circuit breaker is open, 0 otherwise",
    ["endpoint"],
)

ACTIVE_REQUESTS = Gauge(
    "ncore_active_requests",
    "Number of /run requests currently in-flight",
)


# ---------------------------------------------------------------------------
# Metrics endpoint handler (mount on FastAPI)
# ---------------------------------------------------------------------------
def metrics_response() -> Response:
    """Return Prometheus text exposition format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
