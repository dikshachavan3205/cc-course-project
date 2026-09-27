# ChronoNet — AI-Driven Predictive Spot VM Migration Framework

ChronoNet predicts AWS Spot Instance interruptions before they happen and automatically migrates a running workload to a fresh instance — checkpointing progress to S3, restoring it on the replacement, and keeping a live dashboard, alerting, and history trail of everything that happened.

This README tracks progress against the project's own 16-phase execution plan (`CC-Project-Documentation` — Phases 0–15). Status below is taken from the project's live-AWS phase audit (`docs/phase_audit.md`) and the current state of the codebase, not just the original plan — so it reflects what's actually built and verified, including known gaps.

**Status legend:** ✅ Done & verified · ⚠️ Done with caveats · ◻ Not started / out of scope for now

---

## Phase 0 — Team & Environment Setup

**Status: ⚠️ Done with caveats**

- `.env.example` aligned to the actual `CHRONONET_*` variables the code reads.
- `numpy` added to `prediction/requirements.txt`; a stale, unused `requests` entry removed.
- Regenerable dataset directories (`prediction/dataset/raw/`, `processed/`) gitignored so they don't bloat the repo.
- Caveat: `docker-compose.yml` at the repo root is **not functional** — it references Dockerfiles for `data_backend/` and `dashboard/` that don't exist. Only `app/` has a working Dockerfile. Backend and dashboard are run directly (`uvicorn`, `npm run dev`), not containerized. See `setup.md` for the actual run process.

## Phase 1 — AWS Account & IAM Setup

**Status: ⚠️ Done, scope decision documented**

- IAM role `chrononet-ec2-role` (+ instance profile) exists, trusts EC2 only. Zero hardcoded credentials anywhere in the codebase.
- Attached policies are 4 **AWS-managed** policies: `AmazonS3FullAccess`, `AmazonDynamoDBFullAccess`, `AmazonSNSFullAccess`, `CloudWatchReadOnlyAccess` — scoped to the right *services* (no EC2 or EventBridge access) but not resource-scoped.
- **Documented decision:** left as-is to avoid destabilizing a working, tested role close to demo day. A resource-scoped custom policy is a documented future improvement, not a functional gap.

## Phase 2 — Dataset Collection & Preparation

**Status: ✅ Done & verified**

- Real fetchers pull spot price history and interruption-rate data: **2,536 real price rows** across **34 regions / 1,155 instance types**.
- Synthetic training data generated on top of real interruption-rate statistics (`prediction/dataset/generate_synthetic_data.py`).
- Cleaned dataset: **400 rows, 0 NaN / negative / duplicate values**.
- Train/test split uses a fixed seed (42) for reproducibility.

## Phase 3 — Docker Containerization

**Status: ✅ Done & verified**

- `app/Dockerfile` builds the simulated workload container — **258 MB** image.
- Verified: runs to completion, and a volume-persisted checkpoint was confirmed to resume correctly at step 17 rather than restarting from zero.
- Caveat: this containerization exists for `app/` only — `data_backend` and `dashboard` are not (yet) containerized (see Phase 0 caveat).

## Phase 4 — Checkpointing to S3

**Status: ✅ Done & verified**

- Checkpoint key pattern: `checkpoints/{run_id}/{timestamp}.json`.
- Load-latest-checkpoint logic verified against real S3.
- S3 **lifecycle rule added**: checkpoint objects expire after 14 days (verified via `get-bucket-lifecycle-configuration`).
- **Bug found + fixed during real E2E testing:** `load_latest_checkpoint_from_s3` originally picked the lexicographically max key under a run's S3 prefix and blindly parsed it as JSON. A non-checkpoint artifact (probe logs) under the same prefix crashed recovery with a `JSONDecodeError`. Fixed by filtering to `*.json` keys only before selecting "latest."

## Phase 5 — Monitoring Setup

**Status: ✅ Done & verified (including a real live-instance test)**

- `cloudwatch_collector` implemented: pulls **real CPUUtilization** from CloudWatch (RAM stays explicit `None` by design — not available from CloudWatch without a custom agent).
- `imds_watcher` polls the Instance Metadata Service (IMDSv2, token-based) for spot interruption notices — **verified on a live EC2 instance**, correctly reporting "no interruption notice detected" under normal conditions (no false positives).
- **EventBridge rule deployed for real**: `chrononet-spot-interruption-rule`, state `ENABLED`, listening for `EC2 Spot Instance Interruption Warning` events, targeting the SNS alerts topic. Verified via `events:describe-rule` and `events:list-targets-by-rule`.

## Phase 6 — Prediction Model

**Status: ✅ Model trained & evaluated — ◻ trained artifact not committed**

- Random Forest baseline trained and compared against XGBoost on the same 400-row dataset and feature set.
- Final model (XGBoost): **MAE 0.0207, R² 0.8828** against the held-out test set.
- Risk output is clamped to a strict `(0, 1)` range and exposed behind a single wrapped function; the "high risk" threshold is a shared, configurable constant (`RISK_THRESHOLD`), not hardcoded inline.
- Caveat: the trained model file (`prediction/model/risk_model.pkl`) is intentionally gitignored, so a fresh clone doesn't have it. Without it, the backend logs a warning and returns `risk_percent: 0` — it degrades gracefully rather than crashing. Run `prediction/train_model.py` to produce it locally.

