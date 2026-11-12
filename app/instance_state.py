"""Best-effort DynamoDB registration/heartbeat for the instance running the workload.

Enabled only when CHRONONET_REGISTER_STATE=true (set by the EC2 bootstrap), so
local runs never touch DynamoDB. Failures are logged, never fatal: the
workload must keep running and checkpointing even if DynamoDB is unreachable.
Writes the vm-state attributes defined in shared/contracts.md section 6.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("chrononet.instance_state")


def enabled() -> bool:
    return os.environ.get("CHRONONET_REGISTER_STATE", "").lower() in {"1", "true", "yes"}


def _db():
    from data_backend.aws.dynamodb_client import DynamoDBClient
    return DynamoDBClient()


def register(run_id: str, vm_id: str, resumed_index: int,
             instance_type: str | None = None, market: str | None = None) -> bool:
    """Announce 'I am running and resumed from this index' (the hub polls for this)."""
    if not enabled():
        return False
    try:
        fields = {
            "run_id": run_id,
            "status": "running",
            "resumed_index": int(resumed_index),
            "interruption_notice": False,
            "launched_at": datetime.now(timezone.utc).isoformat(),
        }
        if instance_type:
            fields["instance_type"] = instance_type
        if market:
            fields["market"] = market
        _db().update_vm_state(vm_id, **fields)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("vm-state register failed: %s: %s", type(exc).__name__, exc)
        return False


def heartbeat(run_id: str, vm_id: str, index: int, s3_key: str | None = None) -> bool:
    """Record the latest checkpoint index/key on this VM's state row."""
    if not enabled():
        return False
    try:
        _db().record_checkpoint(vm_id, run_id, int(index), s3_key=s3_key)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("vm-state heartbeat failed: %s: %s", type(exc).__name__, exc)
        return False
