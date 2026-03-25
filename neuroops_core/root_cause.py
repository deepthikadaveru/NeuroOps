"""
Root Cause Analysis Engine
Model-driven: uses anomaly_detector type output first, rules as last resort.
Covers all 10 demo scenarios with human-readable labels and actions.
"""

DEPENDENCY_GRAPH = {
    "payment_failure_spike": ["payment-gateway", "api-service"],
    "traffic_overload":      ["payment-gateway", "web-service", "load-balancer"],
    "memory_leak":           ["api-service"],
    "bad_deployment":        ["payment-gateway", "api-service"],
    "db_slowdown":           ["payment-gateway", "database"],
    "cascade_failure":       ["payment-gateway", "api-service", "web-service", "database"],
    "network_latency_spike": ["network", "load-balancer"],
    "service_recovery":      ["system"],
    "predicted_risk":        ["system"],
    "resource_exhaustion":   ["api-service", "compute"],
    "intermittent_failures": ["api-service"],
    "multi_factor_anomaly":  ["payment-gateway", "api-service", "web-service"],
    "generic_anomaly":       ["system"],
}

MODEL_CAUSE_MAP = {
    "payment_failure_spike": {
        "action":      "restart_api",
        "severity":    "critical",
        "description": "Payment gateway returning errors on most requests — not a CPU issue, likely a gateway or upstream fault",
        "impact":      "Majority of payment transactions are failing",
    },
    "traffic_overload": {
        "action":      "scale_up",
        "severity":    "high",
        "description": "CPU spiked sharply alongside rising latency — traffic volume is exceeding capacity",
        "impact":      "Payments processing slowly, some requests timing out",
    },
    "memory_leak": {
        "action":      "restart_api",
        "severity":    "high",
        "description": "Memory usage growing continuously without release — classic leak pattern",
        "impact":      "Service will crash if not restarted soon",
    },
    "bad_deployment": {
        "action":      "rollback",
        "severity":    "critical",
        "description": "Error rate spiked suddenly after a stable period — consistent with a bad code deployment",
        "impact":      "Large portion of payments failing since deploy",
    },
    "db_slowdown": {
        "action":      "investigate",
        "severity":    "high",
        "description": "Latency very high but CPU is low — bottleneck is downstream, likely the database",
        "impact":      "Transactions completing but very slowly",
    },
    "cascade_failure": {
        "action":      "rollback",
        "severity":    "critical",
        "description": "CPU, errors, and latency all elevated simultaneously — multiple services failing together",
        "impact":      "System-wide outage affecting all payment flows",
    },
    "network_latency_spike": {
        "action":      "investigate",
        "severity":    "high",
        "description": "Extreme latency with low errors and normal CPU — network or load-balancer issue",
        "impact":      "Payments hanging but not outright failing",
    },
    "service_recovery": {
        "action":      "alert",
        "severity":    "low",
        "description": "Metrics are trending back toward normal — system is recovering from a previous incident",
        "impact":      "Payment success rate improving, no action needed",
    },
    "predicted_risk": {
        "action":      "scale_up",
        "severity":    "medium",
        "description": "Model detects rising CPU and memory trend — failure predicted if trajectory continues",
        "impact":      "Preventive scaling recommended before impact reaches users",
    },
    "resource_exhaustion": {
        "action":      "scale_up",
        "severity":    "high",
        "description": "CPU sustained above 90% — compute resources fully saturated",
        "impact":      "Latency will increase and errors will follow without more capacity",
    },
    "intermittent_failures": {
        "action":      "restart_api",
        "severity":    "medium",
        "description": "Errors occurring inconsistently without a clear trigger",
        "impact":      "Unreliable payment experience for some users",
    },
    "multi_factor_anomaly": {
        "action":      "rollback",
        "severity":    "critical",
        "description": "Multiple independent anomaly signals detected at once",
        "impact":      "System-wide instability",
    },
    "generic_anomaly": {
        "action":      "restart_api",
        "severity":    "medium",
        "description": "Model flagged unusual system behaviour — no known pattern matched",
        "impact":      "System behaving abnormally",
    },
}

