"""
Save/load the workload's progress to a local JSON file.
Follows the checkpoint JSON shape agreed in shared/contracts.md.
"""

import json
import os
from datetime import datetime, timezone

from config import LOCAL_CHECKPOINT_DIR, LOCAL_CHECKPOINT_FILE, RUN_ID, VM_ID


def _ensure_checkpoint_dir():
    os.makedirs(LOCAL_CHECKPOINT_DIR, exist_ok=True)


def save_checkpoint(last_processed_index: int) -> dict:
    _ensure_checkpoint_dir()

    checkpoint = {
        "run_id": RUN_ID,
        "vm_id": VM_ID,
        "last_processed_index": last_processed_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    tmp_path = LOCAL_CHECKPOINT_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(checkpoint, f, indent=2)
    os.replace(tmp_path, LOCAL_CHECKPOINT_FILE)

    return checkpoint


def load_checkpoint() -> dict | None:
    if not os.path.exists(LOCAL_CHECKPOINT_FILE):
        return None

    with open(LOCAL_CHECKPOINT_FILE, "r") as f:
        return json.load(f)