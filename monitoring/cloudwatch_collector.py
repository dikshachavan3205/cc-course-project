"""Pull CPU/RAM/network metrics for a running instance from CloudWatch.

Only CPU is read from CloudWatch (metric: AWS/EC2 CPUUtilization). The
default EC2 CloudWatch metrics do NOT include RAM or network throughput,
so those come back as None — never fabricated. A real RAM/disk collector
would require the CloudWatch agent (CWAgent namespace) installed on the
instance; that is a deliberate follow-up, not something we fake here.

Output shape per poll:

    {
      "instance_id": "i-0abc...",
      "instance_type": "t3.micro" | None,
      "cpu_percent": 12.34 | None,   # latest CPUUtilization average, or None
      "ram_percent": None,           # NOT available via default EC2 metrics
      "timestamp_utc": "ISO8601"
    }

CLI:
  python -m monitoring.cloudwatch_collector --instance-id i-0abc --region ap-south-1 [--minutes 30]
Prints one JSON object to STDOUT; diagnostics go to STDERR (matches
monitoring/imds_watcher.py convention).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import boto3

# Make `shared/` importable whether run as `-m monitoring.cloudwatch_collector`
# (repo root on sys.path) or `python monitoring/cloudwatch_collector.py`.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import AWS_REGION  # noqa: E402

CPU_METRIC_NAME = "CPUUtilization"
CPU_NAMESPACE = "AWS/EC2"
CPU_DIMENSION_NAME = "InstanceId"
DEFAULT_LOOKBACK_MINUTES = 60


def get_instance_metrics(
    instance_id: str,
    region: str | None = None,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
) -> dict:
    """
    Returns the latest real CPUUtilization average from CloudWatch for the
    given instance, plus explicit-None values for anything the default EC2
    metrics do NOT expose (RAM in particular — never fabricated).

    cpu_percent is None when the metric can't be read (no access, no
    datapoints, instance gone) instead of raising — the caller decides
    how to behave when telemetry is missing.
    """
    region = region or AWS_REGION
    client = boto3.client("cloudwatch", region_name=region)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=lookback_minutes)

    cpu_percent = None
    try:
        response = client.get_metric_statistics(
            Namespace=CPU_NAMESPACE,
            MetricName=CPU_METRIC_NAME,
            Dimensions=[{"Name": CPU_DIMENSION_NAME, "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if datapoints:
            latest = max(datapoints, key=lambda dp: dp["Timestamp"])
            cpu_percent = round(float(latest["Average"]), 2)
    except Exception as exc:  # noqa: BLE001 - logged, then reported as None
        print(
            f"[cloudwatch_collector] WARNING: CPUUtilization read failed for "
            f"{instance_id} ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )

    metrics = {
        "instance_id": instance_id,
        "instance_type": None,  # not exposed by default EC2 CloudWatch metrics
        "cpu_percent": cpu_percent,
        # RAM is NOT in the default EC2 CloudWatch metric set (requires the
        # CloudWatch agent / CWAgent namespace). Explicit None, not fabricated.
        "ram_percent": None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read real CPU (and explicitly-None RAM) CloudWatch metrics "
                    "for an EC2 instance.",
    )
    parser.add_argument("--instance-id", required=True, help="EC2 instance id (i-...).")
    parser.add_argument(
        "--region", default=None,
        help=f"AWS region (default: {AWS_REGION} from shared/constants.py).",
    )
    parser.add_argument(
        "--minutes", type=int, default=DEFAULT_LOOKBACK_MINUTES,
        help="Lookback window for the average (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    metrics = get_instance_metrics(
        instance_id=args.instance_id,
        region=args.region,
        lookback_minutes=args.minutes,
    )
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())