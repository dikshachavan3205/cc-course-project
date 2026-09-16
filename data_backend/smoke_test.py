"""End-to-end smoke test for the hardened ChronoNet orchestration hub.

Starts the FastAPI server (uvicorn) on 127.0.0.1:8001, then verifies:
  1. GET  /status              200 + EXACT contract shape #2, even for a
                                vm_id with no DynamoDB row (graceful fallback)
  2. CORS headers present (React frontend on common dev port)
  3. POST /interruption        200 + contract shape for a completed migration
  4. POST /interruption        noop when threshold_exceeded=False
  5. POST /interruption        422 when the payload violates the RiskEvent schema
  6. GET  /history             200 + normalized JSON migrations (no Decimals)
  7. GET  /health and GET  /   directory listing
  8. Test rows/S3 objects cleaned out of the shared AWS account afterwards

Usage:
  python data_backend/smoke_test.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import boto3  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from data_backend.aws.dynamodb_client import DynamoDBClient  # noqa: E402
from shared.constants import (  # noqa: E402
    AWS_REGION, S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX,
)

BASE_URL = os.environ.get("CHRONONET_API_URL", "http://127.0.0.1:8001")
PORT = int(BASE_URL.rsplit(":", 1)[1])

LOCAL_CHECKPOINT = os.path.join(REPO_ROOT, "app", "checkpoints", "checkpoint.json")

STATUS_KEYS = {
    "run_id", "vm_id", "region", "cpu_percent", "ram_percent",
    "risk_percent", "migration_count", "last_downtime_seconds",
}
INTERRUPTION_KEYS = {
    "run_id", "from_vm_id", "to_vm_id", "migration_id", "status",
    "checkpoint_key", "downtime_seconds",
}

EVENT = {
    "run_id": "smoke-test-run",
    "vm_id": "smoke-test-vm",
    "risk_percent": 100.0,
    "threshold_exceeded": True,
    "timestamp": "2026-09-15T00:00:00+00:00",
}


def http_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {}
        return e.code, payload, dict(e.headers)


def wait_until_ready(proc: subprocess.Popen, timeout_s: int = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        try:
            code, _, _ = http_request("GET", "/health")
            if code == 200:
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError("server did not become ready in time")


def cleanup_aws(run_ids: list[str], vm_ids: list[str]) -> None:
    db = DynamoDBClient()
    for vid in vm_ids:
        try:
            db.delete_vm_state(vid)
        except Exception as e:
            print(f"[smoke] WARNING: delete_vm_state({vid}) failed: {e}")
    for run_id in run_ids:
        try:
            for m in db.list_migrations(run_id):
                db.delete_migration(run_id, m["timestamp"])
        except Exception as e:
            print(f"[smoke] WARNING: delete_migration({run_id}) failed: {e}")
    s3 = boto3.client("s3", region_name=AWS_REGION)
    for run_id in run_ids:
        prefix = f"{S3_CHECKPOINT_PREFIX}/{run_id}/"
        while True:
            resp = s3.list_objects_v2(Bucket=S3_CHECKPOINT_BUCKET, Prefix=prefix)
            keys = [o["Key"] for o in resp.get("Contents", [])]
            if not keys:
                break
            s3.delete_objects(Bucket=S3_CHECKPOINT_BUCKET,
                              Delete={"Objects": [{"Key": k} for k in keys]})
            if not resp.get("IsTruncated"):
                break


def main() -> int:
    server = None
    migrated = None
    had_local_checkpoint = os.path.exists(LOCAL_CHECKPOINT)
    prior_checkpoint = None
    if had_local_checkpoint:
        with open(LOCAL_CHECKPOINT, "r") as f:
            prior_checkpoint = f.read()

    if not os.environ.get("CHRONONET_API_URL"):
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "data_backend.main:app",
             "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_until_ready(server)

    try:
        # 0. /health + / directory listing
        code, health, _ = http_request("GET", "/health")
        assert code == 200 and health["status"] == "ok", health
        code, root, _ = http_request("GET", "/")
        assert code == 200, f"GET / -> {code}"
        assert "/status" in root["endpoints"] and "/interruption" in root["endpoints"]
        print("[smoke] GET /health + /  OK")

        # 1. /status must match the contract EXACTLY.
        code, status, _ = http_request("GET", "/status")
        assert code == 200, f"/status -> {code}"
        assert set(status.keys()) == STATUS_KEYS, f"keys mismatch: {sorted(status.keys())}"
        assert 0 <= status["risk_percent"] <= 100
        print("[smoke] GET /status  OK  ->", json.dumps(status))

        # 1b. /status must degrade gracefully for a vm_id with NO DynamoDB row
        #     (missing row must not 500 — zeros + model fallback instead).
        code, status2, _ = http_request(
            "GET", f"/status?vm_id=no-such-vm-{int(time.time())}&run_id=smoke-test-run")
        assert code == 200, f"/status (missing row) -> {code}"
        assert set(status2.keys()) == STATUS_KEYS, f"keys mismatch: {sorted(status2.keys())}"
        print("[smoke] GET /status (missing DynamoDB row) OK  -> graceful defaults")

        # 2. CORS headers present (React frontend on common dev port).
        _, _, headers = http_request("GET", "/status")
        origin_hdr = next((v for k, v in headers.items()
                           if k.lower() == "access-control-allow-origin"), None)
        assert origin_hdr, "missing Access-Control-Allow-Origin header"
        print(f"[smoke] CORS headers OK  (Access-Control-Allow-Origin={origin_hdr})")

        # 3. Valid high-risk event -> real migration workflow completes.
        code, migrated, _ = http_request("POST", "/interruption", body=EVENT)
        assert code == 200, f"/interruption -> {code} ({migrated})"
        assert set(migrated.keys()) == INTERRUPTION_KEYS, \
            f"keys mismatch: {sorted(migrated.keys())}"
        assert migrated["status"] == "completed", migrated
        assert migrated["from_vm_id"] != migrated["to_vm_id"], migrated
        assert migrated["checkpoint_key"], migrated
        assert migrated["downtime_seconds"] >= 0
        print("[smoke] POST /interruption OK ->", json.dumps(migrated))

        # 4. Below-threshold event -> "noop", contract shape, no migration.
        noop_event = dict(EVENT, risk_percent=20.0, threshold_exceeded=False,
                          run_id="smoke-test-noop")
        code, noop, _ = http_request("POST", "/interruption", body=noop_event)
        assert code == 200, f"/interruption (noop) -> {code}"
        assert noop["status"] == "noop", noop
        assert noop["to_vm_id"] == noop["from_vm_id"], noop
        print("[smoke] POST /interruption (below threshold) OK  -> noop")

        # 5. Payload violating the RiskEvent schema -> 422 (not 500).
        code, detail, _ = http_request("POST", "/interruption", body=EVENT | {"risk_percent": 150})
        assert code == 422, f"out-of-range risk -> {code}"
        code, _, _ = http_request(
            "POST", "/interruption", body=EVENT | {"timestamp": "not-an-iso-date"})
        assert code == 422, f"bad timestamp -> {code}"
        code, _, _ = http_request(
            "POST", "/interruption", body={k: v for k, v in EVENT.items()
                                           if k != "run_id"})
        assert code == 422, f"missing field -> {code}"
        print("[smoke] POST /interruption (invalid payload) OK  -> 422")

        # 6. Migration logged in DynamoDB history, JSON-safe numbers (no Decimal).
        code, history, _ = http_request("GET", f"/history?run_id={EVENT['run_id']}")
        assert code == 200, f"/history -> {code}"
        migs = history.get("migrations", [])
        assert migs, "expected at least one migration in history"
        latest = migs[0]
        assert latest["status"] == "completed", latest
        assert isinstance(latest["downtime_seconds"], (int, float)), latest
        print(f"[smoke] GET /history OK  ({len(migs)} migration(s) for "
              f"{EVENT['run_id']}, latest: {latest['from_vm_id']} -> {latest['to_vm_id']})")

        # 6b. /history degrades gracefully on a run with no rows.
        code, history2, _ = http_request("GET", "/history?run_id=smoke-no-history")
        assert code == 200, f"/history (empty) -> {code}"
        assert history2.get("migrations") == [], history2
        print("[smoke] GET /history (no rows) OK  -> []")

        print("\n[smoke] ALL CHECKS PASSED")
        return 0
    finally:
        cleanup_aws(["smoke-test-run", "smoke-test-noop", "smoke-no-history"],
                    [EVENT["vm_id"], migrated["to_vm_id"]] if migrated else [EVENT["vm_id"]])
        if had_local_checkpoint and prior_checkpoint is not None:
            os.makedirs(os.path.dirname(LOCAL_CHECKPOINT), exist_ok=True)
            with open(LOCAL_CHECKPOINT, "w") as f:
                f.write(prior_checkpoint)
        elif os.path.exists(LOCAL_CHECKPOINT):
            os.remove(LOCAL_CHECKPOINT)
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        print("[smoke] Test data cleaned, server stopped.")


if __name__ == "__main__":
    sys.exit(main())