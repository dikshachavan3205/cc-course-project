"""Free, offline checks for Phase 2/3 (no AWS calls).   python testing/test_phase2_local.py"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


def test_price_features_match_training():
    import pandas as pd
    from prediction.features import compute_price_features
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    prices = [(t0 + timedelta(hours=i), p) for i, p in enumerate([0.0031, 0.0032, 0.0031, 0.0040, 0.0035])]
    got = compute_price_features(prices)
    s = pd.Series([p for _, p in prices])
    assert abs(got["price_volatility"] - s.std()) < 1e-12
    assert abs(got["price_trend_ratio"] - s.iloc[-1] / s.mean()) < 1e-12
    assert compute_price_features([]) == {"price_volatility": 0.0, "price_trend_ratio": 1.0}
    print("PASS price features == training definition (std, recent/mean)")


def test_trigger_logic():
    from monitoring.monitor_loop import TriggerState
    t = TriggerState(threshold=15, consecutive=3, cooldown_s=300)
    assert [t.update(r, False, 0) for r in (20, 20)] == [None, None]
    assert t.update(5, False, 0) is None and t.count == 0, "a dip must reset the streak"
    assert [t.update(r, False, 1) for r in (20, 20, 20)] == [None, None, "prediction"]
    assert t.update(99, True, 100) is None, "cooldown must block even a notice"
    assert t.update(1, True, 400) == "imds", "an interruption notice fires immediately"
    print("PASS trigger: streak, reset, cooldown, immediate notice")


def test_agent_sample():
    from monitoring.instance_agent import Sampler
    s = Sampler().sample()
    assert 0 <= s["cpu_percent"] <= 100 and 0 <= s["ram_percent"] <= 100
    assert s["network_mbps"] >= 0 and s["instance_age_minutes"] >= 0
    print("PASS agent sampler returns real cpu/ram/network/age")


class FakeDB:
    def __init__(self): self.rows, self.preds = {}, []
    def get_vm_state(self, i): return {"cpu_percent": 55, "ram_percent": 40, "network_mbps": 2, "instance_age_minutes": 30}
    def update_vm_state(self, i, **f): self.rows.setdefault(i, {}).update(f)
    def put_prediction(self, run_id, iid, risk, **a): self.preds.append((iid, round(risk, 2), a))


def test_monitor_cycle():
    import monitoring.monitor_loop as ml
    calls = []
    ml.find_active = lambda run_id, region: ("i-abc", "t3.micro")
    ml.live_features = lambda t, row, region: {"instance_type": t, "cpu_percent": 55.0, "ram_percent": 40.0,
                                                "network_mbps": 2.0, "instance_age_minutes": 30,
                                                "price_volatility": 1e-4, "price_trend_ratio": 1.0, "savings_percent": 68.0}
    ml.predict_risk = lambda **k: 20.0
    ml.run_migration = lambda event, **k: calls.append((event, k)) or {"status": "completed", "from_vm_id": "i-abc",
                                                                       "to_vm_id": "i-new", "downtime_seconds": 61}
    db, trig = FakeDB(), ml.TriggerState(15, 3, 300)
    for _ in range(3):
        ml.cycle("run-x", db, trig, 15, "real", False)
    assert len(calls) == 1 and calls[0][1]["triggered_by"] == "prediction" and calls[0][1]["allow_real_ec2"] is True
    assert calls[0][0]["vm_id"] == "i-abc" and len(db.preds) == 3 and db.rows["i-abc"]["risk_percent"] == 20.0
    db2, trig2, calls[:] = FakeDB(), ml.TriggerState(15, 1, 300), []
    ml.cycle("run-x", db2, trig2, 15, "real", True)
    assert calls == [], "dry-run must never migrate"
    print("PASS monitor cycle: predicts, logs, migrates after 3 readings; dry-run is inert")


def test_bootstrap_script():
    from orchestration.user_data import build_user_data
    script = build_user_data(run_id="run-t")
    assert "psutil" in script and "monitoring/instance_agent.py" in script
    open("/tmp/_ud.sh", "w", newline="\n").write(script) if os.name != "nt" else None
    if os.name != "nt":
        assert subprocess.run(["bash", "-n", "/tmp/_ud.sh"]).returncode == 0
    print("PASS bootstrap installs psutil, starts the agent" + ("" if os.name == "nt" else ", valid bash"))


if __name__ == "__main__":
    test_price_features_match_training()
    test_trigger_logic()
    test_agent_sample()
    test_monitor_cycle()
    test_bootstrap_script()
    print("\nALL PHASE 2/3 LOCAL TESTS PASSED")
