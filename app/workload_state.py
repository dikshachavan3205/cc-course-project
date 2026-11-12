"""Deterministic workload state: a hash chain over the processed steps.

Each processed step folds into a SHA-256 chain, so the state after N steps is a
pure function of N. That makes migration continuity *verifiable*: any
checkpoint's checksum must equal expected_checksum(its last_processed_index),
no matter how many instances the work passed through. A resume that lost data,
or restarted from scratch with a wrong index, produces a mismatch.

Python 3.9-safe (runs on the stock Amazon Linux 2023 interpreter).
"""
from __future__ import annotations

import hashlib

GENESIS = hashlib.sha256(b"chrononet-genesis").hexdigest()


def initial_state() -> dict:
    return {"processed_count": 0, "checksum": GENESIS}


def advance(state: dict, step: int) -> dict:
    digest = hashlib.sha256(f"{state['checksum']}:{step}".encode()).hexdigest()
    return {"processed_count": state["processed_count"] + 1, "checksum": digest}


def state_at(n: int) -> dict:
    """State after steps 0..n-1 have been processed."""
    state = initial_state()
    for i in range(n):
        state = advance(state, i)
    return state


def expected_checksum(n: int) -> str:
    return state_at(n)["checksum"]


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(expected_checksum(n))
