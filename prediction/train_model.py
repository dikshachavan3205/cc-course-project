"""
Trains a model to predict Spot interruption risk (0-1) from instance
type + simulated telemetry + real price signals.

Uses XGBoost (regression, since risk_label is continuous 0-1, not a
binary yes/no).

Input:  prediction/dataset/processed/training_data.csv
Output: prediction/model/risk_model.pkl (trained model)
        prediction/model/feature_columns.json (column order/encoding info,
        so predict.py can reconstruct the same feature format later)
"""

import json
import os

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor

PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset", "processed")
DATA_PATH = os.path.join(PROCESSED_DIR, "training_data.csv")

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "risk_model.pkl")
FEATURE_COLUMNS_PATH = os.path.join(MODEL_DIR, "feature_columns.json")

# instance_type is categorical -> one-hot encoded.
# region is dropped since it's constant (ap-south-1) in this dataset.
CATEGORICAL_COLUMNS = ["instance_type"]
NUMERIC_FEATURE_COLUMNS = [
    "cpu_percent", "ram_percent", "network_mbps", "instance_age_minutes",
    "price_volatility", "price_trend_ratio", "savings_percent",
]
TARGET_COLUMN = "risk_label"


def load_and_prepare_data():
    df = pd.read_csv(DATA_PATH)

    # One-hot encode instance_type -> instance_type_t3.micro, etc.
    df_encoded = pd.get_dummies(df, columns=CATEGORICAL_COLUMNS)

    feature_columns = NUMERIC_FEATURE_COLUMNS + [
        col for col in df_encoded.columns if col.startswith("instance_type_")
    ]

    X = df_encoded[feature_columns]
    y = df_encoded[TARGET_COLUMN]

    return X, y, feature_columns


def train():
    X, y, feature_columns = load_and_prepare_data()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"[train] Training on {len(X_train)} rows, testing on {len(X_test)} rows, "
          f"{len(feature_columns)} features.")

    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    print(f"[train] Test MAE: {mae:.4f}")
    print(f"[train] Test R^2: {r2:.4f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    with open(FEATURE_COLUMNS_PATH, "w") as f:
        json.dump(feature_columns, f)

    print(f"[train] Model saved -> {MODEL_PATH}")
    print(f"[train] Feature columns saved -> {FEATURE_COLUMNS_PATH}")


if __name__ == "__main__":
    train()