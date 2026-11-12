"""Launch the FIRST real ChronoNet workload instance (Spot, On-Demand fallback).

Usage (PowerShell, from the repo root, after setting the env vars below):
  python -m orchestration.launch_primary --print-user-data   # inspect, no AWS calls
  python -m orchestration.launch_primary                     # launch for real

Required env:  CHRONONET_ALLOW_REAL_EC2=true  CHRONONET_AMI=ami-...
               CHRONONET_SECURITY_GROUP_IDS=sg-...  CHRONONET_SUBNET_ID=subnet-...
Optional env:  CHRONONET_INSTANCE_TYPE (default t3.micro)

The instance bootstraps itself (orchestration/user_data.py), starts the
workload, checkpoints to S3 and registers in DynamoDB. Costs real (small) money.
"""
import argparse
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from data_backend.aws.dynamodb_client import DynamoDBClient  # noqa: E402
from orchestration.launch_instance import provision_instance  # noqa: E402
from orchestration.step_logger import StepLogger  # noqa: E402
from orchestration.user_data import (  # noqa: E402
    DEFAULT_CONFIG, build_user_data, save_run_config,
)
from shared.constants import (  # noqa: E402
    AWS_REGION, INSTANCE_TYPE, S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Launch the primary ChronoNet instance")
    ap.add_argument("--run-id", default=None, help="default: run-<UTC timestamp>")
    ap.add_argument("--instance-type", default=os.environ.get("CHRONONET_INSTANCE_TYPE", INSTANCE_TYPE))
    ap.add_argument("--subnet-id", default=os.environ.get("CHRONONET_SUBNET_ID"))
    ap.add_argument("--total-steps", type=int, default=DEFAULT_CONFIG["total_steps"])
    ap.add_argument("--step-delay", type=float, default=DEFAULT_CONFIG["step_delay"])
    ap.add_argument("--checkpoint-interval", type=int, default=DEFAULT_CONFIG["checkpoint_interval"])
    ap.add_argument("--ttl-minutes", type=int, default=DEFAULT_CONFIG["ttl_minutes"])
    ap.add_argument("--repo-url", default=DEFAULT_CONFIG["repo_url"])
    ap.add_argument("--repo-ref", default=DEFAULT_CONFIG["repo_ref"])
    ap.add_argument("--print-user-data", action="store_true", help="print the bootstrap script and exit")
    args = ap.parse_args()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    cfg = {"repo_url": args.repo_url, "repo_ref": args.repo_ref, "total_steps": args.total_steps,
           "step_delay": args.step_delay, "checkpoint_interval": args.checkpoint_interval,
           "ttl_minutes": args.ttl_minutes}
    user_data = build_user_data(run_id=run_id, **cfg)

    if args.print_user_data:
        print(user_data)
        return 0

    allow = os.environ.get("CHRONONET_ALLOW_REAL_EC2", "").lower() == "true"
    sgs = [s for s in (os.environ.get("CHRONONET_SECURITY_GROUP_IDS") or "").split(",") if s]
    logger = StepLogger(owner="launch_primary", run_id=run_id)

    save_run_config(run_id, cfg)  # so replacements reuse the same settings
    prov = provision_instance(
        region=AWS_REGION, instance_type=args.instance_type,
        image_id=os.environ.get("CHRONONET_AMI"), subnet_id=args.subnet_id,
        key_name=os.environ.get("CHRONONET_KEY_NAME"), security_group_ids=sgs or None,
        user_data=user_data, tags={"Project": "chrononet", "RunId": run_id, "Role": "workload"},
        logger=logger, allow_real=allow,
    )
    iid = prov["instance_id"]
    market = "spot" if prov["market"] == "spot" else "ondemand"
    DynamoDBClient().update_vm_state(
        iid, run_id=run_id, status="launching", instance_type=args.instance_type,
        market=market, launched_at=datetime.now(timezone.utc).isoformat(),
    )
    print(f"\nLAUNCHED  instance={iid}  type={args.instance_type}  market={market}  run_id={run_id}")
    print("The workload starts after the bootstrap finishes (~1-2 min). Watch it:")
    print(f"  aws s3 ls s3://{S3_CHECKPOINT_BUCKET}/{S3_CHECKPOINT_PREFIX}/{run_id}/ --region {AWS_REGION}")
    print(f"  aws ec2 get-console-output --instance-id {iid} --latest --output text --region {AWS_REGION}")
    print(f"Trigger a migration:\n  python -m orchestration.migrate --provision real event-json "
          f"'{{\"run_id\":\"{run_id}\",\"vm_id\":\"{iid}\",\"risk_percent\":96,"
          f"\"threshold_exceeded\":true,\"timestamp\":\"{datetime.now(timezone.utc).isoformat()}\"}}'")
    print(f"Stop everything:\n  aws ec2 terminate-instances --instance-ids {iid} --region {AWS_REGION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
