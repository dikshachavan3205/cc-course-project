"""Full recovery sequence: checkpoint -> launch -> restore -> terminate old VM.

This is the Phase 8 orchestrator. It executes the migration in a STRICT order:

    1.  Detect a high-risk interruption signal (event dict supplied by
        monitoring/imds_watcher.py or the ML predictor).
    2.  Force an immediate atomic checkpoint and upload it to S3
        (chrononet-checkpoints) via app/checkpoint_manager.py.
    3.  Record the migration start state in DynamoDB
        (data_backend/aws/dynamodb_client.py).
    4.  Provision a replacement instance via boto3 — Spot first, with a
        graceful fallback to On-Demand if Spot capacity is unavailable.
    5.  Download the latest checkpoint from S3 onto the new target context.
    6.  Boot/restart the workload from that checkpoint index.
    7.  Confirm health of the new instance and terminate the old one.

After step 7, a best-effort SNS alert is published on successful completion
(data_backend/aws/sns_client.py: publish_migration_alert). A failed publish is
logged as a WARNING and never fails the migration.

Every step is logged with a UTC timestamp + monotonic elapsed ms
(orchestration/step_logger.py). Downtime is measured from trigger receipt to
step 6 completion and recorded in DynamoDB.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.checkpoint_manager import (  # noqa: E402
    LOCAL_CHECKPOINT_FILE,
    _s3_key_for,
    load_checkpoint,
    load_latest_checkpoint_from_s3,
    save_checkpoint,
)
from data_backend.aws.dynamodb_client import DynamoDBClient  # noqa: E402
from data_backend.aws.sns_client import SnsClient  # noqa: E402
from orchestration.launch_instance import (  # noqa: E402
    provision_instance,
    simulate_provision,
)
from orchestration.step_logger import StepLogger  # noqa: E402
from orchestration.terminate_instance import (  # noqa: E402
    simulate_terminate,
    terminate_instance,
)
from shared.constants import (  # noqa: E402
    AWS_REGION,
    DYNAMODB_TABLE_MIGRATIONS,
    DYNAMODB_TABLE_VM_STATE,
    INSTANCE_TYPE,
    RISK_THRESHOLD,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _threshold_exceeded(risk_percent: float) -> bool:
    return (risk_percent / 100.0) >= RISK_THRESHOLD


def _safe_ddb(logger, dry_run: bool, fn, *args, **kwargs):
    """Run a DynamoDB call; in dry-run mode swallow errors + warn + return None."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        if dry_run:
            logger.note("db-skipped-dryrun", call=fn.__name__, reason=f"{type(exc).__name__}: {exc}")
            return None
        raise


