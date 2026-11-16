"""On-instance agent: reports REAL telemetry + interruption signals to DynamoDB.

Every CHRONONET_AGENT_INTERVAL seconds (default 10) it writes this instance's
cpu/ram/network/age to its vm-state row and sets interruption_notice=true when
IMDS shows a Spot interruption notice or a rebalance recommendation.
Started by orchestration/user_data.py. Python 3.9-safe.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import psutil  # noqa: E402

IMDS = "http://169.254.169.254/latest"


def _token() -> str | None:
    try:
        req = urllib.request.Request(f"{IMDS}/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"})
        return urllib.request.urlopen(req, timeout=2).read().decode()
    except Exception:  # noqa: BLE001
        return None


def _imds(path: str, token: str | None) -> str | None:
    """Body of an IMDS path, or None when absent (404) / unreachable."""
    try:
        headers = {"X-aws-ec2-metadata-token": token} if token else {}
        return urllib.request.urlopen(urllib.request.Request(f"{IMDS}/{path}", headers=headers),
                                      timeout=2).read().decode()
    except Exception:  # noqa: BLE001
        return None


def check_notice(token: str | None) -> str | None:
    """'spot-interruption' | 'rebalance' | None."""
    if _imds("meta-data/spot/instance-action", token):
        return "spot-interruption"
    if _imds("meta-data/events/recommendations/rebalance", token):
        return "rebalance"
    return None


class Sampler:
    def __init__(self):
        self._net = psutil.net_io_counters()
        self._t = time.time()
        psutil.cpu_percent(interval=None)  # prime

    def sample(self) -> dict:
        now, net = time.time(), psutil.net_io_counters()
        dt = max(now - self._t, 1e-6)
        mbps = ((net.bytes_sent + net.bytes_recv) - (self._net.bytes_sent + self._net.bytes_recv)) * 8 / 1e6 / dt
        self._net, self._t = net, now
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 2),
            "ram_percent": round(psutil.virtual_memory().percent, 2),
            "network_mbps": round(mbps, 3),
            "instance_age_minutes": round((time.time() - psutil.boot_time()) / 60.0, 1),
        }


def main() -> None:
    from data_backend.aws.dynamodb_client import DynamoDBClient
    run_id, vm_id = os.environ["CHRONONET_RUN_ID"], os.environ["CHRONONET_VM_ID"]
    interval = float(os.environ.get("CHRONONET_AGENT_INTERVAL", "10"))
    db, sampler, token = DynamoDBClient(), Sampler(), _token()
    print(f"[agent] reporting for {vm_id} (run {run_id}) every {interval}s", flush=True)
    while True:
        time.sleep(interval)
        try:
            notice = check_notice(token)
            fields = sampler.sample()
            try:  # sample-data visibility: report the artifact this instance holds
                from app.sample_artifact import LOG_FILE, line_count, tail
                lines = tail(1)
                if lines:
                    fields["sample_log_tail"] = lines[-1][:400]
                fields["sample_log_lines"] = line_count()
                fields["sample_log_path"] = LOG_FILE
            except Exception:  # noqa: BLE001
                pass
            if notice:
                fields["interruption_notice"] = True
                print(f"[agent] NOTICE: {notice}", flush=True)
            db.update_vm_state(vm_id, run_id=run_id, **fields)
        except Exception as exc:  # noqa: BLE001 - never die; just report next cycle
            print(f"[agent] warning: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
