"""Free, offline checks for the Phase 3 backend (no AWS).   python testing/test_phase3_local.py"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from fastapi.testclient import TestClient  # noqa: E402

import data_backend.main as m  # noqa: E402

ROWS = [
    {"instance_id": "vm-local-dev", "run_id": "run-local-dev", "status": "running", "risk_percent": 100.0},
    {"instance_id": "i-old", "run_id": "run-r1", "status": "terminated", "market": "spot", "instance_type": "t3.micro",
     "launched_at": "2026-11-14T17:00:00+00:00"},
    {"instance_id": "i-new", "run_id": "run-r1", "status": "running", "market": "spot", "instance_type": "t3.small",
     "launched_at": "2026-11-14T17:20:00+00:00", "cpu_percent": 35, "ram_percent": 22, "risk_percent": 7.5,
     "migration_count": 1, "last_downtime_seconds": 54.5},
]


class FakeDB:
    def list_vm_states(self, run_id=None): return [r for r in ROWS if run_id is None or r.get("run_id") == run_id]
    def get_vm_state(self, vid): return next((dict(r) for r in ROWS if r["instance_id"] == vid), None)
    def list_predictions(self, run_id, limit=100): return [{"run_id": run_id, "timestamp": "t", "risk_percent": 7.5}]
    def list_migrations(self, run_id): return []


m.DynamoDBClient = FakeDB
c = TestClient(m.app)

s = c.get("/status").json()
assert s["vm_id"] == "i-new" and s["run_id"] == "run-r1", s            # newest REAL instance, not vm-local-dev
assert s["instance_type"] == "t3.small" and s["market"] == "spot" and s["risk_percent"] == 7.5, s
assert s["migration_count"] == 1 and s["vm_status"] == "running", s
print("PASS /status resolves the newest real instance (ignores the legacy vm-local-dev row)")

assert c.get("/status?run_id=run-x&vm_id=i-x").json()["vm_id"] == "i-x"
print("PASS /status honours explicit run_id/vm_id")

p = c.get("/predictions").json()
assert p["run_id"] == "run-r1" and p["predictions"][0]["risk_percent"] == 7.5
i = c.get("/instances").json()["instances"]
assert [x["instance_id"] for x in i] == ["i-new", "i-old"] and i[0]["market"] == "spot", i
print("PASS /predictions and /instances (newest first, scoped to the run)")

for k in ("CHRONONET_PROVISION_MODE", "CHRONONET_ALLOW_REAL_EC2"):
    os.environ.pop(k, None)
cfg = c.get("/config").json()
assert cfg["risk_warn_percent"] == 10.0 and cfg["risk_migrate_percent"] == 15.0 and cfg["provision_mode"] == "simulate", cfg
os.environ["CHRONONET_PROVISION_MODE"] = "real"
assert c.get("/config").json()["provision_mode"] == "simulate", "real needs BOTH env vars"
os.environ["CHRONONET_ALLOW_REAL_EC2"] = "true"
assert c.get("/config").json()["provision_mode"] == "real"
print("PASS /config: thresholds 10/15, real mode requires both env vars")

seen = {}
m.run_migration = lambda **k: seen.update(k) or {"status": "completed", "to_vm_id": "i-n", "migration_id": "x",
                                                  "downtime_seconds": 1.0, "steps": []}
ev = {"run_id": "run-r1", "vm_id": "i-new", "risk_percent": 96, "threshold_exceeded": True,
      "timestamp": "2026-11-14T17:30:00+00:00"}
assert c.post("/interruption", json=ev).status_code == 200
assert seen["provision_mode"] == "real" and seen["allow_real_ec2"] is True
os.environ.pop("CHRONONET_PROVISION_MODE")
c.post("/interruption", json=ev)
assert seen["provision_mode"] == "simulate"
print("PASS /interruption: real migration only when explicitly enabled, otherwise simulate")
print("\nALL PHASE 3 LOCAL TESTS PASSED")
