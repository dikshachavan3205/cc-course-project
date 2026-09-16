"""Phase 8 orchestrator CLI.

Drives recovery_flow.run_migration() through its strict 7-step sequence.

Usage:
  python -m orchestration.migrate test-migration              # full end-to-end sim
  python -m orchestration.migrate test-migration --seed-index 37
  python -m orchestration.migrate event-json '{...}'          # custom event
  python -m orchestration.migrate simulate-detect             # event from imds_watcher

The default test mode is entirely SIMULATED for EC2 (provision + terminate)
but uses REAL S3 (chrononet-checkpoints) and REAL DynamoDB
(chrononet-vm-state / chrononet-migrations), then cleans up its own rows so
the shared tables stay clean (opt out with --keep-aws).

Result JSON is printed to STDOUT; the step log goes to STDERR.
"""

import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import boto3  # noqa: E402

from app.checkpoint_manager import (  # noqa: E402
    LOCAL_CHECKPOINT_FILE,
    load_checkpoint,
    save_checkpoint,
)
from data_backend.aws.dynamodb_client import DynamoDBClient  # noqa: E402
from orchestration.recovery_flow import run_migration  # noqa: E402
from shared.constants import (  # noqa: E402
    AWS_REGION, S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX,
)


def _default_event(run_id: str, vm_id: str, risk_percent: int = 96) -> dict:
    from monitoring.imds_watcher import build_high_risk_event
    return build_high_risk_event(run_id=run_id, vm_id=vm_id, risk_percent=risk_percent)


def _cleanup_aws(run_id: str, vm_ids: list[str]) -> None:
    """Delete DynamoDB rows + S3 checkpoints created by this test run."""
    db = DynamoDBClient()
    for vid in vm_ids:
        try:
            db.delete_vm_state(vid)
        except Exception as e:  # noqa: BLE001
            print(f"[cleanup] delete_vm_state({vid}) skipped: {type(e).__name__}: {e}")
    try:
        for row in db.list_migrations(run_id=run_id):
            db.delete_migration(run_id=row["run_id"], timestamp=row["timestamp"])
    except Exception as e:  # noqa: BLE001
        print(f"[cleanup] delete_migration({run_id}) skipped: {type(e).__name__}: {e}")

    s3 = boto3.client("s3", region_name=AWS_REGION)
    prefix = f"{S3_CHECKPOINT_PREFIX}/{run_id}/"
    deleted = 0
    while True:
        resp = s3.list_objects_v2(Bucket=S3_CHECKPOINT_BUCKET, Prefix=prefix)
        keys = [o["Key"] for o in resp.get("Contents", [])]
        if not keys:
            break
        s3.delete_objects(
            Bucket=S3_CHECKPOINT_BUCKET,
            Delete={"Objects": [{"Key": k} for k in keys]},
        )
        deleted += len(keys)
        if not resp.get("IsTruncated"):
            break
    if deleted:
        print(f"[cleanup] Deleted {deleted} S3 object(s) under {prefix}")


def cmd_test_migration(args) -> int:
    run_id = args.run_id or "run-orchestrator-test"
    vm_id = args.from_vm or f"vm-{run_id}-src"

    prior_local = load_checkpoint()  # restore this after the test

    # Seed a checkpoint so the workload demonstrably resumes from index > 0.
    if args.seed_index is not None:
        save_checkpoint(args.seed_index, run_id=run_id, vm_id=vm_id)
        print(f"[seed] Checkpoint saved with last_processed_index={args.seed_index}")

    event = _default_event(run_id=run_id, vm_id=vm_id, risk_percent=args.risk)
    print("[event] " + json.dumps(event))

    result = run_migration(
        event,
        provision_mode="simulate",
        allow_real_ec2=(os.environ.get("CHRONONET_ALLOW_REAL_EC2", "").lower() == "true"),
        dry_run=args.dry_run,
    )

    print("[result] " + json.dumps(result, indent=2, default=str))

    ok = (
        result["status"] == "completed"
        and result["health_ok"]
        and (result["downtime_seconds"] or 0) >= 0.0
    )
    print(f"[test-migration] {'PASS' if ok else 'FAIL'} (status={result['status']})")

    if not args.keep_aws:
        _cleanup_aws(run_id, [vm_id, result.get("to_vm_id")])

    # Restore the pre-test local checkpoint (test hygiene, mirrors smoke_test).
    if prior_local is not None:
        with open(LOCAL_CHECKPOINT_FILE, "w") as f:
            json.dump(prior_local, f)
        print("[cleanup] Restored pre-test local checkpoint")

    return 0 if ok else 1


def cmd_event(args) -> int:
    event = json.loads(args.event_json)
    result = run_migration(
        event,
        provision_mode=args.provision,
        allow_real_ec2=(os.environ.get("CHRONONET_ALLOW_REAL_EC2", "").lower() == "true"),
        dry_run=args.dry_run,
    )
    print("[result] " + json.dumps(result, indent=2, default=str))
    print(f"[event-json] {'PASS' if result['status'].startswith('completed') or result['status'] == 'noop' else 'FAIL'}")
    return 0 if result["status"].startswith("completed") or result["status"] == "noop" else 1


def cmd_simulate_detect(args) -> int:
    """Emit one simulated IMDS notice, then run the migration it triggers."""
    print("[detect] Running: python -m monitoring.imds_watcher --simulate --once")
    proc = subprocess.run(
        [sys.executable, "-m", "monitoring.imds_watcher", "--simulate", "--once"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if proc.returncode != 0:
        print("[detect] imds_watcher failed:\n", proc.stderr)
        return 1
    event = json.loads(proc.stdout.strip())
    print("[detect] Event parsed: " + json.dumps(event))
    result = run_migration(
        event,
        provision_mode=args.provision,
        allow_real_ec2=(os.environ.get("CHRONONET_ALLOW_REAL_EC2", "").lower() == "true"),
        dry_run=args.dry_run,
    )
    print("[result] " + json.dumps(result, indent=2, default=str))
    return 0 if result["status"].startswith("completed") or result["status"] == "noop" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ChronoNet migration orchestrator")
    parser.add_argument("--provision", choices=["simulate", "real"],
                        default="simulate", help="EC2 provisioning mode (default: simulate)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip real DynamoDB writes (log a warning per skipped call).")
    parser.add_argument("--keep-aws", action="store_true",
                        help="Keep the DynamoDB/S3 records this test created.")

    sub = parser.add_subparsers(dest="command", required=True)

    test = sub.add_parser("test-migration", help="Full end-to-end simulated migration")
    test.set_defaults(handler=cmd_test_migration)
    test.add_argument("--run-id", help="Run id (default: run-orchestrator-test)")
    test.add_argument("--from-vm", help="Source VM id (default: vm-{run}--src)")
    test.add_argument("--seed-index", type=int, default=37,
                      help="Checkpoint index to seed before migrating (default: 37)")
    test.add_argument("--risk", type=int, default=96, help="risk_percent for the event (0-100)")

    ev = sub.add_parser("event-json", help="Trigger a migration from a raw event dict")
    ev.set_defaults(handler=cmd_event)
    ev.add_argument("event_json",
                    help='JSON: {"run_id":..., "vm_id":..., "risk_percent":96, "timestamp":...}')

    det = sub.add_parser("simulate-detect",
                         help="Emit a simulated IMDS notice, then run the migration it triggers")
    det.set_defaults(handler=cmd_simulate_detect)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())