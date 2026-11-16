"""Sample-artifact manager: keeps the visible sample data (generator script +
cumulative output log) synced between this instance's disk and the run's S3
checkpoint folder, across migrations.

On boot, restore() pulls the existing artifacts down from S3 so the log
visibly CONTINUES on the replacement instance. At every checkpoint cycle,
record() runs the generator, appends its output line locally, and re-uploads
both files to s3://<bucket>/checkpoints/<run_id>/sample_data/.

All failures are non-fatal (logged) so the demo artifact can never break the
workload itself. Python 3.9-safe.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone

import boto3

try:
    from config import RUN_ID, VM_ID
except ModuleNotFoundError:
    from app.config import RUN_ID, VM_ID

from shared.constants import AWS_REGION, S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX

APP_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATOR = os.path.join(APP_DIR, "sample_data_generator.py")
SAMPLE_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "sample_data"))
LOG_FILE = os.path.join(SAMPLE_DIR, "sample_output.log")

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=AWS_REGION)
    return _s3


def _prefix(run_id: str) -> str:
    return f"{S3_CHECKPOINT_PREFIX}/{run_id}/sample_data"


def restore(run_id: str | None = None) -> None:
    """On boot: fetch the run's existing sample artifacts from S3 (if any)."""
    run_id = run_id or RUN_ID
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    for name, dest in (("sample_output.log", LOG_FILE),
                       ("sample_data_generator.py", GENERATOR)):
        try:
            _client().download_file(S3_CHECKPOINT_BUCKET, f"{_prefix(run_id)}/{name}", dest)
            print(f"[sample] restored {name} <- s3://{S3_CHECKPOINT_BUCKET}/{_prefix(run_id)}/{name}",
                  flush=True)
        except Exception:
            pass  # first instance of the run has no artifact yet - start fresh
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write(f"# ChronoNet sample output log - created by {VM_ID} at "
                    f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        print(f"[sample] no prior artifact in S3 - new log started by {VM_ID}", flush=True)


def record(step_index: int, checksum: str, run_id: str | None = None,
           vm_id: str | None = None) -> None:
    """Checkpoint cycle: run the generator, append its line, upload artifacts."""
    run_id = run_id or RUN_ID
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    try:
        out = subprocess.run([sys.executable, GENERATOR, str(step_index), checksum],
                             capture_output=True, text=True, timeout=20)
        line = (out.stdout or out.stderr).strip()
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        for name, src in (("sample_output.log", LOG_FILE),
                          ("sample_data_generator.py", GENERATOR)):
            _client().upload_file(src, S3_CHECKPOINT_BUCKET, f"{_prefix(run_id)}/{name}")
        # web page files travel with the run too (served by app/web_server.py)
        site_dir = os.path.join(SAMPLE_DIR, "site")
        for name in ("index.html", "style.css"):
            src = os.path.join(site_dir, name)
            if os.path.exists(src):
                _client().upload_file(src, S3_CHECKPOINT_BUCKET, f"{_prefix(run_id)}/site/{name}")
        print(f"[sample] log + script -> s3://{S3_CHECKPOINT_BUCKET}/{_prefix(run_id)}/ "
              f"({line[:60]}...)", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[sample] WARNING record failed: {type(e).__name__}: {e}", flush=True)


def tail(n: int = 1) -> list:
    try:
        with open(LOG_FILE) as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        return lines[-n:]
    except Exception:  # noqa: BLE001
        return []


def line_count() -> int:
    try:
        with open(LOG_FILE) as f:
            return sum(1 for _ in f)
    except Exception:  # noqa: BLE001
        return 0
