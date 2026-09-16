"""
Save/load the workload's progress — locally AND to S3.

Local file = fast, always-available working copy for this instance.
S3 = durable copy that survives even if this instance is terminated;
     a NEW instance reads from S3 (not local disk) during recovery.

Follows the checkpoint JSON shape agreed in shared/contracts.md:
{
  "run_id": "string",
  "vm_id": "string",
  "last_processed_index": 0,
  "timestamp": "ISO8601"
}

S3 key pattern: checkpoints/{run_id}/{timestamp}.json
  - Keyed by run_id (not vm_id) since run_id stays constant across
    instance migrations — this is how a new instance finds "all
    checkpoints belonging to this job" after the old VM is gone.

CLI:
  python -m app.checkpoint_manager --test-upload
    Saves one checkpoint (locally + S3) and verifies it exists in the
    S3 bucket by listing + reading it back.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

import boto3

# config.py resolves to app/config.py whether we're run as `-m app.checkpoint_manager`
# (repo root on sys.path) or as `python app/checkpoint_manager.py` (app/ on sys.path).
try:
    from config import LOCAL_CHECKPOINT_DIR, LOCAL_CHECKPOINT_FILE, RUN_ID, VM_ID
except ModuleNotFoundError:
    from app.config import LOCAL_CHECKPOINT_DIR, LOCAL_CHECKPOINT_FILE, RUN_ID, VM_ID

from shared.constants import S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX, AWS_REGION

# Ensure WARNING/ERROR messages are ALWAYS visible, even when this module is
# imported by a caller that never configures logging (e.g. app/main.py).
logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("chrononet.checkpoint_manager")

# Lazy: not created at import time so a machine with missing/broken AWS config
# can still run the workload locally (and only the upload hits the failure path).
_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=AWS_REGION)
    return _s3_client


def _ensure_checkpoint_dir():
    os.makedirs(LOCAL_CHECKPOINT_DIR, exist_ok=True)


def _s3_key_for(run_id: str, timestamp: str) -> str:
    # "#" is invalid inside S3 keys (would break console/ARN tooling); ":" too.
    safe_timestamp = timestamp.replace(":", "-").replace("#", "-")
    return f"{S3_CHECKPOINT_PREFIX}/{run_id}/{safe_timestamp}.json"


def save_checkpoint(
    last_processed_index: int,
    run_id: str | None = None,
    vm_id: str | None = None,
) -> dict:
    """
    Writes progress locally AND (best-effort) uploads it to S3.
    Returns the checkpoint dict that was written.

    The LOCAL write always happens first, so even if the S3 upload fails
    (no credentials, no network, denied access...) the progress is never
    lost — the failure is only logged as a WARNING.

    run_id/vm_id default to the env-configured identities (config.RUN_ID /
    config.VM_ID); pass them explicitly when the checkpoint must carry a
    different identity (e.g. the orchestration hub saving for a migrated VM).
    """
    _ensure_checkpoint_dir()

    checkpoint = {
        "run_id": run_id or RUN_ID,
        "vm_id": vm_id or VM_ID,
        "last_processed_index": last_processed_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    checkpoint_json = json.dumps(checkpoint, indent=2)

    # ── Local write (atomic) — ALWAYS happens, even if S3 fails ──
    tmp_path = LOCAL_CHECKPOINT_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(checkpoint_json)
    os.replace(tmp_path, LOCAL_CHECKPOINT_FILE)

    # ── S3 upload (best-effort) ──
    key = _s3_key_for(checkpoint["run_id"], checkpoint["timestamp"])
    try:
        _get_s3_client().put_object(
            Bucket=S3_CHECKPOINT_BUCKET,
            Key=key,
            Body=checkpoint_json,
            ContentType="application/json",
        )
        logger.info("Checkpoint uploaded -> s3://%s/%s", S3_CHECKPOINT_BUCKET, key)
    except Exception as e:
        logger.warning(
            "S3 upload failed for key 's3://%s/%s' (local checkpoint was still "
            "saved to %s): %s: %s",
            S3_CHECKPOINT_BUCKET, key, LOCAL_CHECKPOINT_FILE, type(e).__name__, e,
        )

    return checkpoint


def load_checkpoint() -> dict | None:
    """
    Reads the LOCAL checkpoint file if it exists (fast path — used when
    an instance is resuming its own prior run on the same machine).
    """
    if not os.path.exists(LOCAL_CHECKPOINT_FILE):
        return None

    with open(LOCAL_CHECKPOINT_FILE, "r") as f:
        return json.load(f)


def load_latest_checkpoint_from_s3(run_id: str) -> dict | None:
    """
    Finds and returns the MOST RECENT checkpoint for a given run_id from S3.
    A NEW instance (after migration) has no local checkpoint of its own,
    so it calls this instead to pull the last known state from S3.
    """
    prefix = f"{S3_CHECKPOINT_PREFIX}/{run_id}/"

    response = _get_s3_client().list_objects_v2(
        Bucket=S3_CHECKPOINT_BUCKET,
        Prefix=prefix,
    )

    objects = response.get("Contents", [])
    if not objects:
        return None

    latest_key = max(objects, key=lambda obj: obj["Key"])["Key"]

    obj = _get_s3_client().get_object(Bucket=S3_CHECKPOINT_BUCKET, Key=latest_key)
    body = obj["Body"].read().decode("utf-8")
    return json.loads(body)


def test_upload(last_processed_index: int = 0) -> None:
    """
    CLI helper: forces one checkpoint save, then lists + reads the object back
    from S3 to prove it actually landed in the checkpoint bucket.
    Exits non-zero if the object cannot be confirmed.
    """
    checkpoint = save_checkpoint(last_processed_index=last_processed_index)
    key = _s3_key_for(checkpoint["run_id"], checkpoint["timestamp"])

    print(f"[test-upload] Saved checkpoint {key}")
    print(f"[test-upload] Confirming object exists in s3://{S3_CHECKPOINT_BUCKET} ...")

    try:
        response = _get_s3_client().list_objects_v2(
            Bucket=S3_CHECKPOINT_BUCKET,
            Prefix=f"{S3_CHECKPOINT_PREFIX}/{checkpoint['run_id']}/",
        )
        objects = response.get("Contents", [])
    except Exception as e:
        logger.error("Could not list objects in s3://%s: %s: %s",
                     S3_CHECKPOINT_BUCKET, type(e).__name__, e)
        sys.exit(1)

    if not any(obj["Key"] == key for obj in objects):
        logger.error("Object '%s' was NOT found in s3://%s", key, S3_CHECKPOINT_BUCKET)
        sys.exit(1)

    try:
        obj = _get_s3_client().get_object(Bucket=S3_CHECKPOINT_BUCKET, Key=key)
        body = json.loads(obj["Body"].read().decode("utf-8"))
    except Exception as e:
        logger.error("Object '%s' listed but could not be read back: %s: %s",
                     key, type(e).__name__, e)
        sys.exit(1)

    if body == checkpoint:
        print(f"[test-upload] SUCCESS: {key} ({obj.get('ContentLength', '?')} bytes) "
              f"matches saved checkpoint for run_id={checkpoint['run_id']}.")
        sys.exit(0)
    else:
        logger.error("Object '%s' content does not match what was saved:\n"
                     f"expected={checkpoint}\nsaved={body}", key)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="checkpoint_manager utilities")
    parser.add_argument(
        "--test-upload",
        action="store_true",
        help="Force one checkpoint save and verify it landed in the S3 bucket.",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="last_processed_index to write in the test checkpoint (default: 0).",
    )
    args = parser.parse_args()

    # Make the INFO line in save_checkpoint visible during the CLI test.
    logger.setLevel(logging.INFO)

    if args.test_upload:
        test_upload(args.index)
    else:
        parser.print_help()