"""
Fetches REAL historical Spot pricing data via boto3's describe_spot_price_history.

This pulls actual observed price fluctuations for a set of instance types
in our target region over the last N days. Price volatility (how much and
how fast price changes) is a genuine signal correlated with interruption
risk — rapid price increases often precede capacity crunches that lead
to interruptions.

No cost to call this API — it's a read-only describe call, no resources
are created.

Output: prediction/dataset/raw/spot_price_history.csv
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import boto3
import pandas as pd

# Make shared/ importable
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import AWS_REGION

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
CSV_OUTPUT_PATH = os.path.join(RAW_DIR, "spot_price_history.csv")

# A representative spread of instance types — small/medium general purpose,
# since these are the most commonly used and most likely to be relevant
# to a student project's demo (t3/t2/m5 families).
INSTANCE_TYPES = [
    "t3.micro", "t3.small", "t3.medium",
    "t2.micro", "t2.small", "t2.medium",
    "m5.large", "m5.xlarge",
]

LOOKBACK_DAYS = 30


def fetch_price_history():
    os.makedirs(RAW_DIR, exist_ok=True)

    client = boto3.client("ec2", region_name=AWS_REGION)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=LOOKBACK_DAYS)

    all_rows = []

    print(f"[fetch] Pulling {LOOKBACK_DAYS} days of spot price history for "
          f"{len(INSTANCE_TYPES)} instance types in {AWS_REGION} ...")

    paginator = client.get_paginator("describe_spot_price_history")
    for instance_type in INSTANCE_TYPES:
        page_iterator = paginator.paginate(
            InstanceTypes=[instance_type],
            ProductDescriptions=["Linux/UNIX"],
            StartTime=start_time,
            EndTime=end_time,
        )
        count_for_type = 0
        for page in page_iterator:
            for entry in page["SpotPriceHistory"]:
                all_rows.append({
                    "instance_type": entry["InstanceType"],
                    "availability_zone": entry["AvailabilityZone"],
                    "spot_price": float(entry["SpotPrice"]),
                    "timestamp": entry["Timestamp"].isoformat(),
                })
                count_for_type += 1
        print(f"[fetch]   {instance_type}: {count_for_type} price points")

    df = pd.DataFrame(all_rows)
    df.to_csv(CSV_OUTPUT_PATH, index=False)
    print(f"[fetch] Saved {len(df)} total rows -> {CSV_OUTPUT_PATH}")
    return df


if __name__ == "__main__":
    df = fetch_price_history()
    print(df.head(10))