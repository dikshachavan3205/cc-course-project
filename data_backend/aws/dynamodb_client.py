"""DynamoDB helpers for VM state, checkpoint tracking, and migration history.

Tables are defined in shared/constants.py and created by
data_backend/db_setup/create_tables.py :

  chrononet-vm-state     HASH: instance_id -> one row per VM instance
  chrononet-migrations   HASH: run_id, SORT: timestamp -> migration history per run

NOTE on keys: the live tables in the shared account already use `instance_id`
(a.k.a. our vm_id) as the vm-state key and `timestamp` as the migrations sort
key — this client matches that EXISTING schema so it works against the real
tables without any destructive migration.

Every write/read goes through boto3 resource/table objects bound to AWS_REGION
from shared/constants.py.

Usage (as a library):
    from data_backend.aws.dynamodb_client import DynamoDBClient
    db = DynamoDBClient()
    db.put_vm_state(vm_id="vm-a", run_id="run-1", cpu_percent=42.5)
    db.record_checkpoint(vm_id="vm-a", run_id="run-1",
                         last_processed_index=12, s3_key="checkpoints/run-1/..")
    ts = db.record_migration(run_id="run-1", from_vm_id="vm-a", to_vm_id="vm-b")
    db.complete_migration("run-1", ts)

CLI validation:
    python -m data_backend.aws.dynamodb_client --self-check
    python -m data_backend.aws.dynamodb_client --create-tables
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from data_backend.db_setup.create_tables import create_tables_if_missing  # noqa: E402
from shared.constants import (  # noqa: E402
    AWS_REGION,
    DYNAMODB_TABLE_VM_STATE,
    DYNAMODB_TABLE_MIGRATIONS,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_decimal(value):
    """boto3's resource layer stores numbers as Decimal — convert floats too."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return value


