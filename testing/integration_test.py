"""End-to-end test: checkpoint -> interrupt -> recover -> verify.

Phase 13 -- Full System Integration Testing. Each check exercises REAL code
paths and fails loudly if a guarantee breaks:

  Check 1 -- repeated interruptions in a row never lose progress.
  Check 2 -- no Spot capacity -> On-Demand fallback still works (boto3 is
             mocked here, so this costs nothing and needs no AWS access).
  Check 3 -- the prediction model never returns risk outside [0, 100].
  Check 4 -- a broken S3 upload does not crash the workload.

Usage:
  python -m testing.integration_test
  python -m testing.integration_test --skip-aws     # skip check 1 only
  python -m testing.integration_test --repeats 5
"""

import argparse
import json as _json
import os
import sys
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def check_repeated_migrations(repeats: int = 3, provision_mode: str = "simulate") -> None:
    from app.checkpoint_manager import LOCAL_CHECKPOINT_FILE, load_checkpoint, save_checkpoint
    from orchestration.migrate import _cleanup_aws
    from orchestration.recovery_flow import run_migration
    from testing.simulate_interruption import build_manual_event

    run_id = "run-integration-test"
    vm_id = "vm-integration-test"
    prior_local = load_checkpoint()

    save_checkpoint(0, run_id=run_id, vm_id=vm_id)

    last_index = -1
    vm = vm_id
    all_vm_ids = [vm_id]
    try:
        for i in range(repeats):
            event = build_manual_event(run_id, vm, risk_percent=95)
            result = run_migration(event, provision_mode=provision_mode,
                                    triggered_by="integration-test")
            assert result["status"].startswith("completed"), (
                f"[check 1] round {i}: expected completed, got {result['status']}"
            )
            resumed = result["resumed_index"]
            assert resumed >= last_index, (
                f"[check 1] round {i}: progress went BACKWARDS "
                f"({resumed} < {last_index}) -- must never happen"
            )
            assert result["health_ok"], f"[check 1] round {i}: health check failed"
            last_index = resumed
            vm = result["to_vm_id"]
            all_vm_ids.append(vm)
            print(f"[check 1] round {i}: OK -- resumed at step {resumed}, "
                  f"downtime {result['downtime_seconds']}s")
        print(f"[check 1] PASSED: {repeats} consecutive migrations, zero progress lost.\n")
    finally:
        try:
            _cleanup_aws(run_id, all_vm_ids)
        except Exception as e:  # noqa: BLE001
            print(f"[check 1] cleanup warning: {type(e).__name__}: {e}")
        if prior_local is not None:
            with open(LOCAL_CHECKPOINT_FILE, "w") as f:
                _json.dump(prior_local, f)


def check_ondemand_fallback() -> None:
    from orchestration.launch_instance import provision_instance

    fail_once = {"done": False}

    class FakeEc2:
        def run_instances(self, **kwargs):
            if kwargs.get("InstanceMarketOptions") and not fail_once["done"]:
                fail_once["done"] = True
                raise RuntimeError("InsufficientInstanceCapacity (simulated)")
            return {"Instances": [{"InstanceId": "i-fakeondemand123"}]}

        def get_waiter(self, name):
            class W:
                def wait(self, **kwargs):
                    return None
            return W()

    with mock.patch("boto3.client", return_value=FakeEc2()):
        result = provision_instance(
            region="ap-south-1", instance_type="t3.micro",
            image_id="ami-fake", allow_real=True,
        )

    assert result["market"] == "ondemand-fallback", (
        f"[check 2] expected On-Demand fallback, got market={result['market']!r}"
    )
    print("[check 2] PASSED: Spot failure correctly fell back to On-Demand.\n")


def check_prediction_bounds() -> None:
    from prediction.predict import predict_risk

    extreme_inputs = [
        dict(instance_type="t3.micro", cpu_percent=-50, ram_percent=-10,
             network_mbps=-5, instance_age_minutes=-100),
        dict(instance_type="t3.micro", cpu_percent=99999, ram_percent=99999,
             network_mbps=99999, instance_age_minutes=999999),
        dict(instance_type="unknown-instance-type-xyz", cpu_percent=50,
             ram_percent=50, network_mbps=10, instance_age_minutes=30),
    ]
    for i, kwargs in enumerate(extreme_inputs):
        risk = predict_risk(**kwargs)
        assert isinstance(risk, float), f"[check 3] case {i}: not a float ({risk!r})"
        assert 0.0 <= risk <= 100.0, f"[check 3] case {i}: risk {risk} outside [0, 100]"
        print(f"[check 3] case {i}: OK -- risk={risk:.2f}% for extreme input")
    print("[check 3] PASSED: model stayed within [0, 100] for all extreme inputs.\n")


def check_broken_s3_upload_is_non_fatal() -> None:
    from app import checkpoint_manager

    class BrokenS3:
        def put_object(self, **kwargs):
            raise RuntimeError("simulated S3 outage")

    original_client = checkpoint_manager._s3_client
    checkpoint_manager._s3_client = BrokenS3()
    try:
        checkpoint = checkpoint_manager.save_checkpoint(
            last_processed_index=123, run_id="run-check4", vm_id="vm-check4"
        )
    finally:
        checkpoint_manager._s3_client = original_client

    assert checkpoint["last_processed_index"] == 123, "[check 4] checkpoint content wrong"
    local = checkpoint_manager.load_checkpoint()
    assert local is not None and local["last_processed_index"] == 123, (
        "[check 4] local checkpoint was not saved despite the S3 failure"
    )
    print("[check 4] PASSED: broken S3 upload did not crash the workload.\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ChronoNet Phase 13 integration tests")
    parser.add_argument("--skip-aws", action="store_true",
                        help="Skip check 1 (needs real S3 + DynamoDB access).")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--provision", choices=["simulate", "real"], default="simulate")
    args = parser.parse_args(argv)

    failures = []
    for name, fn in [
        ("prediction bounds", check_prediction_bounds),
        ("broken S3 upload", check_broken_s3_upload_is_non_fatal),
        ("On-Demand fallback", check_ondemand_fallback),
    ]:
        try:
            fn()
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}\n")
            failures.append(name)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {name}: {type(e).__name__}: {e}\n")
            failures.append(name)

    if not args.skip_aws:
        try:
            check_repeated_migrations(repeats=args.repeats, provision_mode=args.provision)
        except AssertionError as e:
            print(f"[FAIL] repeated migrations: {e}\n")
            failures.append("repeated migrations")
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] repeated migrations: {type(e).__name__}: {e}\n"
                  f"        (needs real AWS access -- try --skip-aws first)")
            failures.append("repeated migrations")
    else:
        print("[skip] repeated migrations (--skip-aws)\n")

    print("=" * 60)
    if failures:
        print(f"INTEGRATION TESTS: {len(failures)} FAILED -> {failures}")
        return 1
    print("INTEGRATION TESTS: ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())