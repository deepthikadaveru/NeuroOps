"""
Processor
Converts raw metric snapshots into feature vectors for the anomaly detector.
raw_memory is now passed through so the anomaly classifier can use it.
"""

import numpy as np
from collections import deque

# Rolling window: last 60 snapshots (~5 min at 5 s intervals)
history = deque(maxlen=60)


def add_snapshot(snapshot: dict):
    history.append(snapshot)


def compute_features(snapshot: dict) -> dict:
    features = {}

    features["timestamp"]      = snapshot["timestamp"]
    features["raw_error_rate"] = snapshot.get("api_error_rate", 0.0)
    features["raw_cpu"]        = snapshot.get("cpu_usage", 0.0)
    features["raw_memory"]     = snapshot.get("memory_bytes", 0.0)
    features["raw_latency"]    = snapshot.get("web_latency", 0.0)

    if len(history) >= 2:
        prev = history[-2]

        # CPU spike rate: how fast CPU is rising
        cpu_delta = snapshot["cpu_usage"] - prev.get("cpu_usage", 0)
        features["cpu_spike_rate"] = max(0.0, cpu_delta)

        # Error acceleration: is error rate growing (can be negative = improving)
        err_delta = snapshot["api_error_rate"] - prev.get("api_error_rate", 0)
        features["error_acceleration"] = err_delta

        # Memory growth rate (bytes per interval — positive = growing)
        mem_delta = snapshot["memory_bytes"] - prev.get("memory_bytes", 0)
        features["memory_growth_rate"] = max(0.0, mem_delta)

        # Latency variation (absolute change)
        lat_delta = snapshot["web_latency"] - prev.get("web_latency", 0)
        features["latency_variation"] = abs(lat_delta)

    else:
        features["cpu_spike_rate"]     = 0.0
        features["error_acceleration"] = 0.0
        features["memory_growth_rate"] = 0.0
        features["latency_variation"]  = 0.0

    # Health score 0-100 (higher = healthier)
    error_score  = max(0.0, 1.0 - (features["raw_error_rate"] * 10))
    cpu_score    = max(0.0, 1.0 - features["raw_cpu"])
    latency_score = max(0.0, 1.0 - (features["raw_latency"] / 5.0))   # 5 s max
    memory_score = max(0.0, 1.0 - (features["raw_memory"] / 600_000_000))

    features["health_score"] = round(
        (error_score  * 0.35 +
         cpu_score    * 0.25 +
         latency_score * 0.25 +
         memory_score * 0.15) * 100,
        2,
    )

    return features


def get_trend(metric_key: str, window: int = 10) -> str:
    if len(history) < window:
        return "stable"
    values = [s.get(metric_key, 0) for s in list(history)[-window:]]
    slope  = np.polyfit(range(len(values)), values, 1)[0]
    if slope > 0.01:
        return "rising"
    elif slope < -0.01:
        return "falling"
    return "stable"