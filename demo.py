"""
demo.py  —  Neuro-Ops 10-Scenario Demo Runner

Usage:
    python demo.py                   # run all 10 scenarios in sequence
    python demo.py payment_failure   # run one specific scenario
    python demo.py --list            # show all scenario names

Each scenario:
  1. Triggers the metric signature on the API service
  2. Waits for the pipeline to detect it (up to 30 s)
  3. Prints what was detected and what action was taken
  4. Waits for auto-recovery before the next scenario
"""

import sys
import time
import requests

CORE_API  = "http://localhost:8000"   # Neuro-Ops FastAPI (proxied via nginx)
SVC_API   = "http://localhost:5001"   # NovaPay API service (direct)

SCENARIOS = [
    ("payment_failure",    "Payment Gateway Failure",   "High errors, low CPU — gateway fault"),
    ("traffic_overload",   "Traffic Overload",          "CPU spike + latency spike together"),
    ("memory_leak",        "Memory Leak",               "Memory growing linearly over time"),
    ("bad_deployment",     "Bad Deployment",            "Sudden error spike after stable period"),
    ("db_slowdown",        "Database Slowdown",         "High latency, moderate errors, low CPU"),
    ("cascade_failure",    "Cascade Failure",           "Everything degrading simultaneously"),
    ("network_latency",    "Network Latency Spike",     "Extreme latency, low errors, normal CPU"),
    ("recovery",           "Service Recovery",          "Metrics returning to normal"),
    ("predicted_failure",  "Predicted Failure",         "CPU + memory slowly rising"),
    ("resource_exhaustion","Resource Exhaustion",       "CPU sustained above 90%"),
]

WAIT_FOR_DETECT = 30   # seconds to wait for pipeline to detect
BETWEEN_SCENARIOS = 20  # seconds between scenarios


def _sep(char="─", width=70):
    print(char * width)


def _poll_status():
    try:
        r = requests.get(f"{CORE_API}/api/status", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _trigger(scenario_id: str):
    try:
        r = requests.get(f"{SVC_API}/demo/{scenario_id}", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def run_scenario(scenario_id: str, name: str, description: str):
    _sep("═")
    print(f"  SCENARIO: {name}")
    print(f"  Signature: {description}")
    _sep()

    # Trigger
    result = _trigger(scenario_id)
    if "error" in result:
        print(f"  ✗ Trigger failed: {result['error']}")
        print(f"    (Make sure the API service is running on port 5001)")
        return
    print(f"  ✓ Triggered — auto-recovers in {result.get('auto_recover_in', '?')}s")

    # Poll for detection
    detected    = False
    start       = time.time()
    last_type   = None

    print(f"  Waiting for anomaly detection", end="", flush=True)

    while time.time() - start < WAIT_FOR_DETECT:
        time.sleep(3)
        status = _poll_status()

        if "error" in status:
            print(".", end="", flush=True)
            continue

        anomaly    = status.get("anomaly", {})
        root_cause = status.get("root_cause", {})
        auto_action = status.get("auto_action")

        if anomaly.get("is_anomaly"):
            print()  # newline after dots
            _sep("-")
            print(f"  ✓ DETECTED in {time.time()-start:.1f}s")
            print(f"    Type      : {anomaly.get('type', '—')}")
            print(f"    Label     : {root_cause.get('human_label', '—')}")
            print(f"    Severity  : {root_cause.get('severity', '—').upper()}")
            print(f"    Confidence: {anomaly.get('confidence', 0):.0%}")
            print(f"    Reason    : {', '.join(anomaly.get('reasons', []))}")
            print(f"    Action    : {root_cause.get('action', '—')}")
            print(f"    Impact    : {root_cause.get('impact', '—')}")
            if root_cause.get("affected_services"):
                print(f"    Services  : {', '.join(root_cause['affected_services'])}")
            if auto_action:
                ok = "✓" if auto_action.get("success") else "✗"
                print(f"    Auto-heal : {ok} {auto_action.get('label', auto_action.get('action', '—'))}")
            detected = True
            break

        elif status.get("prediction", {}).get("failure_predicted") and scenario_id == "predicted_failure":
            print()
            _sep("-")
            pred = status["prediction"]
            print(f"  ✓ PREDICTED in {time.time()-start:.1f}s (pre-failure detection)")
            print(f"    Risk level : {pred.get('risk_level', '—').upper()}")
            print(f"    Forecast   : health → {pred.get('predicted_health', '—')} in ~{pred.get('time_to_failure_seconds', '?')}s")
            detected = True
            break

        print(".", end="", flush=True)

    if not detected:
        print()
        print(f"  ⚠ Not detected within {WAIT_FOR_DETECT}s")
        print(f"    — Model may still be warming up (needs 30 baseline samples)")
        print(f"    — Current status: health={status.get('health_score', '?')}, "
              f"model_trained={status.get('model_trained', False)}")

    print(f"\n  Waiting {BETWEEN_SCENARIOS}s for recovery before next scenario...")
    time.sleep(BETWEEN_SCENARIOS)


def check_warmup():
    """Wait until the model is trained before starting the demo."""
    print("Checking pipeline readiness...")
    for _ in range(20):
        status = _poll_status()
        if status.get("model_trained"):
            print(f"✓ Model is trained — health={status.get('health_score', '?')}")
            return True
        print("  Model warming up, waiting 5s...")
        time.sleep(5)
    print("⚠ Model not trained after 100s — demo will proceed but detection may miss early scenarios")
    return False


def main():
    args = sys.argv[1:]

    if "--list" in args:
        print("\nAvailable scenarios:")
        for sid, name, desc in SCENARIOS:
            print(f"  {sid:<25} {name:<30} {desc}")
        return

    print()
    print("  ███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗       ██████╗ ██████╗ ███████╗")
    print("  ████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗     ██╔═══██╗██╔══██╗██╔════╝")
    print("  ██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║     ██║   ██║██████╔╝███████╗")
    print("  ██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║     ██║   ██║██╔═══╝ ╚════██║")
    print("  ██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝     ╚██████╔╝██║     ███████║")
    print("  ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝       ╚═════╝ ╚═╝     ╚══════╝")
    print()
    print("  10-Scenario Anomaly Detection Demo")
    print()

    check_warmup()
    print()

    if args:
        # Run a single named scenario
        sid = args[0]
        match = next((s for s in SCENARIOS if s[0] == sid), None)
        if not match:
            print(f"Unknown scenario: {sid}")
            print("Run with --list to see available scenarios")
            sys.exit(1)
        run_scenario(*match)
    else:
        # Run all 10 in order
        print(f"Running all {len(SCENARIOS)} scenarios...\n")
        for scenario in SCENARIOS:
            run_scenario(*scenario)

    _sep("═")
    print("  Demo complete.")
    print("  Open the dashboard at http://localhost:3000 to review incident history.")
    _sep("═")


if __name__ == "__main__":
    main()