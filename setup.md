# ChronoNet — Setup & Run Guide

Full step-by-step flow to get the project running locally, from a fresh clone/zip to a working backend + dashboard.

---

## 0. Important things to know before you start

- **Don't use `docker-compose up`.** The `docker-compose.yml` at the repo root references Dockerfiles for `data_backend/` and `dashboard/` that don't exist in this repo — only `app/` has a working Dockerfile. Run the backend and dashboard directly instead (covered below).
- **AWS credentials are optional.** Every AWS call (S3, DynamoDB, SNS, EC2) is wrapped so it fails gracefully and just logs a warning if credentials are missing or lack permissions. You can run and demo the whole app without any AWS account at all — you just won't get real telemetry/history.
- **No `.env` auto-loading.** Nothing in the codebase uses `python-dotenv`. A `.env` file only matters if you use `docker-compose` (which you're not). Running things directly with `python` / `uvicorn` never reads `.env` automatically — every setting already has a safe default in `shared/constants.py`.
- **AWS keys never go in `.env`.** If you do want real AWS features working, credentials go in `~/.aws/credentials` (via `aws configure`) or as real shell environment variables — never in this project's `.env` file, and never in `.env.example` (that file is meant to be committed to git).

---

## 1. Prerequisites

| Tool | Version | Why |
| --- | --- | --- |
| Python | 3.10+ | Codebase uses `str \| None` type hints (3.10 syntax) |
| Node.js | 18+ | Dashboard uses Vite 5 / React 18 |
| npm | comes with Node | Dashboard package manager |
| Git | any recent | Only needed if cloning fresh instead of unzipping |
| AWS CLI (optional) | any recent | Only if you want real AWS features |

---

## 2. Get the project

```bash
# If you have the zip:
unzip cc-course-project.zip
cd cc-course-project

# If cloning fresh from GitHub instead:
git clone https://github.com/dikshachavan3205/cc-course-project.git cc-course-project
cd cc-course-project
```

---

## 3. (Optional) Copy the env template

```bash
cp .env.example .env
```

Not required to run anything — every value already has a code default — but useful if you later want to override something like `CHRONONET_TOTAL_STEPS` or `CHRONONET_CORS_ORIGINS`.

---

## 4. Set up Python and install dependencies

There's no single root `requirements.txt` — each module has its own. Install them all into one virtual environment at the repo root:

```bash
python -m venv venv

# Activate it:
source venv/bin/activate          # macOS/Linux
venv\Scripts\activate             # Windows PowerShell/CMD

# Install every module's dependencies:
pip install -r app/requirements.txt
pip install -r data_backend/requirements.txt
pip install -r monitoring/requirements.txt
pip install -r orchestration/requirements.txt
pip install -r prediction/requirements.txt
```

---

## 5. Run the backend API

From the **repo root**, with the venv active:

```bash
python -m uvicorn data_backend.main:app --reload --port 8000
```

Leave this terminal running. Verify it's up:

```bash
curl http://127.0.0.1:8000/health
```

You should get a JSON response. Interactive API docs are at `http://127.0.0.1:8000/docs`.

**If you see AWS warnings in the log** (e.g. `AccessDeniedException`, `NoCredentialsError`) — that's expected without full AWS setup. The server keeps running; `/status` and `/history` just return zeroed/empty data instead of real telemetry.

---

## 6. Run the dashboard (in a second terminal)

```bash
cd cc-course-project/dashboard
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

- It talks to the backend at `http://127.0.0.1:8000` by default.
- Override the API base URL anytime under Settings → API base URL (or set `VITE_API_BASE_URL` before building).
- If AWS reads are failing and the UI looks blank/zeroed, toggle **Demo Data** in Settings — same UI, synthetic-but-realistic data, always shown with a visible "Demo data" badge.

At this point you have a fully running system: **backend on :8000, dashboard on :5173.**

---

## 7. (Optional) Run the simulated workload

This is the demo "app" ChronoNet protects — it checkpoints progress locally and best-effort to S3:

```bash
cd cc-course-project/app
python main.py
```

Checkpoints land in `app/checkpoints/checkpoint.json`. Stop it anytime with `Ctrl+C` — it checkpoints on shutdown before exiting.

---

## 8. (Optional) Enable real AWS features

Only needed for real S3 checkpoints, DynamoDB history, SNS alerts, or real EC2 migration.

1. **Rotate/create a fresh IAM access key** for a user with the needed permissions (S3, DynamoDB, SNS at minimum — EC2 too if testing real migration).
2. Configure credentials **outside** this project:

   ```bash
   aws configure
   ```

   This writes to `~/.aws/credentials`; boto3 (used throughout the project) reads it automatically. Region should be `ap-south-1` to match `shared/constants.py`, unless you've changed it there.
3. Restart the backend (`uvicorn --reload` will pick this up automatically on the next request).
4. For real EC2 migration specifically, also set in `.env` (and actually load these into your shell/session):

   ```
   CHRONONET_ALLOW_REAL_EC2=true
   CHRONONET_AMI=<your AMI id>
   CHRONONET_SUBNET_ID=<your subnet id>
   CHRONONET_KEY_NAME=<your EC2 key pair name>
   CHRONONET_SECURITY_GROUP_IDS=<your security group id(s)>
   ```

   Remember, since nothing loads `.env` automatically outside Docker, you'll need to `export` these in your shell (or add them via `aws configure`/system environment variables) for the process to actually see them.

---

## 9. (Optional) Train the risk model

No trained model (`prediction/model/risk_model.pkl`) is committed — it's gitignored. Without it, the backend just logs a warning and returns `risk_percent: 0`.

```bash
cd cc-course-project
source venv/bin/activate
python prediction/dataset/generate_synthetic_data.py   # or the real fetch_* scripts
python prediction/train_model.py
```

---

## 10. Quick troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `docker-compose up` fails | Missing Dockerfiles for `data_backend`/`dashboard` | Don't use Docker — run steps 5–6 directly |
| `ModuleNotFoundError` on backend start | venv not activated, or a `requirements.txt` skipped | Re-activate venv, re-run all 5 `pip install -r ...` commands |
| `AccessDeniedException` / `NoCredentialsError` in backend logs | No/insufficient AWS credentials | Expected if you skipped step 8 — app still works, data is just zeroed |
| Dashboard shows blank/zero everything | Same as above — backend can't reach AWS | Toggle **Demo Data** in dashboard Settings |
| `npm run dev` fails | Node version too old, or `npm install` didn't finish | Confirm `node -v` is 18+; re-run `npm install` |
| Backend port 8000 already in use | Something else running on that port | `--port 8080` (or any free port) and update dashboard's API base URL to match |

---

## Summary — fastest path to "it's running"

```bash
# Terminal 1
cd cc-course-project
python -m venv venv && source venv/bin/activate
pip install -r app/requirements.txt -r data_backend/requirements.txt -r monitoring/requirements.txt -r orchestration/requirements.txt -r prediction/requirements.txt
python -m uvicorn data_backend.main:app --reload --port 8000

# Terminal 2
cd cc-course-project/dashboard
npm install
npm run dev
```

Open `http://localhost:5173`. Done.