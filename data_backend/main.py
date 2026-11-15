"""ChronoNet orchestration hub (FastAPI) — the unified API for the whole system.

Endpoints (contracts in shared/contracts.md):
  GET  /status         Current run/VM state + metrics (shape #2)
  GET  /history        Migration history for a run from chrononet-migrations
  POST /interruption   High-risk event (shape #3) -> triggers the real
                       orchestration/recovery_flow workflow, records state
                       changes, then returns the migration summary
  GET  /health         Liveness + endpoint directory
  GET  /               Endpoint directory listing

Hardening guarantees:
  * Every DynamoDB read is wrapped so a missing row, missing table, throttle,
    or offline AWS never turns into a 500 — the endpoint returns contract-valid
    defaults and falls back to prediction/predict.py where sensible.
  * POST /interruption validates the payload against the RiskEvent schema
    (422 on malformed/out-of-range input) and delegates to the real migration
    workflow; a failed workflow still returns a contract-valid body with
    status="failed" instead of a bare 500.
  * CORS is enabled (origin list configurable via CHRONONET_CORS_ORIGINS,
    default "*") so any local frontend or test script can call it.

Run locally:
  python -m uvicorn data_backend.main:app --reload --port 8000

Verify:
  python data_backend/smoke_test.py        (spins up its own server on :8001)
"""

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from data_backend.aws.dynamodb_client import DynamoDBClient  # noqa: E402
from data_backend.models.schemas import (  # noqa: E402
    InterruptionResponse,
    RiskEvent,
    StatusResponse,
)
from orchestration.recovery_flow import run_migration  # noqa: E402
from shared.constants import (  # noqa: E402
    AWS_REGION, CHECKPOINT_INTERVAL_SECONDS, INSTANCE_TYPE, RISK_THRESHOLD, RISK_THRESHOLD_WARN,
)

# Optional integration: predict risk from live telemetry when the VM-state row
# is missing or has no risk_percent yet. Guarded so the API works without ML deps.
try:
    from prediction.predict import predict_risk
except Exception:  # pragma: no cover - ML deps optional at runtime
    predict_risk = None
try:
    from prediction.features import live_features
except Exception:  # pragma: no cover
    live_features = None


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "").lower() in {"true", "1", "yes"}


def _allow_real_ec2() -> bool:
    return _env_bool("CHRONONET_ALLOW_REAL_EC2")


def _provision_mode() -> str:
    """'real' only when BOTH CHRONONET_PROVISION_MODE=real and CHRONONET_ALLOW_REAL_EC2=true."""
    if os.environ.get("CHRONONET_PROVISION_MODE", "").lower() == "real" and _allow_real_ec2():
        return "real"
    return "simulate"


def _resolve_current(run_id, vm_id):
    """Explicit ids win; otherwise the newest live REAL instance (has a market) in vm-state."""
    if run_id and vm_id:
        return run_id, vm_id
    try:
        rows = [r for r in DynamoDBClient().list_vm_states(run_id)
                if r.get("market") and r.get("status") in ("running", "launching", "migrating")]
    except Exception as e:  # noqa: BLE001
        print(f"[orchestrator] WARNING: list_vm_states failed: {type(e).__name__}: {e}")
        rows = []
    if rows:
        rows.sort(key=lambda r: (r.get("status") == "running", str(r.get("launched_at") or "")), reverse=True)
        top = rows[0]
        return top.get("run_id") or run_id or _current["run_id"], top["instance_id"]
    return run_id or _current["run_id"], vm_id or _current["vm_id"]


