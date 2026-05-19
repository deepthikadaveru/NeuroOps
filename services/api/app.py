from flask import Flask, jsonify
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from flask_cors import CORS
import random
import time
import threading
import math

app = Flask(__name__)
CORS(app)

# state
degradation_level = 0
current_scenario = "normal"
scenario_start = time.time()

# prometheus counters
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests')
ERROR_COUNT   = Counter('api_errors_total',   'Total API errors')

# rich gauges — these are what Neuro-Ops reads via /metrics_json
g_cpu        = Gauge('api_cpu_usage',       'Simulated CPU usage 0-1')
g_memory     = Gauge('api_memory_bytes',    'Simulated memory bytes')
g_latency    = Gauge('api_latency_seconds', 'Simulated latency seconds')
g_error_rate = Gauge('api_error_rate',      'Current error rate 0-1')
g_req_rate   = Gauge('api_request_rate',    'Requests per second')

BASE_MEMORY = 200_000_000  # 200 MB baseline


# ── Scenario definitions ────────────────────────────────────────────────────
# Each scenario produces a DISTINCT metric signature so the model can tell
# them apart. Values are (cpu, latency, error_rate, memory_multiplier)
SCENARIOS = {
    # name              cpu    latency  errors  mem_mult
    "normal":          (0.15,  0.05,   0.00,   1.0),
    "payment_failure": (0.18,  0.08,   0.95,   1.0),   # errors spike, cpu fine
    "traffic_overload":(0.92,  0.85,   0.15,   1.3),   # cpu + latency spike
    "slow_gateway":    (0.20,  2.40,   0.05,   1.0),   # latency only
    "memory_leak":     (0.25,  0.10,   0.02,   3.5),   # memory only
    "bad_deployment":  (0.22,  0.12,   0.88,   1.1),   # errors + slight cpu
    "db_overload":     (0.45,  1.80,   0.40,   1.2),   # latency + errors + cpu
    "cascade_failure": (0.95,  3.50,   0.99,   2.0),   # everything maxed
    "network_spike":   (0.18,  4.20,   0.10,   1.0),   # latency only, extreme
    "cpu_exhaustion":  (0.98,  0.30,   0.05,   1.1),   # cpu only
    "intermittent":    (0.20,  0.15,   0.45,   1.0),   # medium errors, random
}

# how long each scenario runs before auto-recovery (seconds)
SCENARIO_DURATION = {
    "payment_failure":  25,
    "traffic_overload": 30,
    "slow_gateway":     25,
    "memory_leak":      40,
    "bad_deployment":   25,
    "db_overload":      30,
    "cascade_failure":  20,
    "network_spike":    25,
    "cpu_exhaustion":   30,
    "intermittent":     30,
}


def get_metrics():
    """Return current metric values with scenario-appropriate noise."""
    s = SCENARIOS.get(current_scenario, SCENARIOS["normal"])
    cpu_base, lat_base, err_base, mem_mult = s

    t = time.time() - scenario_start
    noise = math.sin(t * 0.5) * 0.03

    cpu     = max(0.0, min(1.0, cpu_base + noise + random.uniform(-0.02, 0.02)))
    latency = max(0.0, lat_base + noise + random.uniform(-0.01, 0.01))
    memory  = BASE_MEMORY * mem_mult + random.randint(-5_000_000, 5_000_000)

    if current_scenario == "intermittent":
        error_rate = err_base if random.random() > 0.4 else 0.02
    else:
        error_rate = max(0.0, min(1.0, err_base + random.uniform(-0.03, 0.03)))

    return cpu, latency, error_rate, memory


def update_gauges():
    """Background thread: update Prometheus gauges every 2 seconds."""
    while True:
        cpu, lat, err, mem = get_metrics()
        g_cpu.set(cpu)
        g_latency.set(lat)
        g_error_rate.set(err)
        g_memory.set(mem)
        g_req_rate.set(random.uniform(80, 120) if current_scenario == "normal"
                       else random.uniform(200, 500))
        time.sleep(2)


threading.Thread(target=update_gauges, daemon=True).start()


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/metrics_json")
def metrics_json():
    """Rich JSON metrics — primary source for Neuro-Ops collector."""
    cpu, lat, err, mem = get_metrics()
    return jsonify({
        "cpu":          round(cpu, 4),
        "latency":      round(lat, 4),
        "error_rate":   round(err, 4),
        "memory":       int(mem),
        "request_rate": round(random.uniform(80, 150), 1),
        "scenario":     current_scenario,
        "degradation":  degradation_level,
    })


@app.route("/data")
def data():
    global degradation_level
    REQUEST_COUNT.inc()
    cpu, lat, err, mem = get_metrics()

    if err > 0.5 or degradation_level >= 4:
        ERROR_COUNT.inc()
        time.sleep(min(lat, 3.0))
        return jsonify({
            "error":    "service degraded",
            "scenario": current_scenario
        }), 500

    if lat > 0.5:
        time.sleep(min(lat, 3.0))

    ERROR_COUNT.inc() if random.random() < err else None

    return jsonify({
        "service":  "api",
        "data":     [random.randint(1, 100) for _ in range(5)],
        "scenario": current_scenario,
    })


@app.route("/health")
def health():
    cpu, lat, err, mem = get_metrics()
    return jsonify({
        "status":      "healthy" if err < 0.3 else "degraded",
        "scenario":    current_scenario,
        "degradation": degradation_level,
        "error_rate":  round(err, 3),
        "latency":     round(lat, 3),
        "cpu":         round(cpu, 3),
    })


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ── Demo scenario triggers ───────────────────────────────────────────────────

@app.route("/demo/<scenario>")
def trigger_demo(scenario):
    global current_scenario, degradation_level, scenario_start

    if scenario not in SCENARIOS and scenario != "recover":
        return jsonify({
            "error": "unknown scenario",
            "available": list(SCENARIOS.keys())
        }), 400

    if scenario == "recover":
        current_scenario  = "normal"
        degradation_level = 0
        scenario_start    = time.time()
        return jsonify({"status": "recovered", "scenario": "normal"})

    current_scenario  = scenario
    degradation_level = 5 if SCENARIOS[scenario][2] > 0.5 else 3
    scenario_start    = time.time()

    # auto recover after duration
    duration = SCENARIO_DURATION.get(scenario, 30)
    def _recover():
        global current_scenario, degradation_level
        time.sleep(duration)
        if current_scenario == scenario:  # only if not changed
            current_scenario  = "normal"
            degradation_level = 0
            print(f"[demo] auto-recovered from {scenario}")
    threading.Thread(target=_recover, daemon=True).start()

    return jsonify({
        "status":    "triggered",
        "scenario":  scenario,
        "duration":  duration,
        "signature": dict(zip(
            ["cpu", "latency", "errors", "memory_mult"],
            SCENARIOS[scenario]
        ))
    })


# legacy break/fix for backward compatibility
@app.route("/break")
def break_service():
    global degradation_level
    degradation_level = min(degradation_level + 1, 5)
    return jsonify({"level": degradation_level})


@app.route("/fix")
def fix_service():
    global current_scenario, degradation_level
    degradation_level = max(0, degradation_level - 1)
    if degradation_level == 0:
        current_scenario = "normal"
    return jsonify({"level": degradation_level})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)