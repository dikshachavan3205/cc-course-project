"""Measures and logs actual migration downtime.

Runs several simulated migrations back-to-back through the real
orchestrator and records each measured downtime_seconds. This is where the
"our downtime stayed under 10s" number in your report actually comes from --
not a single lucky run.

Usage:
  python -m testing.downtime_timer
  python -m testing.downtime_timer --runs 10 --target 8
"""

import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

RUN_LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_results", "run_logs")


def measure(runs: int = 5, provision_mode: str = "simulate", target_seconds: float = 10.0,
            keep_aws: bool = False) -> dict:
    from orchestration.migrate import _cleanup_aws
    from testing.simulate_interruption import fire

    downtimes, details = [], []
    for i in range(runs):
        run_id, vm_id = f"run-downtime-{i}", f"vm-downtime-{i}"
        result = fire(source="manual", run_id=run_id, vm_id=vm_id,
                       risk_percent=97, provision_mode=provision_mode)
        dt = result.get("downtime_seconds")
        downtimes.append(dt)
        details.append({"run": i, "downtime_seconds": dt, "status": result["status"],
                        "resumed_index": result.get("resumed_index")})
        print(f"[downtime_timer] run {i}: {dt}s (status={result['status']})")
        if not keep_aws:
            try:
                _cleanup_aws(run_id, [vm_id, result.get("to_vm_id")])
            except Exception as e:  # noqa: BLE001
                print(f"[downtime_timer] cleanup warning run {i}: {type(e).__name__}: {e}")

    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "runs": runs, "provision_mode": provision_mode, "target_seconds": target_seconds,
        "downtimes": downtimes,
        "min": min(downtimes), "max": max(downtimes),
        "avg": round(statistics.mean(downtimes), 4),
        "median": round(statistics.median(downtimes), 4),
        "all_under_target": all(d <= target_seconds for d in downtimes),
        "details": details,
    }


def save_summary(summary: dict) -> str:
    os.makedirs(RUN_LOGS_DIR, exist_ok=True)
    fname = f"downtime_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path = os.path.join(RUN_LOGS_DIR, fname)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Measure ChronoNet migration downtime over N runs")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--target", type=float, default=10.0)
    parser.add_argument("--provision", choices=["simulate", "real"], default="simulate")
    parser.add_argument("--keep-aws", action="store_true")
    args = parser.parse_args(argv)

    summary = measure(runs=args.runs, provision_mode=args.provision,
                       target_seconds=args.target, keep_aws=args.keep_aws)
    path = save_summary(summary)

    print("\n" + "=" * 60)
    print(f"Runs: {summary['runs']}  |  Target: <= {summary['target_seconds']}s")
    print(f"Min: {summary['min']}s  Max: {summary['max']}s  "
          f"Avg: {summary['avg']}s  Median: {summary['median']}s")
    print(f"All under target: {summary['all_under_target']}")
    print(f"Saved -> {path}")
    print("=" * 60)
    return 0 if summary["all_under_target"] else 1


if __name__ == "__main__":
    sys.exit(main())