# In-process reflection of the "current" VM for this demo hub. Durable truth
# lives in DynamoDB; this cache keeps /status coherent right after a migration,
# and is the last-resort fallback if DynamoDB is temporarily unreachable.
_current = {
    "run_id": _env("CHRONONET_RUN_ID", "run-local-dev"),
    "vm_id": _env("CHRONONET_VM_ID", "vm-local-dev"),
    "migration_count": 0,
    "last_downtime_seconds": 0.0,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort: make sure the DynamoDB tables exist before serving.
    try:
        created = DynamoDBClient().ensure_tables()
        print(f"[orchestrator] DynamoDB ready (created: {created or 'none needed'}).")
    except Exception as e:  # pragma: no cover
        print(f"[orchestrator] WARNING: could not ensure DynamoDB tables: {e}")
    yield


app = FastAPI(
    title="ChronoNet Orchestration Hub",
    description="Predicts, detects, and migrates EC2 Spot workloads with zero progress loss.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow_origins=["*"] by default (dev); pin domains via
# CHRONONET_CORS_ORIGINS="https://ui.example.com,http://localhost:5173".
_cors_origins = [
    o.strip() for o in _env("CHRONONET_CORS_ORIGINS", "*").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,  # must stay False while allow_origins includes "*"
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── resilience helpers ──────────────────────────────────────────────────────
def _safe_get_vm_state(vm_id: str) -> dict | None:
    """
    Fetch a VM-state row. Returns a dict on success, None when the row or
    the table is missing/unreachable — callers build graceful defaults.
    """
    try:
        row = DynamoDBClient().get_vm_state(vm_id)
        return row if row else None
    except Exception as e:  # noqa: BLE001 - never let AWS hiccups reach the client
        print(f"[orchestrator] WARNING: get_vm_state({vm_id}) failed: {type(e).__name__}: {e}")
        return None


def _normalize_number(value, default: float = 0.0) -> float:
    """float()-cast with None guard (DynamoDB rows pass Decimals)."""
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _normalize_migration(item: dict) -> dict:
    """Convert a raw DynamoDB item into JSON-safe values (Decimals -> int/float)."""
    out = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            v = int(v) if v == v.to_integral_value() else float(v)
        out[k] = v
    return out


def _build_status(run_id: str, vm_id: str) -> dict:
    """
    Pull the VM-state record from DynamoDB, then merge with a live prediction
    when the row is missing or carries no risk measurement yet. Always returns
    the full contract shape #2 — never raises.
    """
    row = _safe_get_vm_state(vm_id)

    cpu_percent = _normalize_number(row.get("cpu_percent")) if row else 0.0
    ram_percent = _normalize_number(row.get("ram_percent")) if row else 0.0
    risk_percent = _normalize_number(row.get("risk_percent")) if row else 0.0

    # Fallback to the ML model when we have no measured risk (row missing or
    # risk_percent still 0) — predict.py returns a 0-100 percentage.
    needs_prediction = row is None or risk_percent == 0.0
    if needs_prediction and predict_risk is not None:
        try:
            if row is None:
                network_mbps, age_minutes = 0.0, 30
            else:
                network_mbps = _normalize_number(row.get("network_mbps"))
                age_minutes = int(
                    _normalize_number(row.get("instance_age_minutes"), default=30.0)
                    or 30.0)
            itype = (row or {}).get("instance_type")
            if itype and live_features is not None:
                # real instance: live price features, same as the monitor loop
                risk_percent = round(predict_risk(**live_features(itype, row)), 2)
            else:
                risk_percent = round(predict_risk(
                    instance_type=INSTANCE_TYPE,
                    cpu_percent=cpu_percent,
                    ram_percent=ram_percent,
                    network_mbps=network_mbps,
                    instance_age_minutes=age_minutes,
                ), 2)
        except Exception as e:  # noqa: BLE001
            print(f"[orchestrator] WARNING: predict_risk failed: {e}")

    migration_count = max(
        int(_normalize_number(row.get("migration_count"))) if row else 0,
        _current["migration_count"],
    )
    downtime = max(
        _normalize_number(row.get("last_downtime_seconds")) if row else 0.0,
        _current["last_downtime_seconds"],
    )

    return StatusResponse(
        run_id=run_id,
        vm_id=vm_id,
        region=AWS_REGION,
        cpu_percent=cpu_percent,
        ram_percent=ram_percent,
        risk_percent=risk_percent,
        migration_count=migration_count,
        last_downtime_seconds=round(downtime, 3),
        instance_type=(row or {}).get("instance_type"),
        market=(row or {}).get("market"),
        vm_status=(row or {}).get("status"),
    ).model_dump()


@app.get("/")
def root():
    return {
        "service": "ChronoNet Orchestration Hub",
        "version": app.version,
        "endpoints": ["/status", "/history", "/checkpoint-status", "/interruption", "/health"],
        "docs": "/docs",
    }


@app.get("/status", response_model=StatusResponse)
def get_status(
    run_id: str = Query(default=None, description="Defaults to CHRONONET_RUN_ID / run-local-dev."),
    vm_id: str = Query(default=None, description="Defaults to CHRONONET_VM_ID / vm-local-dev."),
):
    """Current VM state + metrics, exactly matching contract shape #2."""
    run_id, vm_id = _resolve_current(run_id, vm_id)
    return _build_status(run_id, vm_id)


@app.get("/predictions")
def get_predictions(run_id: str = Query(default=None), limit: int = 120):
    """Risk history for a run (newest first) from chrononet-predictions."""
    run_id, _ = _resolve_current(run_id, None)
    body = {"run_id": run_id, "predictions": []}
    try:
        body["predictions"] = [_normalize_migration(r) for r in DynamoDBClient().list_predictions(run_id, limit)]
    except Exception as e:  # noqa: BLE001 - table may not exist until the monitor first runs
        print(f"[orchestrator] WARNING: list_predictions failed: {type(e).__name__}: {e}")
        body["warning"] = f"{type(e).__name__}: {e}"
    return body


@app.get("/instances")
def get_instances(run_id: str = Query(default=None)):
    """Every instance this run has used (newest first)."""
    run_id, _ = _resolve_current(run_id, None)
    try:
        rows = DynamoDBClient().list_vm_states(run_id)
    except Exception as e:  # noqa: BLE001
        print(f"[orchestrator] WARNING: list_vm_states failed: {type(e).__name__}: {e}")
        rows = []
    keys = ("instance_id", "status", "instance_type", "market", "launched_at",
            "resumed_index", "last_processed_index", "risk_percent")
    out = [{k: _normalize_migration(r).get(k) for k in keys} for r in rows]
    out.sort(key=lambda r: str(r.get("launched_at") or ""), reverse=True)
    return {"run_id": run_id, "instances": out}


@app.get("/config")
def get_config():
    """Thresholds and mode the dashboard should display (single source of truth)."""
    return {
        "risk_warn_percent": round(RISK_THRESHOLD_WARN * 100, 2),
        "risk_migrate_percent": round(RISK_THRESHOLD * 100, 2),
        "provision_mode": _provision_mode(),
        "checkpoint_interval_s": int(os.environ.get("CHRONONET_CHECKPOINT_INTERVAL", 10)),
        "region": AWS_REGION,
    }


@app.get("/history")
def get_history(run_id: str):
    """
    Chronological migration history for a run, straight from the
    chrononet-migrations table (newest first). Graceful empty on AWS errors.
    """
    try:
        rows = DynamoDBClient().list_migrations(run_id)
        migrations = [_normalize_migration(r) for r in rows]
    except Exception as e:  # noqa: BLE001 - degrade gracefully, never 500
        print(f"[orchestrator] WARNING: list_migrations({run_id}) failed: {type(e).__name__}: {e}")
        migrations = []
        warning = f"{type(e).__name__}: {e}"
    else:
        warning = None
    body = {"run_id": run_id, "migrations": migrations}
    if warning:
        body["warning"] = warning
    return body


@app.get("/checkpoint-status")
def checkpoint_status(run_id: str):
    """
    Most recent checkpoint for a run — the latest object under
    checkpoints/{run_id}/ in S3 (chrononet-checkpoints). Returns a valid JSON
    body with found=false when there is nothing yet or AWS is unreachable.
    """
    body = {
        "run_id": run_id,
        "found": False,
        "last_processed_index": None,
        "vm_id": None,
        "timestamp": None,
        "s3_key": None,
    }
    try:
        from app.checkpoint_manager import _s3_key_for, load_latest_checkpoint_from_s3
        cp = load_latest_checkpoint_from_s3(run_id)
        if cp:
            body.update({
                "found": True,
                "last_processed_index": int(cp["last_processed_index"]),
                "vm_id": cp.get("vm_id"),
                "timestamp": cp.get("timestamp"),
                "s3_key": _s3_key_for(run_id, cp["timestamp"]),
            })
    except Exception as e:  # noqa: BLE001 - never 500 on AWS hiccups
        print(f"[orchestrator] WARNING: checkpoint-status lookup failed "
              f"({type(e).__name__}: {e})")
        body["warning"] = f"{type(e).__name__}: {e}"
    return body


@app.post("/interruption", response_model=InterruptionResponse)
def on_interruption(
    event: RiskEvent,
    x_chrononet_trigger: str = Header(default="imds", alias="X-ChronoNet-Trigger"),
):
    """
    Orchestration entry point for a high-risk event (shape #3).

    Delegates to orchestration/recovery_flow.run_migration() — the real,
    7-step workflow (checkpoint -> S3, migration log, spot provision w/
    on-demand fallback, checkpoint restore, boot+health, terminate old VM,
    SNS alert) — then returns the migration summary.

    Graceful behaviors:
      * threshold_exceeded=False  -> status "noop", nothing migrates.
      * run_migration() itself fails -> contract-valid body with status "failed"
        (no bare 500).
    """
    event_dict = event.model_dump()

    if not event.threshold_exceeded:
        print(f"[orchestrator] Risk {event.risk_percent} below threshold — no migration.")
        return InterruptionResponse(
            run_id=event.run_id,
            from_vm_id=event.vm_id,
            to_vm_id=event.vm_id,
            migration_id="none",
            status="noop",
            checkpoint_key=None,
            downtime_seconds=0.0,
        )

    try:
        result = run_migration(
            event=event_dict,
            provision_mode=_provision_mode(),   # real only if PROVISION_MODE=real AND ALLOW_REAL_EC2=true
            allow_real_ec2=_allow_real_ec2(),
            dry_run=False,
            triggered_by=x_chrononet_trigger or "imds",
        )
    except Exception as e:  # noqa: BLE001 - degrade to a graceful response
        print(f"[orchestrator] ERROR: run_migration failed ({type(e).__name__}: {e})")
        return InterruptionResponse(
            run_id=event.run_id,
            from_vm_id=event.vm_id,
            to_vm_id=event.vm_id,
            migration_id="failed",
            status="failed",
            checkpoint_key=None,
            downtime_seconds=0.0,
        )

    status = result["status"]
    to_vm_id = result.get("to_vm_id") or event.vm_id
    migration_id = result.get("migration_id") or "none"
    downtime = round(float(result.get("downtime_seconds") or 0.0), 3)

    if status.startswith("completed"):
        # Keep the in-memory cache coherent with the durable record.
        _current.update({
            "vm_id": to_vm_id,
            "migration_count": _current["migration_count"] + 1,
            "last_downtime_seconds": downtime,
        })
        print(f"[orchestrator] Migration {migration_id} complete: "
              f"{event.vm_id} -> {to_vm_id} (downtime {downtime}s, status={status}).")

    return InterruptionResponse(
        run_id=event.run_id,
        from_vm_id=event.vm_id,
        to_vm_id=to_vm_id,
        migration_id=migration_id,
        status=status,
        checkpoint_key=result.get("checkpoint_key"),
        downtime_seconds=downtime,
        timeline=result.get("steps"),
    )


@app.get("/health")
def health():
    return {"status": "ok", "region": AWS_REGION, "time": _now_iso()}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("data_backend.main:app", host="127.0.0.1", port=8000, reload=False)