class DynamoDBClient:
    """Thin wrapper around the two ChronoNet DynamoDB tables."""

    # VM-state fields that update_vm_state is allowed to touch.
    VM_STATE_FIELDS = {
        "run_id", "status", "cpu_percent", "ram_percent", "risk_percent",
        "migration_count", "last_downtime_seconds",
    }

    def __init__(self, region: str | None = None):
        self.region = region or AWS_REGION
        self._resource = boto3.resource("dynamodb", region_name=self.region)
        self._client = boto3.client("dynamodb", region_name=self.region)

    # ── infrastructure ──────────────────────────────────────────────────────
    def ensure_tables(self) -> list[str]:
        """Create the ChronoNet tables if they don't exist yet."""
        return create_tables_if_missing(self._client)

    def _table(self, name: str):
        return self._resource.Table(name)

    # ── VM state (chrononet-vm-state, HASH: instance_id) ───────────────────
    def put_vm_state(
        self,
        vm_id: str,
        run_id: str,
        region: str | None = None,
        cpu_percent: float = 0.0,
        ram_percent: float = 0.0,
        risk_percent: float = 0.0,
        migration_count: int = 0,
        last_downtime_seconds: float = 0.0,
        status: str = "running",
    ) -> dict:
        """Upsert the state record for a VM instance (keyed by instance_id)."""
        item = {
            "instance_id": vm_id,       # table HASH key
            "vm_id": vm_id,             # contract-facing alias
            "run_id": run_id,
            "region": region or self.region,
            "status": status,
            "cpu_percent": _as_decimal(cpu_percent),
            "ram_percent": _as_decimal(ram_percent),
            "risk_percent": _as_decimal(risk_percent),
            "migration_count": _as_decimal(migration_count),
            "last_downtime_seconds": _as_decimal(last_downtime_seconds),
            "updated_at": _now_iso(),
        }
        self._table(DYNAMODB_TABLE_VM_STATE).put_item(Item=item)
        return item

    def update_vm_state(self, vm_id: str, **fields) -> None:
        """Partial update of a VM state record (keyed by instance_id)."""
        unknown = set(fields) - self.VM_STATE_FIELDS
        if unknown:
            raise ValueError(f"Unknown vm-state field(s): {sorted(unknown)}")
        if not fields:
            return

        fields = dict(fields, updated_at=_now_iso())
        expr_parts = ", ".join(f"#{k}=:v_{k}" for k in fields)
        self._table(DYNAMODB_TABLE_VM_STATE).update_item(
            Key={"instance_id": vm_id},
            UpdateExpression=f"SET {expr_parts}",
            ExpressionAttributeNames={f"#{k}": k for k in fields},
            ExpressionAttributeValues={f":v_{k}": _as_decimal(v) for k, v in fields.items()},
        )

    def get_vm_state(self, vm_id: str) -> dict | None:
        """Return the (strongly consistent) state for a VM instance, or None."""
        resp = self._table(DYNAMODB_TABLE_VM_STATE).get_item(
            Key={"instance_id": vm_id}, ConsistentRead=True,
        )
        return resp.get("Item")

    def delete_vm_state(self, vm_id: str) -> None:
        self._table(DYNAMODB_TABLE_VM_STATE).delete_item(Key={"instance_id": vm_id})

    # ── checkpoint tracking (stored in the VM's state row) ─────────────────
    def record_checkpoint(
        self,
        vm_id: str,
        run_id: str,
        last_processed_index: int,
        timestamp: str | None = None,
        s3_key: str | None = None,
    ) -> None:
        """
        Record a checkpoint against the VM's state row. UpdateItem creates the
        item if the VM has no row yet, so checkpoints are durable even if no
        other VM state was written first.
        """
        ts = timestamp or _now_iso()
        update = {
            "run_id": run_id,
            "last_processed_index": _as_decimal(last_processed_index),
            "last_checkpoint_timestamp": ts,
            "updated_at": _now_iso(),
        }
        if s3_key:
            update["last_checkpoint_key"] = s3_key

        expr_parts = ", ".join(f"#{k}=:v_{k}" for k in update)
        self._table(DYNAMODB_TABLE_VM_STATE).update_item(
            Key={"instance_id": vm_id},
            UpdateExpression=f"SET {expr_parts}",
            ExpressionAttributeNames={f"#{k}": k for k in update},
            ExpressionAttributeValues={f":v_{k}": v for k, v in update.items()},
        )

    # ── migration history (chrononet-migrations, run_id + timestamp) ────────
    def record_migration(
        self,
        run_id: str,
        from_vm_id: str,
        to_vm_id: str,
        triggered_by: str = "prediction",
        risk_percent: float = 0.0,
        downtime_seconds: float = 0.0,
        status: str = "started",
        checkpoint_key: str | None = None,
        timestamp: str | None = None,
    ) -> str:
        """
        Log a migration event. Returns the timestamp used as the sort key
        (use it later with complete_migration / delete_migration).
        """
        ts = timestamp or _now_iso()
        item = {
            "run_id": run_id,
            "timestamp": ts,            # table SORT key (ISO8601, sortable)
            "from_vm_id": from_vm_id,
            "to_vm_id": to_vm_id,
            "triggered_by": triggered_by,
            "risk_percent": _as_decimal(risk_percent),
            "downtime_seconds": _as_decimal(downtime_seconds),
            "status": status,
        }
        if checkpoint_key:
            item["checkpoint_key"] = checkpoint_key
        self._table(DYNAMODB_TABLE_MIGRATIONS).put_item(Item=item)
        return ts

    def complete_migration(
        self, run_id: str, timestamp: str, status: str = "completed",
    ) -> None:
        """Mark a migration completed/failed and stamp completed_at."""
        self.update_migration(
            run_id, timestamp, status=status, completed_at=_now_iso(),
        )

    def update_migration(self, run_id: str, timestamp: str, **fields) -> None:
        """Partial update of a migration record. Only known fields are accepted."""
        allowed = {
            "from_vm_id", "to_vm_id", "triggered_by", "risk_percent",
            "downtime_seconds", "status", "checkpoint_key", "checkpoint_index",
            "resumed_index", "provision_market", "timeline", "completed_at",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown migration field(s): {sorted(unknown)}")
        if not fields:
            return

        expr_parts = ", ".join(f"#{k}=:v_{k}" for k in fields)
        self._table(DYNAMODB_TABLE_MIGRATIONS).update_item(
            Key={"run_id": run_id, "timestamp": timestamp},
            UpdateExpression=f"SET {expr_parts}",
            ExpressionAttributeNames={f"#{k}": k for k in fields},
            ExpressionAttributeValues={f":v_{k}": _as_decimal(v) for k, v in fields.items()},
        )

    def list_migrations(self, run_id: str) -> list[dict]:
        """Migration history for a run, most recent first."""
        resp = self._table(DYNAMODB_TABLE_MIGRATIONS).query(
            KeyConditionExpression=Key("run_id").eq(run_id),
            ScanIndexForward=False,     # returns newest first (sort key = timestamp)
            ConsistentRead=True,
        )
        return resp.get("Items", [])

    def delete_migration(self, run_id: str, timestamp: str) -> None:
        self._table(DYNAMODB_TABLE_MIGRATIONS).delete_item(
            Key={"run_id": run_id, "timestamp": timestamp},
        )


def self_check(db: DynamoDBClient) -> int:
    """Write/read a temporary record in both tables to prove connectivity."""
    vm_a, vm_b = "self-check-vm-a", "self-check-vm-b"
    run_id = f"self-check-{vm_a}"
    print(f"[self-check] Tables: {db.ensure_tables() or '[already exist]'}")
    print(f"[self-check] run_id={run_id}, vm_a={vm_a}, vm_b={vm_b}")
    try:
        # 1. VM state write/read
        db.put_vm_state(
            vm_id=vm_a, run_id=run_id, cpu_percent=42.5, ram_percent=61.25,
            risk_percent=7.5, status="running",
        )
        got = db.get_vm_state(vm_a)
        assert got is not None, "get_vm_state returned None after put"
        assert got["run_id"] == run_id and got["vm_id"] == vm_a
        assert abs(float(got["cpu_percent"]) - 42.5) < 1e-9
        print("[self-check] vm-state: put + get OK")

        # 2. Checkpoint tracking write/read
        db.record_checkpoint(
            vm_id=vm_a, run_id=run_id, last_processed_index=12,
            s3_key="checkpoints/self-check/latest.json",
        )
        got2 = db.get_vm_state(vm_a)
        assert int(got2["last_processed_index"]) == 12
        assert got2["last_checkpoint_key"] == "checkpoints/self-check/latest.json"
        print("[self-check] checkpoint: record_checkpoint + read-back OK")

        # 3. Migration history write/read
        ts = db.record_migration(
            run_id=run_id, from_vm_id=vm_a, to_vm_id=vm_b,
            triggered_by="prediction", risk_percent=87.5, downtime_seconds=2.5,
            checkpoint_key="checkpoints/self-check/latest.json",
        )
        db.complete_migration(run_id, ts, status="completed")
        migs = db.list_migrations(run_id)
        assert migs and migs[0]["timestamp"] == ts
        assert migs[0]["status"] == "completed"
        print("[self-check] migration: record + complete + list OK")

        print("[self-check] SUCCESS: DynamoDB connected and write/read verified.")
        return 0
    finally:
        # Always clean up the temporary records.
        db.delete_vm_state(vm_a)
        if "ts" in locals():
            db.delete_migration(run_id, ts)
        print("[self-check] Cleaned up temporary records.")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="ChronoNet DynamoDB client tools")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Create tables if needed, then write/read a temporary test record in both.",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create the ChronoNet DynamoDB tables if they don't exist.",
    )
    args = parser.parse_args(argv)

    if args.create_tables:
        try:
            created = DynamoDBClient().ensure_tables()
        except Exception as e:
            print(f"[main] ERROR creating tables: {type(e).__name__}: {e}")
            return 1
        print(f"[main] Tables ready. Created: {created or 'none (already exist)'}")
        return 0

    if args.self_check:
        try:
            return self_check(DynamoDBClient())
        except Exception as e:
            print(f"[main] ERROR during self-check: {type(e).__name__}: {e}")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())