import time
import threading
from collector import collect_snapshot
from processor import add_snapshot, compute_features, get_trend
from anomaly_detector import AnomalyDetector
from root_cause import analyze
from automator import execute_action, get_action_log
from predictor import FailurePredictor
from config import POLL_INTERVAL

feature_log = []
anomaly_log = []
detector    = AnomalyDetector()
predictor   = FailurePredictor()

last_action      = {}
COOLDOWN_SECONDS = 30


def should_act(action: str) -> bool:
    now = time.time()
    if action in last_action:
        if now - last_action[action] < COOLDOWN_SECONDS:
            return False
    last_action[action] = now
    return True

def set_auto_heal(state: bool):
    global AUTO_HEAL_ENABLED
    AUTO_HEAL_ENABLED = state


def run_pipeline():
    print("[neuro-ops] pipeline started")
    while True:
        try:
            # 1. collect
            snapshot = collect_snapshot()

            # 2. store history
            add_snapshot(snapshot)

            # 3. compute features
            features = compute_features(snapshot)
            features["cpu_trend"]     = get_trend("cpu_usage")
            features["error_trend"]   = get_trend("api_error_rate")
            features["latency_trend"] = get_trend("web_latency")

            # 4. anomaly detection
            detector.add_sample(features)
            anomaly = detector.predict(features)
            features["anomaly"] = anomaly

            # 5. root cause analysis
            cause = analyze(features, anomaly)
            features["root_cause"] = cause

            # 6. failure prediction
            predictor.add_sample(features)
            prediction = predictor.predict()
            features["prediction"] = prediction

            # 7. autonomous action
            should_intervene = (
                anomaly["is_anomaly"] or
                prediction.get("risk_level") in ["critical", "high"]
            )

            if should_intervene and cause.get("action") and cause["action"] != "alert":
                action = cause["action"]
                if should_act(action):
                    reason = cause["description"]
                    if prediction.get("failure_predicted"):
                        reason = f"[PREDICTED] {reason}"
                    print(f"[neuro-ops] intervening: {action} | {reason}")
                    if AUTO_HEAL_ENABLED:
                        action_result = execute_action(action, reason)
                    else:
                        action_result = {
                             "action": action,
                                "label": action,
                                "success": False,
                                "reason": "auto-heal disabled"
                        }
                    features["auto_action"] = result
                else:
                    features["auto_action"] = {"action": action, "status": "cooldown"}
            else:
                features["auto_action"] = None

            # 8. log
            status_str  = "ANOMALY" if anomaly["is_anomaly"] else "normal"
            risk        = prediction.get("risk_level", "unknown")
            pred_health = prediction.get("predicted_health", "?")
            print(
                f"[{features['timestamp']}] "
                f"health={features['health_score']} "
                f"status={status_str} "
                f"type={anomaly.get('type','—')} "
                f"risk={risk} "
                f"pred={pred_health} "
                f"action={features.get('auto_action')}"
            )

            # Only log to anomaly_log when:
            #   a) it IS an anomaly AND root_cause has a real label (not null/normal)
            #   b) OR failure is predicted AND root cause is set
            # This prevents "Anomaly Detected / All systems operating normally" ghost entries
            has_real_cause = (
                cause.get("root_cause") is not None and
                cause.get("root_cause") != "unknown" and
                cause.get("description") != "All systems operating normally"
            )

            should_log = (
                (anomaly["is_anomaly"] and has_real_cause) or
                (prediction.get("failure_predicted") and has_real_cause)
            )

            if should_log:
                anomaly_log.append({
                    "timestamp":    features["timestamp"],
                    "anomaly":      anomaly,
                    "root_cause":   cause,
                    "prediction":   prediction,
                    "health_score": features["health_score"],
                    "auto_action":  features.get("auto_action"),
                })
                if len(anomaly_log) > 100:
                    anomaly_log.pop(0)

            feature_log.append(features)
            if len(feature_log) > 200:
                feature_log.pop(0)

        except Exception as e:
            print(f"[pipeline] error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(POLL_INTERVAL)