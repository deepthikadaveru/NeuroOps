import requests
from datetime import datetime

PROMETHEUS_URL = "http://prometheus:9090"
API_DIRECT_URL = "http://api:5001"


def query(metric: str) -> float:
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric},
            timeout=5,
        )
        results = r.json()["data"]["result"]
        if not results:
            return 0.0
        return float(results[0]["value"][1])
    except Exception as e:
        print(f"[collector] failed: {metric}: {e}")
        return 0.0


def _direct_metrics() -> dict:
    try:
        r = requests.get(f"{API_DIRECT_URL}/metrics_json", timeout=3)
        return r.json()
    except Exception:
        return {}


def collect_snapshot() -> dict:
    # get computed rates from Prometheus
    error_rate = query(
        "rate(api_errors_total[1m]) / (rate(api_requests_total[1m]) + 0.001)"
    )
    request_rate = query("rate(api_requests_total[1m])")
    cpu_rate = query(
        "rate(container_cpu_usage_seconds_total"
        "{name=~'.*api.*'}[1m])"
    )
    memory_bytes = query(
        "container_memory_usage_bytes{name=~'.*api.*'}"
    )

    # fallback: read rich metrics directly from the api service
    direct = _direct_metrics()
    if direct:
        return {
            "timestamp":      datetime.utcnow().isoformat(),
            "cpu_usage":      direct.get("cpu",          cpu_rate),
            "memory_bytes":   direct.get("memory",       memory_bytes or 200_000_000),
            "web_latency":    direct.get("latency",      0.0),
            "api_error_rate": direct.get("error_rate",   error_rate),
            "request_rate":   direct.get("request_rate", request_rate),
            "scenario":       direct.get("scenario",     "normal"),
            "degradation":    direct.get("degradation",  0),
        }

    return {
        "timestamp":      datetime.utcnow().isoformat(),
        "cpu_usage":      cpu_rate,
        "memory_bytes":   memory_bytes or 200_000_000,
        "web_latency":    0.0,
        "api_error_rate": error_rate,
        "request_rate":   request_rate,
        "scenario":       "normal",
        "degradation":    0,
    }