"""Pydantic models — defines the shared API response / event shapes.

Every model here mirrors shared/contracts.md EXACTLY (same field names and
types), so the API layer and any consumer stay in lockstep with the contract.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class StatusResponse(BaseModel):
    """GET /status response — shape #2 in shared/contracts.md."""

    run_id: str
    vm_id: str
    region: str
    cpu_percent: float
    ram_percent: float
    risk_percent: float
    migration_count: int
    last_downtime_seconds: float


class RiskEvent(BaseModel):
    """High-risk event (Predictor / IMDS watcher -> Orchestrator) — shape #3."""

    run_id: str
    vm_id: str
    risk_percent: float = Field(ge=0, le=100)
    threshold_exceeded: bool
    timestamp: str  # ISO8601

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_iso8601(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"timestamp must be ISO8601, got {value!r}"
            ) from exc
        return value


class InterruptionResponse(BaseModel):
    """Orchestrator's answer to a received high-risk event."""

    run_id: str
    from_vm_id: str
    to_vm_id: str
    migration_id: str
    status: str
    checkpoint_key: str | None = None
    downtime_seconds: float
    timeline: list[dict] | None = None