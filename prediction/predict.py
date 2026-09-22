"""
Loads the trained risk model and predicts interruption risk as a PERCENTAGE
(0-100) from live instance telemetry + price signals.

shared/contracts.md defines risk_percent as 0-100 for the backend API response
and the "high risk" event — so this module returns the model's 0-1 score
scaled to 0-100. The raw 0-1 score is available via _predict_risk_raw.

This is what gets called at runtime (e.g. by monitoring/cloudwatch_collector.py
or the backend) to answer: "what's the current interruption risk for this VM?"

Usage:
    from predict import predict_risk
    risk_percent = predict_risk(
        instance_type="t3.micro",
        cpu_percent=72.5,
        ram_percent=60.0,
        network_mbps=15.2,
        instance_age_minutes=45,
        price_volatility=0.0001,
        price_trend_ratio=1.05,
        savings_percent=70,
    )   # -> float in [0, 100]
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


def _predict_risk_raw(
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
    Internal: returns the model's raw risk score clamped to [0, 1].
    Callers that need the contract-compliant percentage should use
    predict_risk (0-100) instead.
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
    # Strictly inside (0, 1), never exactly 0 or 1: a regression model can
    # saturate, but a risk probability must stay a valid strict probability.
    return min(0.999999, max(0.000001, risk_score))


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
    Returns the predicted interruption risk as a PERCENTAGE in [0, 100],
    matching risk_percent in shared/contracts.md (the backend API response
    and the "high risk" event both use 0-100).
    """
    raw = _predict_risk_raw(
        instance_type,
        cpu_percent,
        ram_percent,
        network_mbps,
        instance_age_minutes,
        price_volatility,
        price_trend_ratio,
        savings_percent,
    )
    return max(0.0, min(100.0, raw * 100.0))  # scale to percentage, clamp [0, 100]


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
    print(f"[predict] Predicted risk% for t3.micro under load: {test_risk:.2f}")

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
    print(f"[predict] Predicted risk% for t3.micro idle: {test_risk_idle:.2f}")

    for label, value in [("under load", test_risk), ("idle", test_risk_idle)]:
        assert isinstance(value, float), f"{label}: not a float"
        assert 0.0 <= value <= 100.0, f"{label}: risk not in [0, 100]"
    print("[predict] OK: both outputs are valid 0-100 percentage floats.")
    