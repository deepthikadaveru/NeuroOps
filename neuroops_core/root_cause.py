CAUSE_MAP = {
    "payment_failure": {
        "human_label": "Payment Gateway Failure",
        "description": "Payment error rate has spiked critically — transactions are being declined",
        "action":      "restart_api",
        "severity":    "critical",
        "impact":      "Most payments are failing — immediate action required",
        "affected":    ["payment-gateway", "api-service"],
    },
    "bad_deployment": {
        "human_label": "Bad Deployment Detected",
        "description": "Error rate surged after a recent change — deployment likely introduced a bug",
        "action":      "rollback",
        "severity":    "critical",
        "impact":      "Service degraded since last deploy — rolling back",
        "affected":    ["api-service", "payment-gateway"],
    },
    "traffic_overload": {
        "human_label": "Traffic Overload",
        "description": "CPU and latency spiking together — system overwhelmed by request volume",
        "action":      "scale_up",
        "severity":    "high",
        "impact":      "Slower transaction processing — scaling up instances",
        "affected":    ["payment-gateway", "web-service", "load-balancer"],
    },
    "cpu_exhaustion": {
        "human_label": "CPU Exhaustion",
        "description": "CPU pegged at near 100% — compute resources fully saturated",
        "action":      "scale_up",
        "severity":    "high",
        "impact":      "System unresponsive under load",
        "affected":    ["api-service"],
    },
    "network_spike": {
        "human_label": "Network Latency Spike",
        "description": "Response times extremely high without CPU or error increase — network issue",
        "action":      "investigate",
        "severity":    "high",
        "impact":      "Users experiencing severe delays",
        "affected":    ["network", "payment-gateway"],
    },
    "db_overload": {
        "human_label": "Database Overload",
        "description": "Latency, errors, and CPU rising together — database is the bottleneck",
        "action":      "scale_up",
        "severity":    "high",
        "impact":      "Slow queries causing payment timeouts",
        "affected":    ["database", "api-service"],
    },
    "slow_gateway": {
        "human_label": "Slow Payment Gateway",
        "description": "Transaction latency is unusually high — gateway processing is degraded",
        "action":      "restart_api",
        "severity":    "high",
        "impact":      "Users waiting too long for payment confirmation",
        "affected":    ["payment-gateway"],
    },
    "memory_leak": {
        "human_label": "Memory Leak Detected",
        "description": "Memory consumption growing abnormally — service will crash if unchecked",
        "action":      "restart_api",
        "severity":    "high",
        "impact":      "Service will become unavailable — preemptive restart needed",
        "affected":    ["api-service"],
    },
    "cascade_failure": {
        "human_label": "Cascade Failure",
        "description": "All metrics critical simultaneously — system-wide failure in progress",
        "action":      "rollback",
        "severity":    "critical",
        "impact":      "Complete payment system outage — emergency response triggered",
        "affected":    ["payment-gateway", "api-service", "database", "web-service"],
    },
    "intermittent_failures": {
        "human_label": "Intermittent Failures",
        "description": "Errors occurring unpredictably — partial service degradation",
        "action":      "restart_api",
        "severity":    "medium",
        "impact":      "Some payments failing randomly — unreliable experience",
        "affected":    ["api-service"],
    },
    "multi_factor_anomaly": {
        "human_label": "Multi-Factor Anomaly",
        "description": "Multiple system metrics deviating simultaneously from baseline",
        "action":      "investigate",
        "severity":    "high",
        "impact":      "Complex system instability — investigating root cause",
        "affected":    ["system"],
    },
    "generic_anomaly": {
        "human_label": "System Anomaly",
        "description": "Unusual system behaviour detected — does not match known patterns",
        "action":      "investigate",
        "severity":    "medium",
        "impact":      "System behaving abnormally — monitoring closely",
        "affected":    ["system"],
    },
    "predicted_risk": {
        "human_label": "Failure Risk Rising",
        "description": "Metrics trending toward failure — pre-emptive action recommended",
        "action":      "scale_up",
        "severity":    "medium",
        "impact":      "No failure yet — acting before users are affected",
        "affected":    ["system"],
    },
}


def analyze(features: dict, anomaly_result: dict) -> dict:
    if not anomaly_result.get("is_anomaly"):
        # check for predicted risk even when not anomaly
        if anomaly_result.get("type") == "predicted_risk":
            cause = CAUSE_MAP["predicted_risk"]
            return {
                "root_cause":     "predicted_risk",
                "human_label":    cause["human_label"],
                "action":         cause["action"],
                "description":    cause["description"],
                "severity":       cause["severity"],
                "impact":         cause["impact"],
                "affected_services": cause["affected"],
                "confidence":     anomaly_result.get("confidence"),
            }
        return {
            "root_cause":        None,
            "human_label":       None,
            "action":            None,
            "description":       "All systems operating normally",
            "severity":          "none",
            "impact":            None,
            "affected_services": [],
        }

    anomaly_type = anomaly_result.get("type", "generic_anomaly")
    cause = CAUSE_MAP.get(anomaly_type, CAUSE_MAP["generic_anomaly"])

    return {
        "root_cause":        anomaly_type,
        "human_label":       cause["human_label"],
        "action":            cause["action"],
        "description":       cause["description"],
        "severity":          cause["severity"],
        "impact":            cause["impact"],
        "affected_services": cause["affected"],
        "confidence":        anomaly_result.get("confidence"),
    }