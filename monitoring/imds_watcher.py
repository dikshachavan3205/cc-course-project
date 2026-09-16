"""
Poll the EC2 Instance Metadata Service (IMDSv2) for a Spot interruption notice.

Real flow (on an EC2 instance):
  PUT  http://169.254.169.254/latest/api/token                     -> session token
  GET  http://169.254.169.254/latest/meta-data/spot/instance-action -> 404 if no notice,
       otherwise JSON like {"action": "terminate", "time": "..."}

Local simulation:
  Set CHRONONET_SIMULATE_INTERRUPTION=true (or pass --simulate) so we can
  exercise the pipeline without a running EC2 instance.

On detection (real OR simulated) this module emits the "high risk" event
exactly as defined in shared/contracts.md:

    {
      "run_id": "string",
      "vm_id": "string",
      "risk_percent": 100,
      "threshold_exceeded": true,
      "timestamp": "ISO8601"
    }

The event payload goes to STDOUT (easy to pipe/parse); all diagnostic
messages go to STDERR so they never pollute the JSON output.

CLI:
  python -m monitoring.imds_watcher                # poll forever (real IMDS)
  python -m monitoring.imds_watcher --interval 2   # poll every 2 s
  python -m monitoring.imds_watcher --once         # single check, then exit
  python -m monitoring.imds_watcher --simulate --once   # one simulated event
  CHRONONET_SIMULATE_INTERRUPTION=true python -m monitoring.imds_watcher --once
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# Make `shared/` importable whether run as `-m monitoring.imds_watcher`
# (repo root on sys.path) or `python monitoring/imds_watcher.py` (script dir).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import IMDS_POLL_INTERVAL_SECONDS, RISK_THRESHOLD  # noqa: E402

IMDS_BASE_URL = "http://169.254.169.254"
IMDS_TOKEN_PATH = "/latest/api/token"
IMDS_ACTION_PATH = "/latest/meta-data/spot/instance-action"
IMDS_TOKEN_HEADER = "X-aws-ec2-metadata-token"
IMDS_TTL_HEADER = "X-aws-ec2-metadata-token-ttl-seconds"
IMDS_TOKEN_TTL_SECONDS = 21600  # max allowed TTL for the IMDSv2 session token
IMDS_TIMEOUT_SECONDS = 2

# Simulated interruption switch (env var OR --simulate flag).
SIM_ENV_VAR = "CHRONONET_SIMULATE_INTERRUPTION"
SIMULATED_ACTIONS = ("terminate", "stop", "hibernate")

# A real interruption notice means the instance is about to be reclaimed —
# that is the maximum possible risk, so emit risk_percent = 100.
NOTICE_RISK_PERCENT = 100


def _resolve_run_id() -> str:
    # Matches the default used by app/config.py so the payload lines up with
    # the workload's own identity when no env vars are set.
    return os.environ.get("CHRONONET_RUN_ID", "run-local-dev")


def _resolve_vm_id() -> str:
    return os.environ.get("CHRONONET_VM_ID", "vm-local-dev")


def _get_imds_token() -> str:
    """IMDSv2 requires a PUT request to mint a session token first."""
    response = requests.put(
        IMDS_BASE_URL + IMDS_TOKEN_PATH,
        headers={IMDS_TTL_HEADER: str(IMDS_TOKEN_TTL_SECONDS)},
        timeout=IMDS_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def fetch_interruption_notice() -> dict | None:
    """
    Returns the parsed IMDS spot/instance-action JSON, or None when there is
    no pending notice OR when IMDS is unreachable (e.g. running on a laptop).
    Reachability problems are logged as WARNINGs on STDERR, not swallowed.
    """
    try:
        token = _get_imds_token()
    except requests.RequestException as exc:
        print(f"[imds_watcher] WARNING: IMDS token request failed — is IMDSv2 available? "
              f"({exc})", file=sys.stderr)
        return None

    try:
        response = requests.get(
            IMDS_BASE_URL + IMDS_ACTION_PATH,
            headers={IMDS_TOKEN_HEADER: token},
            timeout=IMDS_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        print(f"[imds_watcher] WARNING: IMDS instance-action request failed ({exc})",
              file=sys.stderr)
        return None

    if response.status_code == 404:
        # 404 is the NORMAL "no interruption notice pending" answer.
        return None

    try:
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"[imds_watcher] WARNING: unexpected IMDS response "
              f"({response.status_code}): {exc}", file=sys.stderr)
        return None


def build_high_risk_event(
    run_id: str | None = None,
    vm_id: str | None = None,
    risk_percent: int = NOTICE_RISK_PERCENT,
) -> dict:
    """
    Builds the "high risk" event EXACTLY matching shared/contracts.md.
    risk_percent defaults to 100 because a real interruption notice is the
    highest possible risk; threshold_exceeded is derived from RISK_THRESHOLD.
    """
    event = {
        "run_id": run_id or _resolve_run_id(),
        "vm_id": vm_id or _resolve_vm_id(),
        "risk_percent": risk_percent,
        "threshold_exceeded": (risk_percent / 100.0) >= RISK_THRESHOLD,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    validate_high_risk_event(event)
    return event


def validate_high_risk_event(event: dict) -> None:
    """Checks an event against the contract shape. Raises ValueError if not OK."""
    expected_keys = {"run_id", "vm_id", "risk_percent", "threshold_exceeded", "timestamp"}
    if set(event.keys()) != expected_keys:
        raise ValueError(
            f"high-risk event keys {sorted(event.keys())} do not match contract {sorted(expected_keys)}"
        )
    risk = event["risk_percent"]
    if not isinstance(risk, (int, float)) or not (0 <= risk <= 100):
        raise ValueError(f"risk_percent must be 0-100, got {risk!r}")
    if not isinstance(event["threshold_exceeded"], bool):
        raise ValueError("threshold_exceeded must be a boolean")


def _simulated_notice(action: str) -> dict:
    return {
        "action": action,
        "time": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
    }


def check_once(simulate: bool = False, simulate_action: str = "terminate") -> tuple[bool, dict | None]:
    """
    Single poll. Returns (detected, event):
      - (False, None)                  when no interruption notice is pending
      - (True, high_risk_event_dict)   when a notice (real or simulated) arrived
    """
    if simulate:
        notice = _simulated_notice(simulate_action)
        print(f"[imds_watcher] SIMULATED interruption notice: {notice}", file=sys.stderr)
        return True, build_high_risk_event()

    notice = fetch_interruption_notice()
    if notice is None:
        return False, None

    print(f"[imds_watcher] Interruption notice received: {notice}", file=sys.stderr)
    return True, build_high_risk_event()


def run_loop(interval: float, simulate: bool, simulate_action: str) -> None:
    """Poll forever, emitting a high-risk event JSON to STDOUT per detection."""
    print(f"[imds_watcher] Polling every {interval:g}s "
          f"(simulate={simulate}). Ctrl+C to stop.", file=sys.stderr)
    while True:
        try:
            detected, event = check_once(simulate=simulate, simulate_action=simulate_action)
            if detected:
                # One compact event per line (JSONL) so a downstream consumer
                # can reliably stream/parse stdout line-by-line.
                print(json.dumps(event))
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n[imds_watcher] Stopping.", file=sys.stderr)
            break
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Poll EC2 IMDSv2 for a Spot interruption notice and emit "
                    "the contractual high-risk event JSON (see shared/contracts.md).",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Poll a single time and exit instead of looping forever.",
    )
    parser.add_argument(
        "--simulate", action="store_true",
        help=f"Emit a simulated interruption (equivalent to {SIM_ENV_VAR}=true).",
    )
    parser.add_argument(
        "--simulate-action", choices=SIMULATED_ACTIONS, default="terminate",
        help="Action reported by a simulated notice (default: terminate).",
    )
    parser.add_argument(
        "--interval", type=float,
        default=float(os.environ.get("CHRONONET_POLL_INTERVAL", IMDS_POLL_INTERVAL_SECONDS)),
        help="Poll interval in seconds (default: CHRONONET_POLL_INTERVAL or "
             f"{IMDS_POLL_INTERVAL_SECONDS}s from shared/constants.py).",
    )
    args = parser.parse_args(argv)

    simulate = args.simulate or os.environ.get(SIM_ENV_VAR, "").strip().lower() == "true"

    if args.once:
        detected, event = check_once(simulate=simulate, simulate_action=args.simulate_action)
        if detected:
            print(json.dumps(event, indent=2))
        else:
            print("[imds_watcher] No interruption notice detected.", file=sys.stderr)
        return 0

    run_loop(args.interval, simulate, args.simulate_action)
    return 0


if __name__ == "__main__":
    sys.exit(main())