"""Free, offline checks for Phase 1 (no AWS calls, no cost).

  python testing/test_phase1_local.py

1. Resume continuity: run the workload in two segments via a checkpoint file and
   confirm the final hash chain equals an uninterrupted run.
2. Real-mode migration logic against fakes: happy path, no-checkpoint abort, and
   unhealthy replacement (old instance must NOT be terminated).
"""
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from app import workload_state  # noqa: E402


def run_workload(ckpt_dir, total):
    env = dict(os.environ, CHRONONET_CHECKPOINT_DIR=ckpt_dir, CHRONONET_DISABLE_S3="true",
               CHRONONET_RUN_ID="run-test", CHRONONET_VM_ID="vm-test",
               CHRONONET_TOTAL_STEPS=str(total), CHRONONET_STEP_DELAY="0.001",
               CHRONONET_CHECKPOINT_INTERVAL="999999")
    out = subprocess.run([sys.executable, os.path.join(REPO, "app", "main.py")],
                         env=env, capture_output=True, text=True, cwd=REPO)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_resume_continuity():
    with tempfile.TemporaryDirectory() as d:
        first = run_workload(d, 80)
        assert "starting fresh" in first and "checksum MATCH" in first, first
        second = run_workload(d, 200)           # resumes at 80, finishes at 200
        assert "Resuming from checkpoint: step 80" in second, second
        assert "checksum MATCH" in second, second
    print("PASS resume continuity (80 -> 200, chain matches an uninterrupted run)")


class FakeLogger:
    def __init__(self): self.timeline = []
    def step(self, name, **f): self.timeline.append(name); return {}
    def note(self, name, **f): self.timeline.append(name); return {}


class FakeDB:
    def __init__(self, healthy=True): self.healthy, self.calls = healthy, []
    def update_vm_state(self, vm, **f): self.calls.append(("update_vm_state", vm, f))
    def put_vm_state(self, **f): self.calls.append(("put_vm_state", f))   # must NOT happen in real mode
    def record_migration(self, **f): self.calls.append(("record_migration",)); return "ts-1"
    def update_migration(self, *a, **f): self.calls.append(("update_migration", f))
    def record_checkpoint(self, **f): self.calls.append(("record_checkpoint", f))
    def get_vm_state(self, vm):
        if vm == "i-new":
            return {"status": "running", "resumed_index": 130} if self.healthy else {"status": "launching"}
        return {"migration_count": 2}


def run_real(checkpoint, healthy):
    import orchestration.recovery_flow as rf
    terminated, db = [], FakeDB(healthy)
    rf.DynamoDBClient = lambda: db
    rf.load_latest_checkpoint_from_s3 = lambda run_id: checkpoint
    rf.pick_replacement_pool = lambda **k: ("subnet-b", "t3.small")
    rf.load_run_config = lambda run_id: {}
    rf.provision_instance = lambda **k: {"instance_id": "i-new", "market": "spot", "mode": "real"}
    rf.terminate_instance = lambda **k: terminated.append(k["instance_id"]) or {"CurrentState": {"Name": "shutting-down"}}
    rf.SnsClient = lambda: type("S", (), {"topic_arn": "t", "publish_migration_alert": lambda s, r: {"MessageId": "m"}})()
    os.environ["CHRONONET_BOOT_TIMEOUT"] = "1"
    rf.time.sleep = lambda s: None
    event = {"run_id": "run-test", "vm_id": "i-old", "risk_percent": 96, "threshold_exceeded": True}
    res = rf.run_migration(event, provision_mode="real", allow_real_ec2=True, logger=FakeLogger())
    return res, terminated, db


def test_real_mode_logic():
    cp = {"run_id": "run-test", "vm_id": "i-old", "last_processed_index": 120,
          "timestamp": "2026-01-01T00:00:00+00:00", "state": {}}
    res, term, db = run_real(cp, healthy=True)
    assert res["status"] == "completed" and res["to_vm_id"] == "i-new", res
    assert res["resumed_index"] == 130 and term == ["i-old"], (res, term)
    assert not [c for c in db.calls if c[0] == "put_vm_state"], "put_vm_state would overwrite the instance's own row"
    assert any(c[0] == "update_vm_state" and c[1] == "i-new" and c[2].get("migration_count") == 3 for c in db.calls)
    print("PASS real-mode happy path (new instance resumed at 130, old terminated, count 2->3)")

    res, term, _ = run_real(None, healthy=True)
    assert res["status"] == "failed" and term == [], res
    print("PASS no checkpoint in S3 -> aborts, nothing launched/terminated")

    res, term, _ = run_real(cp, healthy=False)
    assert res["status"] == "failed" and term == [], (res, term)
    print("PASS unhealthy replacement -> old instance kept (NOT terminated)")


def test_userdata_single_encoded():
    """The request that would hit EC2 must carry the script base64-encoded ONCE."""
    import base64
    import urllib.parse
    import boto3
    import orchestration.launch_instance as li
    from orchestration.user_data import build_user_data

    os.environ.update(AWS_ACCESS_KEY_ID="x", AWS_SECRET_ACCESS_KEY="x", AWS_DEFAULT_REGION="ap-south-1")
    captured = {}
    real_client = boto3.client

    def fake_client(*a, **k):
        c = real_client(*a, **k)

        def grab(params, **kw):
            body = params["body"]
            if isinstance(body, dict):          # ec2 (query protocol) passes a dict here
                captured.update({k: [v] for k, v in body.items()})
            else:
                body = body.decode() if isinstance(body, bytes) else body
                captured.update(urllib.parse.parse_qs(body))
            raise RuntimeError("captured")   # stop before any network call
        c.meta.events.register("before-call.ec2.RunInstances", grab)
        return c

    li.boto3.client = fake_client
    try:
        li.provision_instance(region="ap-south-1", instance_type="t3.micro", image_id="ami-1",
                              user_data=build_user_data(run_id="run-x"), tags={"Project": "chrononet"},
                              allow_real=True)
    except Exception:
        pass
    finally:
        li.boto3.client = real_client
    script = base64.b64decode(captured["UserData"][0]).decode()
    assert script.startswith("#!/bin/bash"), "UserData is double-encoded: " + script[:40]
    assert captured["InstanceInitiatedShutdownBehavior"] == ["terminate"]
    print("PASS user-data is sent as a real script (single base64), shutdown=terminate")


if __name__ == "__main__":
    test_resume_continuity()
    test_real_mode_logic()
    test_userdata_single_encoded()
    print("\nALL PHASE 1 LOCAL TESTS PASSED")
