PROMETHEUS_URL = "http://prometheus:9090"

METRICS = {
    "web_requests_total": "counter",
    "web_request_latency_seconds_sum": "gauge",
    "api_requests_total": "counter",
    "api_errors_total": "counter",
    "container_cpu_usage_seconds_total": "counter",
    "container_memory_usage_bytes": "gauge",
}

THRESHOLDS = {
    "error_rate": 0.3,        # 30% errors = anomaly
    "cpu_spike": 0.4,         # 40% spike rate = anomaly
    "memory_growth": 0.2,     # 20% growth rate = anomaly
    "latency_spike": 2.0,     # 2x normal latency = anomaly
}

POLL_INTERVAL = 5  # seconds between metric pulls