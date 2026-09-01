"""Demo app entry point (the 'workload').
Processes items in chunks, checkpointing progress via checkpoint_manager.
"""
"""
Demo workload — stands in for "the real app" ChronoNet is protecting.
Run with: python app/main.py  (from the repo root)
"""

import signal
import sys
import time

from config import TOTAL_STEPS, WORK_STEP_DELAY_SECONDS, CHECKPOINT_INTERVAL_SECONDS
from checkpoint_manager import save_checkpoint, load_checkpoint

_shutdown_requested = False


def _handle_shutdown_signal(signum, frame):
    global _shutdown_requested
    print(f"\n[main] Received signal {signum} — will checkpoint and exit.")
    _shutdown_requested = True


def run_workload():
    checkpoint = load_checkpoint()
    if checkpoint:
        start_index = checkpoint["last_processed_index"]
        print(f"[main] Resuming from checkpoint: step {start_index} "
              f"(run_id={checkpoint['run_id']}, saved at {checkpoint['timestamp']})")
    else:
        start_index = 0
        print("[main] No checkpoint found — starting fresh from step 0.")

    last_checkpoint_time = time.time()

    for step in range(start_index, TOTAL_STEPS):
        time.sleep(WORK_STEP_DELAY_SECONDS)

        if step % 10 == 0:
            print(f"[main] Processing step {step}/{TOTAL_STEPS}")

        now = time.time()
        if now - last_checkpoint_time >= CHECKPOINT_INTERVAL_SECONDS:
            cp = save_checkpoint(last_processed_index=step)
            print(f"[main] Checkpoint saved: {cp}")
            last_checkpoint_time = now

        if _shutdown_requested:
            cp = save_checkpoint(last_processed_index=step)
            print(f"[main] Final checkpoint saved before shutdown: {cp}")
            sys.exit(0)

    save_checkpoint(last_processed_index=TOTAL_STEPS)
    print("[main] Workload complete. Final checkpoint saved.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    run_workload()