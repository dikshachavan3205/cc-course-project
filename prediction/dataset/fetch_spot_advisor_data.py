"""
Fetches AWS's own published Spot Instance interruption-rate data.

This is REAL data — the same JSON file that powers the public AWS Spot
Instance Advisor webpage (https://aws.amazon.com/ec2/spot/instance-advisor/).
It contains actual observed interruption frequency ranges per instance
type, per region — not synthetic.

No AWS account/credentials needed for this call — it's a public,
unauthenticated JSON endpoint.

Output: prediction/dataset/raw/spot_advisor_data.json (raw AWS data)
        prediction/dataset/raw/interruption_rates.csv (flattened, usable)
"""

import json
import os
import requests
import pandas as pd

SPOT_ADVISOR_URL = "https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json"

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
RAW_JSON_PATH = os.path.join(RAW_DIR, "spot_advisor_data.json")
CSV_OUTPUT_PATH = os.path.join(RAW_DIR, "interruption_rates.csv")

# AWS encodes interruption frequency as a numeric "range index" (0-4),
# not a plain percentage. This mapping comes from AWS's own advisor
# frontend logic — we translate it to a usable numeric estimate.
INTERRUPTION_RANGE_LABELS = {
    0: "<5%",
    1: "5-10%",
    2: "10-15%",
    3: "15-20%",
    4: ">20%",
}
# Midpoint estimate for each range, used as a numeric feature/label input.
INTERRUPTION_RANGE_MIDPOINT = {
    0: 0.025,
    1: 0.075,
    2: 0.125,
    3: 0.175,
    4: 0.25,
}


def fetch_raw_data():
    os.makedirs(RAW_DIR, exist_ok=True)
    print(f"[fetch] Requesting {SPOT_ADVISOR_URL} ...")
    response = requests.get(SPOT_ADVISOR_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    with open(RAW_JSON_PATH, "w") as f:
        json.dump(data, f)
    print(f"[fetch] Saved raw JSON to {RAW_JSON_PATH}")
    return data


def flatten_to_csv(data: dict):
    """
    The raw AWS JSON is structured as:
      data["spot_advisor"][region][os][instance_type] = {"r": range_index, "s": savings_pct}
    We flatten this into a simple, tidy CSV: one row per (region, os, instance_type).
    """
    rows = []
    spot_advisor = data.get("spot_advisor", {})

    for region, os_map in spot_advisor.items():
        for os_name, instance_map in os_map.items():
            for instance_type, stats in instance_map.items():
                range_index = stats.get("r", 0)
                rows.append({
                    "region": region,
                    "os": os_name,
                    "instance_type": instance_type,
                    "interruption_range_index": range_index,
                    "interruption_range_label": INTERRUPTION_RANGE_LABELS.get(range_index, "unknown"),
                    "interruption_rate_estimate": INTERRUPTION_RANGE_MIDPOINT.get(range_index, 0.1),
                    "savings_percent": stats.get("s", None),
                })

    df = pd.DataFrame(rows)
    df.to_csv(CSV_OUTPUT_PATH, index=False)
    print(f"[fetch] Flattened {len(df)} rows -> {CSV_OUTPUT_PATH}")
    return df


if __name__ == "__main__":
    data = fetch_raw_data()
    df = flatten_to_csv(data)
    print(df.head(10))
    print(f"\n[fetch] Regions found: {df['region'].nunique()}")
    print(f"[fetch] Instance types found: {df['instance_type'].nunique()}")