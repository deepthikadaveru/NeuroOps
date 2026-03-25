"""
NovaPay API Service
10 distinct demo scenarios with unique metric signatures so the
IsolationForest model can actually tell them apart.
"""

from flask import Flask, jsonify
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask_cors import CORS
import random
import time
import threading

app = Flask(__name__)
CORS(app)

# ── State ────────────────────────────────────────────────────────────────────
current_scenario = "normal"
scenario_start   = 0.0   # epoch time when scenario was triggered

# Prometheus metrics
REQUEST_COUNT  = Counter('api_requests_total',  'Total API requests')
ERROR_COUNT    = Counter('api_errors_total',     'Total API errors')
CPU_GAUGE      = Gauge('api_cpu_usage',          'Simulated CPU usage 0-1')
MEMORY_GAUGE   = Gauge('api_memory_bytes',       'Simulated memory bytes')
LATENCY_GAUGE  = Gauge('api_latency_seconds',    'Simulated response latency')
ERROR_RATE_G   = Gauge('api_error_rate',         'Simulated error rate 0-1')

# ── Scenario definitions ──────────────────────────────────────────────────────
# Each scenario returns a dict of metric overrides.
# Metrics NOT listed fall back to normal ranges.
# "elapsed" is seconds since scenario triggered (passed in at call time).

def _normal():
    return dict(
        cpu         = random.uniform(0.10, 0.25),
        memory      = random.uniform(180_000_000, 220_000_000),
        latency     = random.uniform(0.04, 0.10),
        error_rate  = random.uniform(0.00, 0.02),
        http_status = 200,
    )

SCENARIOS = {
    # 1. Payment gateway failure — high errors, LOW cpu (gateway issue not compute)
    "payment_failure": lambda elapsed: dict(
        cpu         = random.uniform(0.10, 0.18),
        memory      = random.uniform(190_000_000, 210_000_000),
        latency     = random.uniform(0.08, 0.15),
        error_rate  = random.uniform(0.75, 0.95),
        http_status = 500,
    ),

    # 2. Traffic overload — HIGH cpu + HIGH latency together
    "traffic_overload": lambda elapsed: dict(
        cpu         = random.uniform(0.80, 0.95),
        memory      = random.uniform(300_000_000, 380_000_000),
        latency     = random.uniform(1.20, 2.50),
        error_rate  = random.uniform(0.15, 0.30),
        http_status = 200 if random.random() > 0.2 else 503,
    ),

    # 3. Memory leak — memory grows linearly over time, cpu/latency normal
    "memory_leak": lambda elapsed: dict(
        cpu         = random.uniform(0.20, 0.30),
        memory      = 200_000_000 + elapsed * 8_000_000 + random.uniform(-5e6, 5e6),
        latency     = random.uniform(0.05, 0.12),
        error_rate  = random.uniform(0.00, 0.04),
        http_status = 200,
    ),

    # 4. Bad deployment — sudden error spike after normal, cpu stays normal
    "bad_deployment": lambda elapsed: dict(
        cpu         = random.uniform(0.15, 0.25),
        memory      = random.uniform(185_000_000, 215_000_000),
        latency     = random.uniform(0.10, 0.20),
        error_rate  = random.uniform(0.55, 0.80),
        http_status = 500 if random.random() > 0.3 else 200,
    ),

    # 5. Database slowdown — latency high, errors moderate, cpu LOW
    "db_slowdown": lambda elapsed: dict(
        cpu         = random.uniform(0.08, 0.18),
        memory      = random.uniform(190_000_000, 220_000_000),
        latency     = random.uniform(2.00, 4.50),
        error_rate  = random.uniform(0.20, 0.45),
        http_status = 200 if random.random() > 0.35 else 504,
    ),

    # 6. Cascade failure — EVERYTHING high simultaneously
    "cascade_failure": lambda elapsed: dict(
        cpu         = random.uniform(0.85, 1.00),
        memory      = random.uniform(450_000_000, 600_000_000),
        latency     = random.uniform(3.00, 6.00),
        error_rate  = random.uniform(0.70, 0.95),
        http_status = 500,
    ),

    # 7. Network latency spike — latency very high, errors LOW, cpu normal
    "network_latency": lambda elapsed: dict(
        cpu         = random.uniform(0.12, 0.22),
        memory      = random.uniform(185_000_000, 215_000_000),
        latency     = random.uniform(3.00, 7.00),
        error_rate  = random.uniform(0.00, 0.05),
        http_status = 200,
    ),

    # 8. Service recovery — metrics improving back toward normal over time
    "recovery": lambda elapsed: dict(
        cpu         = max(0.12, 0.85 - elapsed * 0.05 + random.uniform(-0.05, 0.05)),
        memory      = max(200_000_000, 500_000_000 - elapsed * 15_000_000),
        latency     = max(0.06, 3.00 - elapsed * 0.15 + random.uniform(-0.1, 0.1)),
        error_rate  = max(0.00, 0.80 - elapsed * 0.05 + random.uniform(-0.02, 0.02)),
        http_status = 200 if elapsed > 8 else 503,
    ),

    # 9. Predicted failure — risk rising slowly (cpu + memory trending up together)
    "predicted_failure": lambda elapsed: dict(
        cpu         = min(0.90, 0.30 + elapsed * 0.04 + random.uniform(-0.02, 0.02)),
        memory      = min(600_000_000, 220_000_000 + elapsed * 5_000_000),
        latency     = min(2.0, 0.08 + elapsed * 0.03),
        error_rate  = min(0.40, 0.02 + elapsed * 0.015),
        http_status = 200,
    ),

    # 10. Resource exhaustion — cpu sustained very high, latency growing, errors low
    "resource_exhaustion": lambda elapsed: dict(
        cpu         = random.uniform(0.90, 0.99),
        memory      = random.uniform(380_000_000, 480_000_000),
        latency     = random.uniform(0.80, 1.60),
        error_rate  = random.uniform(0.03, 0.10),
        http_status = 200 if random.random() > 0.1 else 503,
    ),
}

