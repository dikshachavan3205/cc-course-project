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
"""

import json
import os
from datetime import datetime, timezone

import boto3

from config import LOCAL_CHECKPOINT_DIR, LOCAL_CHECKPOINT_FILE, RUN_ID, VM_ID
from shared.constants import S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX, AWS_REGION

_s3_client = boto3.client("s3", region_name=AWS_REGION)


def _ensure_checkpoint_dir():
    os.makedirs(LOCAL_CHECKPOINT_DIR, exist_ok=True)


def _s3_key_for(run_id: str, timestamp: str) -> str:
    safe_timestamp = timestamp.replace(":", "-")
    return f"{S3_CHECKPOINT_PREFIX}/{run_id}/{safe_timestamp}.json"


def save_checkpoint(last_processed_index: int) -> dict:
    """
    Writes progress locally AND uploads it to S3.
    Returns the checkpoint dict that was written.
    """
    _ensure_checkpoint_dir()

    checkpoint = {
        "run_id": RUN_ID,
        "vm_id": VM_ID,
        "last_processed_index": last_processed_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    checkpoint_json = json.dumps(checkpoint, indent=2)

    # ── Local write (atomic) ──
    tmp_path = LOCAL_CHECKPOINT_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(checkpoint_json)
    os.replace(tmp_path, LOCAL_CHECKPOINT_FILE)

    # ── S3 upload ──
    key = _s3_key_for(checkpoint["run_id"], checkpoint["timestamp"])
    try:
        _s3_client.put_object(
            Bucket=S3_CHECKPOINT_BUCKET,
            Key=key,
            Body=checkpoint_json,
            ContentType="application/json",
        )
    except Exception as e:
        print(f"[checkpoint_manager] WARNING: S3 upload failed: {e}")

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

    response = _s3_client.list_objects_v2(
        Bucket=S3_CHECKPOINT_BUCKET,
        Prefix=prefix,
    )

    objects = response.get("Contents", [])
    if not objects:
        return None

    latest_key = max(objects, key=lambda obj: obj["Key"])["Key"]

    obj = _s3_client.get_object(Bucket=S3_CHECKPOINT_BUCKET, Key=latest_key)
    body = obj["Body"].read().decode("utf-8")
    return json.loads(body)