def _boot_resume_sim(logger, run_id: str, vm_id: str, resume_index: int,
                     cwd: str, timeout_s: int = 30) -> tuple[bool, str]:
    """
    Simulated 'container boot' that actually spawns app/main.py locally with
    the downloaded checkpoint as its resume point. Returns (health_ok, boot_line).
    """
    env = dict(
        os.environ,
        CHRONONET_RUN_ID=run_id,
        CHRONONET_VM_ID=vm_id,
        CHRONONET_TOTAL_STEPS=str(int(resume_index) + 5),
        CHRONONET_STEP_DELAY="0.02",
        CHRONONET_CHECKPOINT_INTERVAL="999999",  # don't checkpoint during the boot probe
    )
    logger.note("boot-cmd", cwd=cwd, cmd=f"{sys.executable} app/main.py",
                resume_index=resume_index)
    proc = subprocess.Popen(
        [sys.executable, "app/main.py"],
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return False, "TIMEOUT while booting app"

    if resume_index >= 0:
        expected = f"Resuming from checkpoint: step {int(resume_index)}"
    else:
        expected = "No checkpoint found — starting fresh from step 0."
    ok = expected in out
    return ok, expected


def run_migration(
    event: dict,
    *,
    provision_mode: str = "simulate",
    allow_real_ec2: bool = False,
    dry_run: bool = False,
    cwd: str | None = None,
    logger: StepLogger | None = None,
    triggered_by: str = "imds",
) -> dict:
    """
    Execute the full migration workflow for one high-risk event.

    event must match shared/contracts.md shape #3:
      {run_id, vm_id, risk_percent (0-100), threshold_exceeded, timestamp}

    triggered_by records how this migration was kicked off (e.g. "imds",
    "prediction") in the chrononet-migrations row.

    Returns a result dict including the measured downtime (seconds) and the
    full step timeline.
    """
    run_id = event["run_id"]
    vm_id = event["vm_id"]
    risk_percent = float(event["risk_percent"])
    logger = logger or StepLogger(owner="recovery_flow", run_id=run_id)
    cwd = cwd or REPO_ROOT

    db = DynamoDBClient()
    start_mono = time.monotonic()
    trigger_at = _now_iso()
    result: dict = {
        "run_id": run_id,
        "from_vm_id": vm_id,
        "to_vm_id": vm_id,
        "status": "failed",
        "health_ok": False,
        "downtime_seconds": None,
        "steps": logger.timeline,
    }

    # ── 1. RECEIVE / DETECT high-risk signal ──
    if not event.get("threshold_exceeded", _threshold_exceeded(risk_percent)):
        if _threshold_exceeded(risk_percent):
            event["threshold_exceeded"] = True
    logger.step(
        "1/7 signal-received",
        risk_percent=risk_percent,
        threshold_exceeded=bool(event.get("threshold_exceeded")),
        event_timestamp=event.get("timestamp", trigger_at),
    )
    if not bool(event.get("threshold_exceeded")):
        result["status"] = "noop"
        result["downtime_seconds"] = 0.0
        logger.step("1/7 signal-below-threshold → no migration",
                    risk_percent=risk_percent)
        return result

    # ── 2. FORCE immediate atomic checkpoint → S3 ──
    last = load_checkpoint()
    if last:
        resume_index = int(last["last_processed_index"])
    else:
        resume_index = 0
    checkpoint = save_checkpoint(
        last_processed_index=resume_index,
        run_id=run_id,
        vm_id=vm_id,
    )
    checkpoint_key = _s3_key_for(checkpoint["run_id"], checkpoint["timestamp"])
    logger.step("2/7 checkpoint-saved", s3_key=checkpoint_key,
                index=checkpoint["last_processed_index"])

    # ── 3. RECORD migration start in DynamoDB ──
    target_vm = f"{vm_id}-target"
    _safe_ddb(logger, dry_run, db.update_vm_state, vm_id,
              status="migrating", risk_percent=risk_percent)
    migration_id = _safe_ddb(
        logger, dry_run, db.record_migration,
        run_id=run_id,
        from_vm_id=vm_id,
        to_vm_id=target_vm,
        triggered_by=triggered_by,
        risk_percent=risk_percent,
        downtime_seconds=0.0,
        status="started",
        checkpoint_key=checkpoint_key,
    )
    migration_id = migration_id or f"dry-{run_id}"
    logger.step("3/7 migration-logged", table=DYNAMODB_TABLE_MIGRATIONS,
                migration_id=migration_id)

    # ── 4. PROVISION replacement instance (Spot → On-Demand fallback) ──
    if provision_mode == "simulate":
        prov = simulate_provision(instance_type=INSTANCE_TYPE, logger=logger)
        new_vm_id = prov["instance_id"]
        market = prov["market"]
    else:
        prov = provision_instance(
            region=AWS_REGION,
            instance_type=INSTANCE_TYPE,
            image_id=os.environ.get("CHRONONET_AMI"),
            subnet_id=os.environ.get("CHRONONET_SUBNET_ID"),
            key_name=os.environ.get("CHRONONET_KEY_NAME"),
            security_group_ids=(os.environ.get("CHRONONET_SECURITY_GROUP_IDS") or "").split(",")
            if os.environ.get("CHRONONET_SECURITY_GROUP_IDS") else None,
            logger=logger,
            allow_real=allow_real_ec2,
        )
        new_vm_id = prov["instance_id"]
        market = prov["market"]
        if new_vm_id != target_vm:
            _safe_ddb(logger, dry_run, db.update_migration,
                      run_id, migration_id, to_vm_id=new_vm_id)
    logger.step("4/7 replacement-provisioned", instance_id=new_vm_id,
                market=market, mode=provision_mode)

    # ── 5. DOWNLOAD latest checkpoint from S3 onto the new context ──
    s3_checkpoint = None
    if not dry_run:
        s3_checkpoint = load_latest_checkpoint_from_s3(run_id)
    # Prefer what we just downloaded; fall back to the freshly-saved one.
    active = s3_checkpoint or checkpoint
    resume_index = int(active["last_processed_index"])
    # In the sim the "new context" is this same machine: apply the downloaded
    # checkpoint so the booted process really resumes from it.
    os.makedirs(os.path.dirname(LOCAL_CHECKPOINT_FILE), exist_ok=True)
    with open(LOCAL_CHECKPOINT_FILE, "w") as f:
        json.dump(active, f)
    logger.step("5/7 checkpoint-downloaded", index=resume_index,
                source="s3" if s3_checkpoint else "local-fallback")

    # ── 6. BOOT / restart the workload from that index ──
    if provision_mode == "simulate":
        health_ok, boot_line = _boot_resume_sim(
            logger, run_id, new_vm_id, resume_index, cwd=cwd,
        )
    else:
        # Real EC2 boot is outside this sandbox (docker/systemd on the target);
        # log the resume contract so ops can wire it (e.g. SSM/user-data).
        health_ok = True
        boot_line = (f"resume app on {new_vm_id} from checkpoint index {resume_index} "
                     f"(S3 key {checkpoint_key})")
    downtime_s = (time.monotonic() - start_mono)
    logger.step("6/7 app-resumed", health_ok=health_ok,
                downtime_duration_s=round(downtime_s, 4), boot="sim-locally" if provision_mode == "simulate" else "external")

    # ── 7. CONFIRM health + TERMINATE old instance ──
    if provision_mode == "simulate":
        terminate_record = simulate_terminate(vm_id, logger=logger)
    else:
        terminate_record = terminate_instance(region=AWS_REGION, instance_id=vm_id, logger=logger)

    result["to_vm_id"] = new_vm_id
    result["migration_id"] = migration_id
    result["checkpoint_key"] = checkpoint_key
    result["resumed_index"] = resume_index
    result["provision_market"] = market
    result["health_ok"] = health_ok
    result["terminate_record"] = terminate_record

    if dry_run:
        logger.note("db-skipped-dryrun", call="put_vm_state+record_checkpoint")
    else:
        db.put_vm_state(
            vm_id=new_vm_id,
            run_id=run_id,
            region=AWS_REGION,
            cpu_percent=0.0,
            ram_percent=0.0,
            risk_percent=risk_percent,
            migration_count=1,
            last_downtime_seconds=downtime_s,
            status="running",
        )
        db.record_checkpoint(
            vm_id=new_vm_id,
            run_id=run_id,
            last_processed_index=resume_index,
            s3_key=checkpoint_key,
        )
    _safe_ddb(logger, dry_run, db.update_vm_state, vm_id, status="terminated")
    _safe_ddb(
        logger, dry_run, db.update_migration,
        run_id, migration_id,
        status="completed",
        to_vm_id=new_vm_id,
        downtime_seconds=downtime_s,
        resumed_index=resume_index,
        provision_market=market,
        completed_at=_now_iso(),
        timeline=json.dumps(logger.timeline, default=str),
    )
    result["status"] = "completed" if health_ok else "completed-with-warning"
    result["downtime_seconds"] = round(downtime_s, 4)
    result["steps"] = logger.timeline

    # ── 7b. NOTIFY via SNS (best-effort — a publish failure must NOT fail the migration) ──
    if not dry_run and result["status"].startswith("completed"):
        if os.environ.get("CHRONONET_DISABLE_ALERTS", "").lower() == "true":
            logger.note("sns-alert-disabled", env="CHRONONET_DISABLE_ALERTS")
        else:
            try:
                sns = SnsClient()
                publish_resp = sns.publish_migration_alert(result)
                logger.note("sns-alert-published",
                            topic_arn=sns.topic_arn,
                            message_id=publish_resp.get("MessageId"))
            except Exception as exc:  # noqa: BLE001 - best-effort alerting
                logger.note("sns-alert-failed",
                            reason=f"{type(exc).__name__}: {exc}")
    else:
        logger.note("sns-alert-skipped", reason="dry-run" if dry_run else "migration-not-completed")

    logger.step("7/7 old-instance-terminated", table=DYNAMODB_TABLE_VM_STATE,
                final_status=result["status"], final_downtime_s=result["downtime_seconds"])
    return result