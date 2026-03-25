"""NCore Genesis — Prometheus metrics (v3.0)"""
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNTER = Counter(
    "ncore_requests_total",
    "Total requests handled"
)

REQUEST_LATENCY = Histogram(
    "ncore_request_latency_seconds",
    "End-to-end request latency",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

ROUTE_TIER_COUNTER = Counter(
    "ncore_route_tier_total",
    "Requests per routing tier",
    labelnames=["tier"]
)

COST_COUNTER = Counter(
    "ncore_cost_usd_total",
    "Cumulative cost in USD",
    labelnames=["tier"]
)

CACHE_HIT_RATE = Gauge(
    "ncore_cache_hit_rate",
    "SGLang RadixAttention cache hit rate (0-1)"
)

POD_ACTIVE = Gauge(
    "ncore_vast_pods_active",
    "Number of live Vast.ai pods"
)


def update_cost(tier: str, cost: float):
    """Increment cost counter for a given tier."""
    COST_COUNTER.labels(tier=tier).inc(cost)