SCENARIO_RECOVERY_DELAY = {
    "payment_failure":    12,
    "traffic_overload":   15,
    "memory_leak":        20,
    "bad_deployment":     14,
    "db_slowdown":        16,
    "cascade_failure":    10,
    "network_latency":    14,
    "recovery":           18,
    "predicted_failure":  25,
    "resource_exhaustion": 18,
}


def _get_metrics():
    """Return current metric values based on active scenario."""
    global current_scenario, scenario_start
    elapsed = time.time() - scenario_start

    if current_scenario == "normal" or current_scenario not in SCENARIOS:
        return _normal()

    return SCENARIOS[current_scenario](elapsed)


def _update_prometheus(m: dict):
    CPU_GAUGE.set(m["cpu"])
    MEMORY_GAUGE.set(m["memory"])
    LATENCY_GAUGE.set(m["latency"])
    ERROR_RATE_G.set(m["error_rate"])


# ── Background metric emitter (keeps Prometheus fresh) ───────────────────────
def _metric_emitter():
    while True:
        m = _get_metrics()
        _update_prometheus(m)
        time.sleep(2)

threading.Thread(target=_metric_emitter, daemon=True).start()


# ── Auto recovery ─────────────────────────────────────────────────────────────
def _auto_recover(delay: int):
    global current_scenario
    time.sleep(delay)
    current_scenario = "normal"
    print(f"[demo] auto-recovered after {delay}s")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/data")
def data():
    global current_scenario
    REQUEST_COUNT.inc()
    m = _get_metrics()
    _update_prometheus(m)

    if m["error_rate"] > 0.5:
        ERROR_COUNT.inc()

    if m["http_status"] != 200:
        return jsonify({
            "error": "service degraded",
            "scenario": current_scenario,
            "error_rate": round(m["error_rate"], 3),
        }), m["http_status"]

    # Simulate latency
    time.sleep(min(m["latency"], 2.0))

    return jsonify({
        "service":    "api",
        "data":       [random.randint(1, 100) for _ in range(5)],
        "scenario":   current_scenario,
        "error_rate": round(m["error_rate"], 3),
        "latency":    round(m["latency"], 3),
    })


@app.route("/fix")
def fix_service():
    global current_scenario
    current_scenario = "normal"
    return jsonify({"status": "recovered", "scenario": "normal"})


@app.route("/health")
def health():
    m = _get_metrics()
    is_healthy = m["error_rate"] < 0.3 and m["latency"] < 1.5
    return jsonify({
        "status":    "healthy" if is_healthy else "degraded",
        "scenario":  current_scenario,
        "error_rate": round(m["error_rate"], 3),
        "latency":   round(m["latency"], 3),
        "cpu":       round(m["cpu"], 3),
    })


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/demo/<scenario>")
def demo(scenario):
    global current_scenario, scenario_start

    if scenario not in SCENARIOS:
        return jsonify({
            "status": "unknown scenario",
            "available": list(SCENARIOS.keys()),
        }), 400

    current_scenario = scenario
    scenario_start   = time.time()

    delay = SCENARIO_RECOVERY_DELAY.get(scenario, 15)
    threading.Thread(target=_auto_recover, args=(delay,), daemon=True).start()

    print(f"[demo] triggered: {scenario} | auto-recover in {delay}s")
    return jsonify({
        "status":   "scenario triggered",
        "scenario": scenario,
        "description": _scenario_description(scenario),
        "auto_recover_in": delay,
    })


@app.route("/demo/list")
def demo_list():
    return jsonify({"scenarios": list(SCENARIOS.keys())})


def _scenario_description(s: str) -> str:
    return {
        "payment_failure":    "High error rate, low CPU — gateway issue",
        "traffic_overload":   "CPU spike + latency spike together",
        "memory_leak":        "Memory growing linearly over time",
        "bad_deployment":     "Sudden error spike after stable period",
        "db_slowdown":        "High latency, moderate errors, low CPU",
        "cascade_failure":    "Everything degrading simultaneously",
        "network_latency":    "Extreme latency, low errors, normal CPU",
        "recovery":           "Metrics returning to normal after incident",
        "predicted_failure":  "CPU + memory slowly rising toward failure",
        "resource_exhaustion":"CPU sustained >90%, latency creeping up",
    }.get(s, "Unknown scenario")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)