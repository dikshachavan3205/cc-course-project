"""Live model features, computed the same way as at training time.

Training (prediction/dataset/generate_synthetic_data.py) used, per instance type:
  price_volatility  = sample std-dev of the spot price over 30 days
  price_trend_ratio = most recent price / mean price
  savings_percent   = AWS Spot Advisor savings for the type (ap-south-1, Linux)
These functions recompute them from LIVE data so the model sees real inputs.
"""
from __future__ import annotations

import csv
import os
import statistics
import time
from datetime import datetime, timedelta, timezone

ADVISOR_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "dataset", "raw", "interruption_rates.csv")
_price_cache: dict = {}


def compute_price_features(prices: list) -> dict:
    """prices: [(datetime, float), ...] -> {price_volatility, price_trend_ratio}."""
    vals = [p for _, p in prices]
    if not vals:
        return {"price_volatility": 0.0, "price_trend_ratio": 1.0}
    mean = statistics.fmean(vals)
    vol = statistics.stdev(vals) if len(vals) > 1 else 0.0
    recent = max(prices, key=lambda tp: tp[0])[1]
    return {"price_volatility": vol, "price_trend_ratio": (recent / mean) if mean else 1.0}


def savings_percent(instance_type: str, region: str = "ap-south-1", default: float = 50.0) -> float:
    try:
        with open(ADVISOR_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if (row["region"], row["os"], row["instance_type"]) == (region, "Linux", instance_type):
                    return float(row["savings_percent"])
    except Exception:  # noqa: BLE001
        pass
    return default


def price_features(instance_type: str, region: str, days: int = 30, ttl_s: int = 300) -> dict:
    """Live spot-price features via EC2 (read-only, free); cached for ttl_s."""
    hit = _price_cache.get(instance_type)
    if hit and time.time() - hit[0] < ttl_s:
        return hit[1]
    import boto3
    ec2 = boto3.client("ec2", region_name=region)
    end = datetime.now(timezone.utc)
    prices = []
    for page in ec2.get_paginator("describe_spot_price_history").paginate(
            InstanceTypes=[instance_type], ProductDescriptions=["Linux/UNIX"],
            StartTime=end - timedelta(days=days), EndTime=end):
        prices += [(h["Timestamp"], float(h["SpotPrice"])) for h in page["SpotPriceHistory"]]
    feats = compute_price_features(prices)
    _price_cache[instance_type] = (time.time(), feats)
    return feats


def live_features(instance_type: str, telemetry: dict, region: str = "ap-south-1") -> dict:
    """Keyword arguments for prediction.predict.predict_risk()."""
    return {
        "instance_type": instance_type,
        "cpu_percent": float(telemetry.get("cpu_percent") or 0.0),
        "ram_percent": float(telemetry.get("ram_percent") or 0.0),
        "network_mbps": float(telemetry.get("network_mbps") or 0.0),
        "instance_age_minutes": int(float(telemetry.get("instance_age_minutes") or 0)),
        "savings_percent": savings_percent(instance_type, region),
        **price_features(instance_type, region),
    }
