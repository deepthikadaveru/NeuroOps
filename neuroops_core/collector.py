"""
Collector
Pulls metrics from Prometheus / direct API for the active project.
In self-demo mode it reads the Gauges published by services/api/app.py.
"""

import requests
from datetime import datetime
from ingestion.registry import get_active_project, get_active_services

PROMETHEUS_URL = "http://prometheus:9090"
API_DIRECT_URL = "http://api:5001"   # fallback when Prometheus isn't scraped yet


def query(metric: str) -> float:
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric},
            timeout=5,
        )
        data    = response.json()
        results = data["data"]["result"]
        if not results:
            return 0.0
        return float(results[0]["value"][1])
    except Exception as e:
        print(f"[collector] failed to fetch {metric}: {e}")
        return 0.0


def query_range(metric: str, minutes: int = 5) -> list:
    try:
        end   = datetime.utcnow()
        start = end.timestamp() - (minutes * 60)
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={"query": metric, "start": start,
                    "end": end.timestamp(), "step": "15s"},
            timeout=5,
        )
        data    = response.json()
        results = data["data"]["result"]
        if not results:
            return []
        return [(float(ts), float(val)) for ts, val in results[0]["values"]]
    except Exception as e:
        print(f"[collector] range query failed for {metric}: {e}")
        return []


def _direct_health() -> dict:
    """Read metrics directly from the API service health endpoint."""
    try:
        r = requests.get(f"{API_DIRECT_URL}/health", timeout=3)
        return r.json()
    except Exception:
        return {}


def collect_snapshot() -> dict:
    """
    Collect a full metrics snapshot.
    Priority: Prometheus gauges > direct /health fallback > zeros.
    All seven IsolationForest feature keys are populated with
    scenario-distinct values so the model can tell them apart.
    """
    project  = get_active_project()
    services = get_active_services()

    # ── Try Prometheus first ──────────────────────────────────────────────────
    cpu_raw    = query("api_cpu_usage")
    mem_raw    = query("api_memory_bytes")
    latency    = query("api_latency_seconds")
    error_rate = query("api_error_rate")

    # ── Fallback: read from /health directly ──────────────────────────────────
    if cpu_raw == 0.0 and error_rate == 0.0:
        h          = _direct_health()
        cpu_raw    = h.get("cpu",        cpu_raw)
        latency    = h.get("latency",    latency)
        error_rate = h.get("error_rate", error_rate)

    snapshot = {
        "timestamp":     datetime.utcnow().isoformat(),
        "project_id":    project["id"],
        "project_name":  project["name"],
        "mode":          project.get("mode", "self-demo"),

        # ── Core metric signals (directly from scenario Gauges) ───────────────
        "cpu_usage":     cpu_raw,
        "memory_bytes":  mem_raw if mem_raw > 0 else 200_000_000,
        "web_latency":   latency,
        "api_error_rate": error_rate,

        # ── Derived / legacy fields ───────────────────────────────────────────
        "web_requests":  query("web_requests_total"),
        "api_requests":  query("api_requests_total"),
        "api_errors":    query("api_errors_total"),

        "services": {},
    }

    # Per-service metrics for attached external projects
    for service in services:
        if not service.get("is_infra", False):
            svc = {
                "service_name": service["name"],
                "framework":    service.get("framework", "unknown"),
                "error_rate":   query(
                    f'sum(rate(http_requests_total{{job=~".*{service["name"]}.*",'
                    f'status=~"5.."}}[1m])) / '
                    f'(sum(rate(http_requests_total{{job=~".*{service["name"]}.*"}}[1m])) + 0.001)'
                ),
            }
            snapshot["services"][service["name"]] = svc

            if project.get("mode") == "attached" and snapshot["api_error_rate"] == 0:
                snapshot["api_error_rate"] = svc.get("error_rate", 0)

    return snapshot