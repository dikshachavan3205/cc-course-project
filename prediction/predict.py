"""
Loads the trained risk model and predicts a risk score (0-1) from live
instance telemetry + price signals.

This is what gets called at runtime (e.g. by monitoring/cloudwatch_collector.py
or the backend) to answer: "what's the current interruption risk for this VM?"

Usage:
    from predict import predict_risk
    risk = predict_risk(
        instance_type="t3.micro",
        cpu_percent=72.5,
        ram_percent=60.0,
        network_mbps=15.2,
        instance_age_minutes=45,
        price_volatility=0.0001,
        price_trend_ratio=1.05,
        savings_percent=70,
    )
"""

import json
import os

import joblib
import pandas as pd

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "risk_model.pkl")
FEATURE_COLUMNS_PATH = os.path.join(MODEL_DIR, "feature_columns.json")

_model = None
_feature_columns = None


def _load_model():
    global _model, _feature_columns
    if _model is None:
        _model = joblib.load(MODEL_PATH)
        with open(FEATURE_COLUMNS_PATH, "r") as f:
            _feature_columns = json.load(f)
    return _model, _feature_columns


def predict_risk(
    instance_type: str,
    cpu_percent: float,
    ram_percent: float,
    network_mbps: float,
    instance_age_minutes: int,
    price_volatility: float = 0.0,
    price_trend_ratio: float = 1.0,
    savings_percent: float = 50.0,
) -> float:
    """
    Returns a risk score between 0 and 1 (matches risk_percent in
    shared/contracts.md — multiply by 100 if you need a percentage).
    """
    model, feature_columns = _load_model()

    # Build a single-row dataframe matching training format exactly.
    row = {
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "network_mbps": network_mbps,
        "instance_age_minutes": instance_age_minutes,
        "price_volatility": price_volatility,
        "price_trend_ratio": price_trend_ratio,
        "savings_percent": savings_percent,
    }

    # One-hot encode instance_type manually to match training columns —
    # any instance_type not seen during training just gets all zeros
    # (model falls back to telemetry/price signals only).
    for col in feature_columns:
        if col.startswith("instance_type_"):
            row[col] = 1 if col == f"instance_type_{instance_type}" else 0

    X = pd.DataFrame([row])[feature_columns]  # enforce exact column order

    risk_score = float(model.predict(X)[0])
    return max(0.0, min(1.0, risk_score))  # clamp to valid [0, 1] range


if __name__ == "__main__":
    # Quick manual test
    test_risk = predict_risk(
        instance_type="t3.micro",
        cpu_percent=85.0,
        ram_percent=78.0,
        network_mbps=25.0,
        instance_age_minutes=120,
        price_volatility=0.0001,
        price_trend_ratio=1.03,
        savings_percent=70,
    )
    print(f"[predict] Predicted risk for t3.micro under load: {test_risk:.4f}")

    test_risk_idle = predict_risk(
        instance_type="t3.micro",
        cpu_percent=10.0,
        ram_percent=20.0,
        network_mbps=2.0,
        instance_age_minutes=10,
        price_volatility=0.0001,
        price_trend_ratio=1.0,
        savings_percent=70,
    )
    print(f"[predict] Predicted risk for t3.micro idle: {test_risk_idle:.4f}")
    