"""Timestamped step logger for the migration orchestrator.

Emits one line per step with:
  - wall-clock UTC timestamp (ISO8601)
  - elapsed time in ms since the logger was created (monotonic — for downtime)

Keeps a structured `timeline` list that the orchestrator can store in DynamoDB.

Logs go to STDERR so STDOUT stays clean for machine-readable output (the CLI
prints the final result JSON to STDOUT).
"""

import json
import sys
import time
from datetime import datetime, timezone


class StepLogger:
    def __init__(self, owner: str = "migrate", run_id: str | None = None):
        self.owner = owner
        self.run_id = run_id
        self._t0_wall = datetime.now(timezone.utc)
        self._t0_mono = time.monotonic()
        self.timeline: list[dict] = []
        self._step_count = 0

    @property
    def t0_utc(self) -> str:
        return self._t0_wall.isoformat()

    def elapsed_ms(self) -> float:
        """Milliseconds since the workflow started (monotonic clock)."""
        return (time.monotonic() - self._t0_mono) * 1000.0

    def step(self, name: str, **fields) -> dict:
        """Log a workflow step and append it to the timeline."""
        self._step_count += 1
        entry = {
            "step": f"{self._step_count:02d}",
            "name": name,
            "at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": round(self.elapsed_ms(), 1),
            **fields,
        }
        line = (f"[{self.owner}:{self.run_id}] {entry['at_utc']} "
                f"+{entry['elapsed_ms']:>10.1f}ms  {name}")
        if fields:
            line += "  " + json.dumps(fields, default=str)
        print(line, file=sys.stderr)
        self.timeline.append(entry)
        return entry

    def note(self, name: str, **fields) -> dict:
        """Log a non-step detail (sub-event) without bumping the step counter."""
        entry = {
            "step": "note",
            "name": name,
            "at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_ms": round(self.elapsed_ms(), 1),
            **fields,
        }
        line = (f"[{self.owner}:{self.run_id}] {entry['at_utc']} "
                f"+{entry['elapsed_ms']:>10.1f}ms  | {name}")
        if fields:
            line += "  " + json.dumps(fields, default=str)
        print(line, file=sys.stderr)
        self.timeline.append(entry)
        return entry