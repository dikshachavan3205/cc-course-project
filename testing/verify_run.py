"""Prove a run's data survived migration: verify every S3 checkpoint's hash chain.

Usage: python testing/verify_run.py <run_id>

For each checkpoint under checkpoints/<run_id>/ it recomputes the expected
checksum for that checkpoint's index (app/workload_state.py) and compares it to
the checksum stored in the checkpoint. Valid chains across different vm_ids
mean the new instance continued the SAME computation, not a restart.
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import boto3  # noqa: E402

from app import workload_state  # noqa: E402
from shared.constants import AWS_REGION, S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    run_id = sys.argv[1]
    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=S3_CHECKPOINT_BUCKET, Prefix=f"{S3_CHECKPOINT_PREFIX}/{run_id}/"):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".json")]
    keys.sort()
    cps = [json.loads(s3.get_object(Bucket=S3_CHECKPOINT_BUCKET, Key=k)["Body"].read()) for k in keys]
    if not cps:
        print(f"No checkpoints found for {run_id}")
        return 1

    top = max(int(c["last_processed_index"]) for c in cps)
    chain, st = [workload_state.GENESIS], workload_state.initial_state()
    for i in range(top):
        st = workload_state.advance(st, i)
        chain.append(st["checksum"])

    bad, vms, prev_idx = 0, [], -1
    print(f"{'timestamp':32} {'vm_id':22} {'index':>6}  chain")
    for c in cps:
        idx = int(c["last_processed_index"])
        has = isinstance(c.get("state"), dict)
        ok = has and c["state"]["checksum"] == chain[idx]
        bad += 0 if ok else 1
        if c["vm_id"] not in vms:
            vms.append(c["vm_id"])
        print(f"{c['timestamp'][:32]:32} {c['vm_id']:22} {idx:>6}  {'OK' if ok else ('NO-STATE' if not has else 'MISMATCH')}")
    print(f"\n{len(cps)} checkpoints, {len(vms)} distinct instance(s): {', '.join(vms)}")
    print("RESULT:", "ALL CHAINS VALID" if bad == 0 else f"{bad} INVALID CHECKPOINT(S)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
