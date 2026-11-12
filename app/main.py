"""Demo workload — the job ChronoNet protects.

Deterministic and resumable: every step folds into a hash chain
(workload_state), checkpoints carry that state, and a fresh instance with no
local file restores the latest checkpoint from S3 (CHRONONET_RESTORE_FROM_S3).

Checkpoint semantics: last_processed_index = number of steps COMPLETED, i.e.
the next step to run. On SIGINT/SIGTERM (Spot notice, `docker stop`) it writes
one final checkpoint and exits.

Run: python app/main.py   (from the repo root or app/)
"""

import signal
import sys
import time

from config import (
    CHECKPOINT_INTERVAL_SECONDS,
    INSTANCE_TYPE,
    MARKET,
    RESTORE_FROM_S3,
    RUN_ID,
    TOTAL_STEPS,
    VM_ID,
    WORK_STEP_DELAY_SECONDS,
)
from checkpoint_manager import (
    _s3_key_for,
    load_checkpoint,
    load_latest_checkpoint_from_s3,
    save_checkpoint,
)
import instance_state
import workload_state

_shutdown_requested = False


def _handle_shutdown_signal(signum, frame):
    global _shutdown_requested
    print(f"\n[main] Received signal {signum} — will checkpoint and exit.")
    _shutdown_requested = True


def _pick_resume_point():
    """Newest of: local checkpoint, and (on a fresh instance) the latest S3 one."""
    local = load_checkpoint()
    remote = None
    if RESTORE_FROM_S3:
        try:
            remote = load_latest_checkpoint_from_s3(RUN_ID)
        except Exception as exc:  # noqa: BLE001
            print(f"[main] WARNING: could not read S3 checkpoint: {type(exc).__name__}: {exc}")
    candidates = [(c, src) for c, src in ((local, "local"), (remote, "s3")) if c]
    if not candidates:
        return None, None
    return max(candidates, key=lambda cs: int(cs[0]["last_processed_index"]))


def _record(cp: dict) -> None:
    instance_state.heartbeat(
        RUN_ID, VM_ID, cp["last_processed_index"],
        s3_key=_s3_key_for(cp["run_id"], cp["timestamp"]),
    )


def run_workload():
    checkpoint, source = _pick_resume_point()
    if checkpoint:
        start_index = int(checkpoint["last_processed_index"])
        state = checkpoint.get("state") or workload_state.state_at(start_index)
        print(f"[main] Resuming from checkpoint: step {start_index} "
              f"(run_id={checkpoint['run_id']}, from vm={checkpoint.get('vm_id')}, "
              f"source={source}, saved at {checkpoint['timestamp']})")
    else:
        start_index = 0
        state = workload_state.initial_state()
        print("[main] No checkpoint found — starting fresh from step 0.")

    instance_state.register(RUN_ID, VM_ID, start_index,
                            instance_type=INSTANCE_TYPE, market=MARKET)
    print(f"[main] vm={VM_ID} type={INSTANCE_TYPE} market={MARKET} "
          f"checksum@{start_index}={state['checksum'][:12]}")

    last_checkpoint_time = time.time()

    for step in range(start_index, TOTAL_STEPS):
        time.sleep(WORK_STEP_DELAY_SECONDS)
        state = workload_state.advance(state, step)
        done = step + 1

        if step % 10 == 0:
            print(f"[main] Processing step {step}/{TOTAL_STEPS}")

        if time.time() - last_checkpoint_time >= CHECKPOINT_INTERVAL_SECONDS:
            cp = save_checkpoint(done, state=state)
            _record(cp)
            print(f"[main] Checkpoint saved: index={done} checksum={state['checksum'][:12]}")
            last_checkpoint_time = time.time()

        if _shutdown_requested:
            cp = save_checkpoint(done, state=state)
            _record(cp)
            print(f"[main] Final checkpoint saved before shutdown: index={done}")
            sys.exit(0)

    cp = save_checkpoint(TOTAL_STEPS, state=state)
    _record(cp)
    expected = workload_state.expected_checksum(TOTAL_STEPS)
    verdict = "MATCH" if state["checksum"] == expected else "MISMATCH"
    print(f"[main] Workload complete. Final checkpoint saved. "
          f"checksum {verdict} (got {state['checksum'][:12]}, expected {expected[:12]})")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    run_workload()
