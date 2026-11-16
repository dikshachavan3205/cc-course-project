"""Trigger a REAL migration for a running ChronoNet instance.

Builds the same high-risk event a real Spot interruption notice would produce
and runs the full 7-step recovery flow against real AWS: forced checkpoint ->
provision replacement Spot instance -> resume from S3 -> terminate old
instance -> SNS alert.

Usage (from the repo root, venv active, AWS credentials set and
CHRONONET_ALLOW_REAL_EC2=true):
    python trigger_migration.py --run-id run-laptop-20261116-120000 --vm-id i-0123456789abcdef0
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from monitoring.imds_watcher import build_high_risk_event  # noqa: E402
from orchestration.recovery_flow import run_migration  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--vm-id", required=True,
                    help="the running instance to migrate AWAY from (i-...)")
    ap.add_argument("--risk", type=int, default=100)
    args = ap.parse_args()
    event = build_high_risk_event(run_id=args.run_id, vm_id=args.vm_id,
                                  risk_percent=args.risk)
    print("[event] " + json.dumps(event))
    result = run_migration(
        event,
        provision_mode="real",
        allow_real_ec2=(os.environ.get("CHRONONET_ALLOW_REAL_EC2", "").lower() == "true"),
    )
    print("[result] " + json.dumps(result, indent=2, default=str))
    status = str(result.get("status", ""))
    print("[trigger] " + ("PASS" if status.startswith("completed") else "FAIL"))
    return 0 if status.startswith("completed") else 1


if __name__ == "__main__":
    sys.exit(main())
