"""Hub monitor loop: real telemetry + live price features -> model -> auto-migrate.

  python -m monitoring.monitor_loop --run-id <run_id>                 # real migrations
  python -m monitoring.monitor_loop --run-id <run_id> --threshold 5   # demo: threshold just under live risk
  python -m monitoring.monitor_loop --run-id <run_id> --dry-run       # decide, never migrate

Each cycle: find the run's running instance (EC2 tags) -> read the agent's
telemetry from DynamoDB -> build live features -> predict_risk -> write
risk_percent to vm-state and a row to chrononet-predictions -> migrate when risk
stays >= threshold for N consecutive readings, or the agent reports an
interruption notice. A cooldown prevents back-to-back migrations.
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import boto3  # noqa: E402

from data_backend.aws.dynamodb_client import DynamoDBClient  # noqa: E402
from orchestration.recovery_flow import run_migration  # noqa: E402
from prediction.features import live_features  # noqa: E402
from prediction.predict import predict_risk  # noqa: E402
from shared.constants import (  # noqa: E402
    AWS_REGION, MIGRATION_COOLDOWN_SECONDS, RISK_CONSECUTIVE_READINGS, RISK_THRESHOLD,
)


class TriggerState:
    """N consecutive readings >= threshold, or an interruption notice, fires once; then cooldown."""

    def __init__(self, threshold: float, consecutive: int, cooldown_s: float):
        self.threshold, self.consecutive, self.cooldown_s = threshold, consecutive, cooldown_s
        self.count, self.cooldown_until = 0, 0.0

    def update(self, risk: float, notice: bool, now: float):
        if now < self.cooldown_until:
            self.count = 0
            return None
        reason = None
        if notice:
            reason = "imds"
        else:
            self.count = self.count + 1 if risk >= self.threshold else 0
            if self.count >= self.consecutive:
                reason = "prediction"
        if reason:
            self.count, self.cooldown_until = 0, now + self.cooldown_s
        return reason


def find_active(run_id: str, region: str):
    """(instance_id, instance_type) of the newest running instance tagged for this run."""
    resp = boto3.client("ec2", region_name=region).describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["chrononet"]},
        {"Name": "tag:RunId", "Values": [run_id]},
        {"Name": "instance-state-name", "Values": ["running"]}])
    insts = [i for r in resp["Reservations"] for i in r["Instances"]]
    if not insts:
        return None
    newest = max(insts, key=lambda i: i["LaunchTime"])
    return newest["InstanceId"], newest["InstanceType"]


def cycle(run_id, db, trig, threshold, mode, dry_run, region=AWS_REGION):
    active = find_active(run_id, region)
    if not active:
        print("[monitor] no running instance for this run yet ...")
        return
    iid, itype = active
    row = db.get_vm_state(iid) or {}
    if row.get("cpu_percent") is None:
        print(f"[monitor] {iid}: waiting for the instance agent's first telemetry ...")
        return
    feats = live_features(itype, row, region)
    risk = float(predict_risk(**feats))
    db.update_vm_state(iid, run_id=run_id, risk_percent=round(risk, 2))
    db.put_prediction(run_id, iid, risk, threshold_migrate=threshold, source="model", **{
        k: v for k, v in feats.items() if k != "instance_type"}, instance_type=itype)
    notice = bool(row.get("interruption_notice"))
    reason = trig.update(risk, notice, time.time())
    streak = trig.consecutive if reason == "prediction" else trig.count   # counter resets when it fires
    print(f"[monitor] {datetime.now(timezone.utc):%H:%M:%S} {iid} {itype} cpu={feats['cpu_percent']:.0f}% "
          f"ram={feats['ram_percent']:.0f}% risk={risk:.2f}% (threshold {threshold}%, "
          f"streak {streak}/{trig.consecutive}){' NOTICE' if notice else ''}")
    if not reason:
        return
    print(f"[monitor] >>> MIGRATE ({reason}) {iid}" + ("  [dry-run: not migrating]" if dry_run else ""))
    if dry_run:
        return
    event = {"run_id": run_id, "vm_id": iid, "risk_percent": round(max(risk, threshold), 2),
             "threshold_exceeded": True, "timestamp": datetime.now(timezone.utc).isoformat()}
    result = run_migration(event, provision_mode=mode, allow_real_ec2=(mode == "real"),
                           triggered_by=reason)
    print(f"[monitor] migration {result.get('status')}: {result.get('from_vm_id')} -> "
          f"{result.get('to_vm_id')} in {result.get('downtime_seconds')}s")


def main() -> int:
    ap = argparse.ArgumentParser(description="ChronoNet hub monitor loop")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--threshold", type=float, default=RISK_THRESHOLD * 100, help="percent")
    ap.add_argument("--consecutive", type=int, default=RISK_CONSECUTIVE_READINGS)
    ap.add_argument("--cooldown", type=float, default=MIGRATION_COOLDOWN_SECONDS)
    ap.add_argument("--provision", choices=["real", "simulate"], default="real")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    if a.provision == "real" and not a.dry_run and os.environ.get("CHRONONET_ALLOW_REAL_EC2", "").lower() != "true":
        print("Refusing real migrations: set $env:CHRONONET_ALLOW_REAL_EC2=\"true\" (or use --dry-run).")
        return 2
    db = DynamoDBClient()
    db.ensure_predictions_table()
    trig = TriggerState(a.threshold, a.consecutive, a.cooldown)
    print(f"[monitor] run={a.run_id} threshold={a.threshold}% x{a.consecutive} readings, "
          f"cooldown {a.cooldown}s, mode={a.provision}{' (dry-run)' if a.dry_run else ''}")
    while True:
        try:
            cycle(a.run_id, db, trig, a.threshold, a.provision, a.dry_run)
        except Exception as exc:  # noqa: BLE001 - keep monitoring
            print(f"[monitor] warning: {type(exc).__name__}: {exc}")
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