## Phase 7 — Data & State Tracking Setup (DynamoDB)

**Status: ✅ Done & verified**

- Live self-check confirms tables exist and are reachable.
- Field names and types match the shared contracts used by the backend API.
- History endpoint supports filtering and sorting by run.

## Phase 8 — Orchestration & Recovery Logic

**Status: ✅ Done & verified with a real end-to-end AWS test**

Full real E2E run (`run-e2e-real`, t3.micro, region `ap-south-1`):

1. Primary Spot instance `i-0669a3f5474513ba2` launched, running the real workload, checkpointing to S3 every 5s.
2. Migration triggered — forced checkpoint (hub local index 2) → provisioned replacement Spot instance `i-0f9c1e24f72a89e74` → downloaded latest S3 checkpoint and **resumed at index 30027** (real workload progress, not 0, not the forced hub value) → terminated the original instance → SNS alert published.
3. **Measured downtime: 6.906 seconds** (trigger receipt → resume complete).
4. Also implemented: idempotent instance termination, and automatic Spot → On-Demand fallback if a Spot replacement can't be provisioned.

Caveat on migration count: this is currently **one** fully measured real-AWS migration run, plus one local Docker-only resume test (no real migration). Additional runs via the simulated `test-migration --provision` path are recommended before finalizing a "tested across N runs" claim in the report.

## Phase 9 — Notifications (SNS)

**Status: ✅ Done & verified**

- SNS topic ARN is derived at runtime, never hardcoded.
- Subscription confirmed; a real test alert was delivered.
- Orchestration publishes to this topic on migration completion (confirmed in the Phase 8 E2E run above).

## Phase 10 — Backend API

**Status: ✅ Done & verified**

- FastAPI backend (`data_backend/`) exposes `/status`, `/history`, `/checkpoint-status`, `/migrations`, `/health`.
- Endpoint response shapes and empty-data cases verified.
- CORS currently open (`*`) via `CHRONONET_CORS_ORIGINS` — fine for local/demo use, worth tightening for anything beyond that.
- All AWS calls inside the API are wrapped so a missing/denied AWS permission logs a warning and returns safe defaults instead of crashing the endpoint.

## Phase 11 — Dashboard

**Status: ✅ Done & verified**

- React + Vite dashboard polls `/status` every 5s and `/history` every 10s — confirmed against a live backend via request-log inspection, not just assumed from code.
- Displays VM status, live risk %, checkpoint status, and migration history.
- Includes a **Demo Data** toggle in Settings, so the dashboard can display realistic synthetic data if AWS reads are failing (useful for local dev and as a live-demo fallback).

## Phase 12 — Simulated Interruption Trigger

**Status: ✅ Done**

- The dashboard's `/simulate` page and the backend's `test-migration` script trigger the exact same orchestration path a real interruption would — not a separate mocked path — so a manual demo trigger genuinely proves the real system works.

## Phase 13 — Full System Integration Testing

**Status: ⚠️ Partially done**

- One full real-AWS E2E pass completed and verified (see Phase 8) — checkpoint → migrate → resume → terminate → alert, all consistent with DynamoDB records and dashboard display.
- Not yet done: extended continuous run over a longer period, deliberate no-Spot-capacity edge case, repeated back-to-back interruptions to confirm zero cumulative progress loss across multiple runs. Recommended before final submission if time allows.

## Phase 14 — Cost & Cleanup Check

**Status: ✅ Verified after the real E2E test**

- Post-test check confirmed no orphaned instances: account-wide `running,pending` EC2 query returned `[]` after the E2E test.
- S3 lifecycle rule (Phase 4) confirmed active for ongoing checkpoint cleanup.

## Phase 15 — Documentation & Demo Preparation

**Status: ⚠️ In progress**

- Measured results, edge cases, and a full demo runbook (script, rehearsal checklist, fallback plan) are written up — see `docs/demo-runbook.md` (also available as a Word doc).
- Still to do: the team dry-run itself, a recorded backup video of a successful run, and folding the deviations list below into the final requirements/report document.

---

## Known Deviations From the Original Plan (for the report)

- **IAM:** resource-level least privilege not implemented — service-level scoping only (see Phase 1).
- **Docker:** only `app/` is containerized; `docker-compose.yml` is aspirational, not functional (see Phase 0/3).
- **Stubs left out of scope:** `metrics_buffer.py` and `prediction/evaluate.py` remain one-line stubs.
- **Minor:** `AWS_REGION` is defined twice in `shared/constants.py` (harmless duplication).

## Getting Started

See [`setup.md`](./setup.md) for the full local setup and run instructions (prerequisites, dependency install, running the backend and dashboard, optional AWS credential setup, and troubleshooting).