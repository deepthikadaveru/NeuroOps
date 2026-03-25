"""
Anomaly Detector
IsolationForest model + rule-based type classifier.
The classifier uses METRIC SIGNATURES (combinations of feature values)
so each of the 10 scenarios maps to a distinct type reliably.
"""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from collections import deque
import joblib
import os

FEATURE_KEYS = [
    "raw_error_rate",       # 0
    "raw_cpu",              # 1
    "raw_latency",          # 2
    "cpu_spike_rate",       # 3
    "error_acceleration",   # 4
    "memory_growth_rate",   # 5
    "latency_variation",    # 6
]

MODEL_PATH  = "models/isolation_forest.pkl"
SCALER_PATH = "models/scaler.pkl"


class AnomalyDetector:
    def __init__(self, contamination=0.12, min_samples=30):
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=150,
            random_state=42,
        )
        self.scaler       = StandardScaler()
        self.min_samples  = min_samples
        self.training_data = deque(maxlen=500)
        self.is_trained   = False
        self._load_if_exists()

    def _load_if_exists(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            self.model   = joblib.load(MODEL_PATH)
            self.scaler  = joblib.load(SCALER_PATH)
            self.is_trained = True
            print("[anomaly] loaded existing model")

    def _save(self):
        os.makedirs("models", exist_ok=True)
        joblib.dump(self.model,  MODEL_PATH)
        joblib.dump(self.scaler, SCALER_PATH)

    def _extract_vector(self, features: dict) -> list:
        return [features.get(k, 0.0) for k in FEATURE_KEYS]

    def add_sample(self, features: dict):
        vector = self._extract_vector(features)
        self.training_data.append(vector)
        if len(self.training_data) >= self.min_samples:
            if len(self.training_data) % 50 == 0 or not self.is_trained:
                self._train()

    def _train(self):
        X        = np.array(self.training_data)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_trained = True
        self._save()
        print(f"[anomaly] model trained on {len(self.training_data)} samples")

    # ── Classification logic ─────────────────────────────────────────────────
    @staticmethod
    def _classify(f: dict, is_anomaly: bool, confidence: float) -> str:
        """
        Determine anomaly type from metric signatures.
        Uses raw feature values (not deviations) for reliable scenario matching.
        """
        if not is_anomaly:
            if confidence > 0.65:
                return "predicted_risk"
            return "normal"

        err  = f.get("raw_error_rate", 0)
        cpu  = f.get("raw_cpu", 0)
        lat  = f.get("raw_latency", 0)
        mem  = f.get("raw_memory", 0)
        mgr  = f.get("memory_growth_rate", 0)
        csr  = f.get("cpu_spike_rate", 0)
        ea   = f.get("error_acceleration", 0)
        lv   = f.get("latency_variation", 0)

        # Normalised memory (bytes → fraction against 600 MB ceiling)
        mem_norm = mem / 600_000_000

        # ── Priority-ordered signature matching ───────────────────────────────

        # 6. Cascade failure — everything elevated simultaneously
        if err > 0.60 and cpu > 0.75 and lat > 2.5:
            return "cascade_failure"

        # 1. Payment gateway failure — high errors, LOW cpu
        if err > 0.60 and cpu < 0.30:
            return "payment_failure_spike"

        # 4. Bad deployment — error spike, error accelerating, normal cpu
        if err > 0.45 and ea > 0.05 and cpu < 0.35:
            return "bad_deployment"

        # 2. Traffic overload — high cpu AND high latency together
        if cpu > 0.70 and csr > 0.15 and lat > 0.80:
            return "traffic_overload"

        # 10. Resource exhaustion — cpu very high but latency moderate, errors low
        if cpu > 0.85 and err < 0.15 and lat < 2.0:
            return "resource_exhaustion"

        # 5. Database slowdown — high latency, moderate errors, LOW cpu
        if lat > 1.5 and err > 0.15 and cpu < 0.35:
            return "db_slowdown"

        # 7. Network latency spike — extreme latency, low errors, normal cpu
        if lat > 2.5 and err < 0.10 and cpu < 0.35:
            return "network_latency_spike"

        # 3. Memory leak — memory growing (growth rate high), other metrics stable
        if mgr > 3_000_000 or mem_norm > 0.60:
            return "memory_leak"

        # 8. Service recovery — metrics improving (latency variation high, errors falling)
        if lv > 0.30 and ea < -0.02:
            return "service_recovery"

        # 9. Predicted failure — risk building up (cpu trending, error rate low but rising)
        if confidence > 0.65 and cpu > 0.40 and err < 0.25:
            return "predicted_risk"

        # Generic fallback
        return "generic_anomaly"

    def predict(self, features: dict) -> dict:
        if not self.is_trained:
            return {
                "is_anomaly":    False,
                "anomaly_score": 0.0,
                "confidence":    0.0,
                "type":          "warming_up",
                "reasons":       [],
                "status":        "warming up — collecting baseline",
            }

        vector        = np.array([self._extract_vector(features)])
        vector_scaled = self.scaler.transform(vector)

        prediction = self.model.predict(vector_scaled)[0]   # 1=normal, -1=anomaly
        score      = self.model.score_samples(vector_scaled)[0]

        is_anomaly = bool(prediction == -1)
        confidence = min(1.0, max(0.0, abs(score) / 0.5))

        # ── Feature deviation explanations ───────────────────────────────────
        feature_vector = vector[0]
        means = self.scaler.mean_
        stds  = np.sqrt(self.scaler.var_)

        feature_impacts = []
        for i, key in enumerate(FEATURE_KEYS):
            deviation = abs((feature_vector[i] - means[i]) / (stds[i] + 1e-6))
            if deviation > 1.8:
                feature_impacts.append((key, deviation))

        feature_impacts.sort(key=lambda x: x[1], reverse=True)

        REASON_MAP = {
            "raw_error_rate":     "abnormal error spike",
            "raw_cpu":            "unusual CPU behavior",
            "raw_latency":        "latency anomaly",
            "cpu_spike_rate":     "traffic surge detected",
            "error_acceleration": "rapid error escalation",
            "memory_growth_rate": "memory growth anomaly",
            "latency_variation":  "unstable response times",
        }
        reasons = [REASON_MAP[k] for k, _ in feature_impacts[:3] if k in REASON_MAP]

        anomaly_type = self._classify(features, is_anomaly, confidence)

        return {
            "is_anomaly":    is_anomaly,
            "anomaly_score": round(float(score), 4),
            "confidence":    round(float(confidence), 4),
            "type":          anomaly_type,
            "reasons":       reasons,
            "status":        "anomaly detected" if is_anomaly else "normal",
        }