# Fallback rules (only used when model type is unknown/missing)
CAUSE_RULES = [
    {
        "name":        "bad_deployment",
        "condition":   lambda f: f.get("error_acceleration", 0) > 0.15 and f.get("raw_error_rate", 0) > 0.40,
        "description": "Sudden error surge consistent with a bad deployment",
        "action":      "rollback",
        "severity":    "critical",
        "impact":      "Payments failing rapidly",
    },
    {
        "name":        "traffic_overload",
        "condition":   lambda f: f.get("cpu_spike_rate", 0) > 0.20 and f.get("raw_latency", 0) > 0.80,
        "description": "Traffic overload — CPU spike with latency rise",
        "action":      "scale_up",
        "severity":    "high",
        "impact":      "System slowdown",
    },
    {
        "name":        "memory_leak",
        "condition":   lambda f: f.get("memory_growth_rate", 0) > 2_000_000,
        "description": "Memory growing continuously",
        "action":      "restart_api",
        "severity":    "high",
        "impact":      "Service instability risk",
    },
]


def analyze(features: dict, anomaly_result: dict) -> dict:

    if not anomaly_result.get("is_anomaly"):
        # Still show predicted_risk if type is set
        atype = anomaly_result.get("type", "normal")
        if atype == "predicted_risk":
            cause = MODEL_CAUSE_MAP["predicted_risk"]
            return {
                "root_cause":       "predicted_risk",
                "human_label":      "Predicted Risk",
                "action":           cause["action"],
                "description":      cause["description"],
                "severity":         cause["severity"],
                "impact":           cause["impact"],
                "confidence":       anomaly_result.get("confidence"),
                "affected_services": DEPENDENCY_GRAPH.get("predicted_risk", []),
            }
        return {
            "root_cause":       None,
            "action":           None,
            "description":      "All systems operating normally",
            "severity":         "none",
            "impact":           None,
            "affected_services": [],
        }

    anomaly_type = anomaly_result.get("type", "unknown")

    # ── Model-driven path ──────────────────────────────────────────────────────
    if anomaly_type in MODEL_CAUSE_MAP:
        cause = MODEL_CAUSE_MAP[anomaly_type]
        return {
            "root_cause":       anomaly_type,
            "human_label":      _human_label(anomaly_type),
            "action":           cause["action"],
            "description":      cause["description"],
            "severity":         cause["severity"],
            "impact":           cause["impact"],
            "confidence":       anomaly_result.get("confidence"),
            "affected_services": DEPENDENCY_GRAPH.get(anomaly_type, []),
        }

    # ── Rule fallback ──────────────────────────────────────────────────────────
    for rule in CAUSE_RULES:
        if rule["condition"](features):
            return {
                "root_cause":       rule["name"],
                "human_label":      _human_label(rule["name"]),
                "action":           rule["action"],
                "description":      rule["description"],
                "severity":         rule["severity"],
                "impact":           rule["impact"],
                "affected_services": DEPENDENCY_GRAPH.get(rule["name"], []),
            }

    # ── Final fallback ─────────────────────────────────────────────────────────
    return {
        "root_cause":       "unknown",
        "human_label":      "Unknown Anomaly",
        "action":           "alert",
        "description":      "Model detected an anomaly but no known pattern matched",
        "severity":         "medium",
        "impact":           "System behaving unexpectedly",
        "affected_services": [],
    }


_LABELS = {
    "payment_failure_spike": "Payment Gateway Failure",
    "traffic_overload":      "Traffic Overload",
    "memory_leak":           "Memory Leak",
    "bad_deployment":        "Bad Deployment",
    "db_slowdown":           "Database Slowdown",
    "cascade_failure":       "Cascade Failure",
    "network_latency_spike": "Network Latency Spike",
    "service_recovery":      "Service Recovery",
    "predicted_risk":        "Predicted Failure Risk",
    "resource_exhaustion":   "Resource Exhaustion",
    "intermittent_failures": "Intermittent Failures",
    "multi_factor_anomaly":  "Multi-Factor Anomaly",
    "generic_anomaly":       "Anomaly Detected",
}

def _human_label(t: str) -> str:
    return _LABELS.get(t, t.replace("_", " ").title())