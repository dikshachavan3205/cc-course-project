# ChronoNet

AI-Driven Predictive Spot VM Migration Framework.

## Setup
1. Copy `.env.example` to `.env` and fill in your AWS region, bucket names, table names.
2. Each module (`app/`, `orchestration/`, `monitoring/`, `prediction/`, `data_backend/`, `dashboard/`) has its own `requirements.txt` / `package.json`.
3. See `docs/execution_guide.md` for the full build order.
4. See `shared/contracts.md` before writing any code that crosses module boundaries.
