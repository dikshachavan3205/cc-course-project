"""Manual trigger -- fires a fake high-risk/interruption event for demos.

Phase 12 (the demo safety net). This script does NOT depend on a real AWS
Spot interruption ever happening. It builds the exact same "high risk" event
shape defined in shared/contracts.md #3, then hands it to the *real*
orchestrator (orchestration.recovery_flow.run_migration) -- the identical
function a genuine IMDS warning or a genuine ML prediction would call. Only
the *trigger* is synthetic; everything downstream (checkpoint, provision,
restore, terminate, log, alert) runs for real, exactly as production would.
That's what makes it safe to press live in front of an audience: it proves
the real system, not a separate demo trick.

Usage (run from the repo root):

    python -m testing.simulate_interruption
    python -m testing.simulate_interruption --source predicted --cpu 92 --ram 85
    python -m testing.simulate_interruption --source manual --risk 97
    python -m testing.simulate_interruption --seed-index 42
    python -m testing.simulate_interruption --dry-run
"""

import argparse
import datetime
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.checkpoint_manager import save_checkpoint  # noqa: E402
from monitoring.imds_watcher import build_high_risk_event  # noqa: E402
from orchestration.recovery_flow import run_migration  # noqa: E402
from orchestration.step_logger import StepLogger  # noqa: E402
from shared.constants import RISK_THRESHOLD  # noqa: E402


def build_manual_event(run_id: str, vm_id: str, risk_percent: float) -> dict:
    """Build a high-risk event with a risk_percent you choose directly."""
    return {
        "run_id": run_id,
        "vm_id": vm_id,
        "risk_percent": float(risk_percent),
        "threshold_exceeded": (float(risk_percent) / 100.0) >= RISK_THRESHOLD,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def build_predicted_event(run_id: str, vm_id: str, cpu_percent: float,
                           ram_percent: float, instance_type: str = "t3.micro") -> dict:
    """Ask the real ML model (Phase 6) for a risk score, then wrap it as an event."""
    from prediction.predict import predict_risk
    risk_percent = predict_risk(
        instance_type=instance_type,
        cpu_percent=cpu_percent,
        ram_percent=ram_percent,
        network_mbps=15.0,
        instance_age_minutes=60,
    )
    return build_manual_event(run_id, vm_id, risk_percent)


def fire(
    source: str = "imds",
    run_id: str = "run-demo",
    vm_id: str = "vm-demo",
    risk_percent: float | None = None,
    cpu_percent: float = 90.0,
    ram_percent: float = 85.0,
    seed_index: int | None = None,
    provision_mode: str = "simulate",
    dry_run: bool = False,
) -> dict:
    """
    Build one high-risk event from `source`, then run it through the real
    orchestrator. Returns the same result dict run_migration() returns.
    """
    if seed_index is not None:
        save_checkpoint(seed_index, run_id=run_id, vm_id=vm_id)
        print(f"[simulate] Seeded checkpoint at step {seed_index} for run_id={run_id}",
              file=sys.stderr)

    if source == "imds":
        event = build_high_risk_event(run_id=run_id, vm_id=vm_id, risk_percent=100)
    elif source == "predicted":
        event = build_predicted_event(run_id, vm_id, cpu_percent, ram_percent)
    elif source == "manual":
        event = build_manual_event(run_id, vm_id, risk_percent if risk_percent is not None else 96)
    else:
        raise ValueError(f"Unknown source: {source!r} (choose imds/predicted/manual)")

    print("[simulate] Fake trigger built:", file=sys.stderr)
    print(json.dumps(event, indent=2), file=sys.stderr)

    logger = StepLogger(owner="simulate_interruption", run_id=run_id)
    result = run_migration(
        event,
        provision_mode=provision_mode,
        dry_run=dry_run,
        logger=logger,
        triggered_by=f"manual-{source}",
    )
    return result


def print_human_summary(result: dict) -> None:
    print("\n" + "=" * 60)
    if result["status"] == "noop":
        print("NO MIGRATION -- risk stayed below the threshold.")
    else:
        print(f"MIGRATION {result['status'].upper()}")
        print(f"  From VM      : {result['from_vm_id']}")
        print(f"  To VM        : {result['to_vm_id']}")
        print(f"  Resumed at   : step {result.get('resumed_index')}")
        print(f"  Provision    : {result.get('provision_market')}")
        print(f"  Downtime     : {result.get('downtime_seconds')} s")
        print(f"  Health OK    : {result.get('health_ok')}")
    print("=" * 60 + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fire a fake high-risk/interruption event through the real "
                    "ChronoNet orchestrator (Phase 12 demo trigger)."
    )
    parser.add_argument("--source", choices=["imds", "predicted", "manual"], default="imds")
    parser.add_argument("--run-id", default="run-demo")
    parser.add_argument("--vm-id", default="vm-demo")
    parser.add_argument("--risk", type=float, default=None,
                        help="risk_percent (0-100), only used with --source manual.")
    parser.add_argument("--cpu", type=float, default=90.0)
    parser.add_argument("--ram", type=float, default=85.0)
    parser.add_argument("--seed-index", type=int, default=None)
    parser.add_argument("--provision", choices=["simulate", "real"], default="simulate")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = fire(
        source=args.source, run_id=args.run_id, vm_id=args.vm_id,
        risk_percent=args.risk, cpu_percent=args.cpu, ram_percent=args.ram,
        seed_index=args.seed_index, provision_mode=args.provision, dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, default=str))
    print_human_summary(result)
    return 0 if result["status"] == "noop" or result["status"].startswith("completed") else 1


if __name__ == "__main__":
    sys.exit(main())