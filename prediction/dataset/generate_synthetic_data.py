"""
Builds the final training dataset by combining:
  1. REAL AWS interruption rate data (interruption_rates.csv)
  2. REAL AWS spot price history (spot_price_history.csv)
  3. SIMULATED system telemetry (CPU/RAM/network) — since we don't have
     months of real production telemetry, this is generated, but
     correlated with the REAL interruption rate for that instance type
     (higher real-world risk instance types get noisier/spikier
     simulated telemetry, reflecting realistic resource contention).

Output: prediction/dataset/processed/training_data.csv
Each row = one snapshot in time for one (instance_type, region) pair,
with a risk_label (0-1) derived from real AWS data.
"""

import os
import numpy as np
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "processed")
OUTPUT_PATH = os.path.join(PROCESSED_DIR, "training_data.csv")

INTERRUPTION_CSV = os.path.join(RAW_DIR, "interruption_rates.csv")
PRICE_CSV = os.path.join(RAW_DIR, "spot_price_history.csv")

TARGET_REGION = "ap-south-1"
ROWS_PER_INSTANCE_TYPE = 50  # simulated telemetry snapshots per instance type

np.random.seed(42)  # reproducible synthetic component


def load_real_data():
    interruption_df = pd.read_csv(INTERRUPTION_CSV)
    price_df = pd.read_csv(PRICE_CSV)

    # Focus on our target region + Linux (matches price history OS)
    interruption_df = interruption_df[
        (interruption_df["region"] == TARGET_REGION) &
        (interruption_df["os"] == "Linux")
    ]

    return interruption_df, price_df


def compute_price_volatility(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each instance_type, compute price volatility (std dev of price)
    and price trend (recent price vs overall mean) from REAL price history.
    """
    price_df["timestamp"] = pd.to_datetime(price_df["timestamp"])
    grouped = price_df.groupby("instance_type")["spot_price"]

    volatility = grouped.std().fillna(0).rename("price_volatility")
    mean_price = grouped.mean().rename("mean_price")

    # "Recent price" = most recent observation per instance type
    recent_price = (
        price_df.sort_values("timestamp")
        .groupby("instance_type")["spot_price"]
        .last()
        .rename("recent_price")
    )

    summary = pd.concat([mean_price, volatility, recent_price], axis=1).reset_index()
    summary["price_trend_ratio"] = summary["recent_price"] / summary["mean_price"]
    return summary


def simulate_telemetry_row(base_risk: float) -> dict:
    """
    Simulates one CPU/RAM/network snapshot. Higher base_risk (from REAL
    AWS interruption data) produces noisier, higher-load telemetry —
    modeling the realistic idea that instance types under heavier demand
    (and thus more prone to being reclaimed) also tend to show more
    resource contention symptoms.
    """
    load_bias = base_risk * 40  # scales noise/load with real risk

    cpu_percent = np.clip(np.random.normal(50 + load_bias, 15), 0, 100)
    ram_percent = np.clip(np.random.normal(55 + load_bias * 0.8, 12), 0, 100)
    network_mbps = np.clip(np.random.normal(20 + load_bias * 0.5, 8), 0, None)
    instance_age_minutes = np.random.randint(1, 720)  # up to 12 hours old

    return {
        "cpu_percent": round(cpu_percent, 2),
        "ram_percent": round(ram_percent, 2),
        "network_mbps": round(network_mbps, 2),
        "instance_age_minutes": instance_age_minutes,
    }


def build_dataset():
    interruption_df, price_df = load_real_data()
    price_summary = compute_price_volatility(price_df)

    # Only keep instance types we actually have BOTH real interruption
    # data AND real price history for.
    merged_meta = pd.merge(
        interruption_df, price_summary, on="instance_type", how="inner"
    )

    if merged_meta.empty:
        raise RuntimeError(
            "No overlapping instance types between interruption data and "
            "price history. Check TARGET_REGION / instance type lists match."
        )

    print(f"[generate] {len(merged_meta)} instance types have both real "
          f"interruption + price data. Generating {ROWS_PER_INSTANCE_TYPE} "
          f"telemetry snapshots each...")

    rows = []
    for _, meta in merged_meta.iterrows():
        base_risk = meta["interruption_rate_estimate"]  # REAL AWS value

        for _ in range(ROWS_PER_INSTANCE_TYPE):
            telemetry = simulate_telemetry_row(base_risk)

            row = {
                "instance_type": meta["instance_type"],
                "region": TARGET_REGION,
                **telemetry,
                "price_volatility": meta["price_volatility"],
                "price_trend_ratio": meta["price_trend_ratio"],
                "savings_percent": meta["savings_percent"],
                # ── Label: the thing we're training the model to predict ──
                # Base comes from REAL AWS interruption rate, with a small
                # amount of noise added per-snapshot so the model learns
                # a smooth relationship rather than memorizing exact values.
                "risk_label": np.clip(
                    base_risk + np.random.normal(0, 0.02), 0, 1
                ),
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"[generate] Saved {len(df)} rows -> {OUTPUT_PATH}")
    return df


if __name__ == "__main__":
    df = build_dataset()
    print(df.head(10))
    print(f"\n[generate] Instance types covered: {df['instance_type'].nunique()}")
    print(f"[generate] Risk label range: {df['risk_label'].min():.3f} - {df['risk_label'].max():.3f}")