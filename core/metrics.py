"""NCore Genesis — Prometheus metrics v3.1

Audit fix M3: Added ROUTING_LATENCY, CACHE_HITS, CACHE_MISSES,
and increment_metric_safe — required by moe_router.py.
"""
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

# M3: Added for moe_router.py integration
ROUTING_LATENCY = Histogram(
    "ncore_routing_latency_seconds",
    "Time to make routing decision",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25]
)

CACHE_HITS = Counter(
    "ncore_cache_hits_total",
    "Semantic/RadixAttention cache hit count"
)

CACHE_MISSES = Counter(
    "ncore_cache_misses_total",
    "Cache miss count"
)


def update_cost(tier: str, cost: float):
    """Increment cost counter for a given tier."""
    COST_COUNTER.labels(tier=tier).inc(cost)


def increment_metric_safe(metric):
    """Safe metric increment — swallows errors so monitoring never kills a request."""
    try:
        metric.inc()
    except Exception:
        pass
