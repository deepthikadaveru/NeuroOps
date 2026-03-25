import numpy as np
from collections import deque
from datetime import datetime

PREDICTION_WINDOW = 12  # number of samples to look back
PREDICTION_HORIZON = 6  # predict this many steps ahead (30 seconds)

class FailurePredictor:
    def __init__(self):
        self.history = deque(maxlen=100)
        self.predictions = []

    def add_sample(self, features: dict):
        self.history.append({
            "timestamp": features.get("timestamp"),
            "health_score": features.get("health_score", 100),
            "error_rate": features.get("raw_error_rate", 0),
            "cpu": features.get("raw_cpu", 0),
            "memory": features.get("raw_memory", 0),
            "latency": features.get("raw_latency", 0),
        })

    def _linear_forecast(self, values: list, steps_ahead: int) -> float:
        if len(values) < 3:
            return values[-1] if values else 0
        x = np.arange(len(values))
        slope, intercept = np.polyfit(x, values, 1)
        future_x = len(values) + steps_ahead
        return slope * future_x + intercept

    def predict(self) -> dict:
        if len(self.history) < PREDICTION_WINDOW:
            return {
                "status": "warming up",
                "samples_collected": len(self.history),
                "samples_needed": PREDICTION_WINDOW,
                "failure_predicted": False,
                "predicted_health": None,
                "time_to_failure_seconds": None,
                "risk_level": "unknown"
            }

        recent = list(self.history)[-PREDICTION_WINDOW:]

        health_values = [s["health_score"] for s in recent]
        error_values = [s["error_rate"] for s in recent]
        cpu_values = [s["cpu"] for s in recent]

        # forecast values 30 seconds ahead
        predicted_health = self._linear_forecast(health_values, PREDICTION_HORIZON)
        predicted_error = self._linear_forecast(error_values, PREDICTION_HORIZON)
        predicted_cpu = self._linear_forecast(cpu_values, PREDICTION_HORIZON)

        # clamp to valid range
        predicted_health = max(0, min(100, predicted_health))
        predicted_error = max(0, min(1, predicted_error))

        # calculate health trend slope
        health_slope = np.polyfit(range(len(health_values)), health_values, 1)[0]

        # determine risk level
        failure_predicted = False
        time_to_failure = None
        risk_level = "low"

        if predicted_health < 30 or predicted_error > 0.7:
            risk_level = "critical"
            failure_predicted = True
            # estimate time to failure based on slope
            if health_slope < 0:
                current_health = health_values[-1]
                time_to_failure = int((current_health / abs(health_slope)) * 5)
        elif predicted_health < 50 or predicted_error > 0.4:
            risk_level = "high"
        elif predicted_health < 65 or health_slope < -0.5:
            risk_level = "medium"

        prediction = {
            "status": "active",
            "failure_predicted": failure_predicted,
            "predicted_health": round(predicted_health, 2),
            "predicted_error_rate": round(predicted_error, 4),
            "predicted_cpu": round(predicted_cpu, 4),
            "health_trend_slope": round(float(health_slope), 4),
            "risk_level": risk_level,
            "time_to_failure_seconds": time_to_failure,
            "samples_used": len(recent),
            "timestamp": datetime.utcnow().isoformat()
        }

        self.predictions.append(prediction)
        if len(self.predictions) > 100:
            self.predictions.pop(0)

        return prediction

    def get_history(self):
        return self.predictions[-20:]