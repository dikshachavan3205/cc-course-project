"""App-level config: paths, checkpoint interval, etc."""
"""
App-level configuration for the demo workload.
Pulls shared constants (checkpoint interval, S3 bucket names, etc.)
from shared/constants.py so the whole team stays in sync.
"""

import os
import sys

# ── Make `shared/` importable even though app/ is a sibling folder ──
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import CHECKPOINT_INTERVAL_SECONDS  # noqa: E402

# ── Local paths ──
LOCAL_CHECKPOINT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints")
LOCAL_CHECKPOINT_FILE = os.path.join(LOCAL_CHECKPOINT_DIR, "checkpoint.json")

# ── Run identity ──
RUN_ID = os.environ.get("CHRONONET_RUN_ID", "run-local-dev")
VM_ID = os.environ.get("CHRONONET_VM_ID", "vm-local-dev")

# ── Workload simulation settings ──
TOTAL_STEPS = int(os.environ.get("CHRONONET_TOTAL_STEPS", 100))
WORK_STEP_DELAY_SECONDS = float(os.environ.get("CHRONONET_STEP_DELAY", 0.1))

CHECKPOINT_INTERVAL_SECONDS = int(os.environ.get(
    "CHRONONET_CHECKPOINT_INTERVAL", CHECKPOINT_INTERVAL_SECONDS
))