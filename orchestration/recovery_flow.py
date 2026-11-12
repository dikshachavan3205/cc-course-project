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
    pick_replacement_pool,
    provision_instance,
    simulate_provision,
)
from orchestration.step_logger import StepLogger  # noqa: E402
from orchestration.user_data import build_user_data, load_run_config  # noqa: E402
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


def _wait_for_new_instance(db, logger, new_vm_id: str, min_index: int,
                           timeout_s: int = 300, poll_s: int = 3):
    """
    REAL mode step 6: the new instance's own workload registers itself in
    DynamoDB (status=running + resumed_index). Healthy = it reports running and
    resumed at or beyond the index we located (it restores the *latest* S3
    checkpoint on boot, which can be newer than the one the hub saw).
    Returns (healthy, description, resumed_index_or_None).
    """
    deadline = time.monotonic() + timeout_s
    last_note = 0.0
    while time.monotonic() < deadline:
        try:
            row = db.get_vm_state(new_vm_id) or {}
        except Exception as exc:  # noqa: BLE001 - transient DynamoDB error: keep polling
            row = {}
            logger.note("health-poll-error", reason=f"{type(exc).__name__}: {exc}")
        resumed = row.get("resumed_index")
        if row.get("status") == "running" and resumed is not None:
            resumed = int(resumed)
            if resumed >= min_index:
                return True, f"{new_vm_id} running, resumed at index {resumed}", resumed
        if time.monotonic() - last_note > 15:
            logger.note("waiting-for-new-instance", instance_id=new_vm_id,
                        status=row.get("status"), timeout_s=timeout_s)
            last_note = time.monotonic()
        time.sleep(poll_s)
    return False, f"{new_vm_id} did not report running within {timeout_s}s", None


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
    if provision_mode == "simulate":
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
    else:
        # REAL mode: the workload runs on another machine, so the hub cannot
        # snapshot it. The workload checkpoints to S3 every few seconds; use
        # the latest one (at most one interval stale) -- never the hub's local file.
        checkpoint = load_latest_checkpoint_from_s3(run_id)
        if checkpoint is None:
            logger.step("2/7 no-checkpoint-in-s3", run_id=run_id)
            result["status"] = "failed"
            result["error"] = "no checkpoint found in S3 for this run_id"
            return result
        resume_index = int(checkpoint["last_processed_index"])
        checkpoint_key = _s3_key_for(checkpoint["run_id"], checkpoint["timestamp"])
        logger.step("2/7 checkpoint-located", s3_key=checkpoint_key, index=resume_index,
                    source_vm=checkpoint.get("vm_id"))

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
        def _csv(*names):
            for n in names:
                if os.environ.get(n):
                    return [x.strip() for x in os.environ[n].split(",") if x.strip()]
            return []

        # Different AZ / instance type than the one being replaced (a reclaimed
        # Spot pool is the likeliest to be reclaimed again).
        new_subnet, new_type = pick_replacement_pool(
            region=AWS_REGION, old_instance_id=vm_id,
            subnet_ids=_csv("CHRONONET_SUBNET_IDS", "CHRONONET_SUBNET_ID"),
            instance_types=_csv("CHRONONET_INSTANCE_TYPES") or [INSTANCE_TYPE],
            logger=logger,
        )
        user_data = build_user_data(run_id=run_id, **load_run_config(run_id))
        prov = provision_instance(
            region=AWS_REGION,
            instance_type=new_type,
            image_id=os.environ.get("CHRONONET_AMI"),
            subnet_id=new_subnet,
            key_name=os.environ.get("CHRONONET_KEY_NAME"),
            security_group_ids=_csv("CHRONONET_SECURITY_GROUP_IDS") or None,
            user_data=user_data,
            tags={"Project": "chrononet", "RunId": run_id, "Role": "workload"},
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
    if provision_mode == "simulate":
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
    else:
        # REAL mode: the new instance restores itself from S3 on boot
        # (CHRONONET_RESTORE_FROM_S3=true in its bootstrap) - nothing to copy here.
        logger.step("5/7 checkpoint-handoff", index=resume_index, s3_key=checkpoint_key,
                    note="new instance restores latest checkpoint from S3 on boot")

    # ── 6. BOOT / restart the workload from that index ──
    if provision_mode == "simulate":
        health_ok, boot_line = _boot_resume_sim(
            logger, run_id, new_vm_id, resume_index, cwd=cwd,
        )
    else:
        health_ok, boot_line, actual_index = _wait_for_new_instance(
            db, logger, new_vm_id, resume_index,
            timeout_s=int(os.environ.get("CHRONONET_BOOT_TIMEOUT", "300")),
        )
        if actual_index is not None:
            resume_index = actual_index
    downtime_s = (time.monotonic() - start_mono)
    logger.step("6/7 app-resumed", health_ok=health_ok,
                downtime_duration_s=round(downtime_s, 4), boot="sim-locally" if provision_mode == "simulate" else "external")

    if provision_mode != "simulate" and not health_ok:
        # Never terminate the working instance for a replacement that never came up.
        logger.step("6/7 replacement-unhealthy: keeping old instance", new_vm_id=new_vm_id,
                    detail=boot_line)
        _safe_ddb(logger, dry_run, db.update_migration, run_id, migration_id,
                  status="failed", to_vm_id=new_vm_id, provision_market=market,
                  downtime_seconds=downtime_s)
        _safe_ddb(logger, dry_run, db.update_vm_state, vm_id, status="running")
        result.update(to_vm_id=new_vm_id, migration_id=migration_id,
                      checkpoint_key=checkpoint_key, provision_market=market,
                      status="failed", error=boot_line,
                      downtime_seconds=round(downtime_s, 4), steps=logger.timeline)
        return result

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
        if provision_mode == "simulate":
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
        else:
            # The real instance already wrote its own row (type, market,
            # resumed_index...). Update it - put_item would overwrite those.
            prev_row = _safe_ddb(logger, dry_run, db.get_vm_state, vm_id) or {}
            prev_count = int(prev_row.get("migration_count") or 0)
            db.update_vm_state(
                new_vm_id, run_id=run_id, status="running", risk_percent=risk_percent,
                migration_count=prev_count + 1, last_downtime_seconds=downtime_s,
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