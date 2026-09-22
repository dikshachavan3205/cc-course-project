# ChronoNet — Command Center (dashboard)

Studio-grade frontend for the ChronoNet orchestration hub. Reads real state from
the FastAPI backend (`GET /status`, `GET /history`), can **trigger a real 7-step
migration** (`POST /interruption`), and renders the returned step timeline.

## Run it

```powershell
# 1. Backend (repo root)
python -m uvicorn data_backend.main:app --port 8000

# 2. Dashboard (this folder)
npm install
npm run dev
```

Open **http://localhost:5173** (Vite may bind IPv6 — `http://[::1]:5173` also works).

Production build + preview:

```powershell
npm run build        # -> dist/
npm run preview      # serves dist on :4173
```

## API base URL

Defaults to `http://127.0.0.1:8000`. Override **before** build with
`VITE_API_BASE_URL`, or per-browser from **Settings → API base URL** and click
“Save & test”. The backend enables CORS (`*`) by default for any local origin.

## Pages

| Route | What it shows |
| --- | --- |
| `/overview` | State headline ("All stable" / "Risk elevated" / "Migrating now", driven by risk), risk-posture hero gauge, stat grids, interruption trigger, live telemetry + last 3 migrations |
| `/overview/timeline` | The exact step sequence from the most recent trigger |
| `/instances` | Current instance + every node seen in migration history |
| `/checkpoints` | Latest checkpoint key (click to copy), live age, resumed index |
| `/migrations` | Sortable history table; click a row to expand per-step detail when recorded |
| `/monitoring` | CPU / RAM / risk charts over the accumulated rolling window |
| `/simulate` | Large trigger control; renders the 7-step vertical stepper with elapsed ms |
| `/settings` | API base URL, status poll interval, **Demo data** toggle |

## Shared behavior

- One polling engine (`src/hooks/useChrono.js`) drives every page: `/status`
  every N s (default 3 s, Settings-adjustable) and `/history` every 10 s.
- Offline after 2 consecutive failed polls; shows the calm reconnect banner and
  keeps last-known data.
- **Demo data** mode (Settings) serves synthetic telemetry with shapes identical
  to the live API and is always marked with the persistent "Demo data" badge —
  sample data is never presented as live state.
- `src/utils/risk.js` owns every risk-derived color and label
  (Healthy < 40 / Elevated < 70 / Critical).

## Contract fields confirmed against `data_backend` (Phase 0)

- `GET /status` → `run_id, vm_id, region, cpu_percent, ram_percent,
  risk_percent, migration_count, last_downtime_seconds`
- `GET /history?run_id=…` → `migrations` newest-first; each row:
  `run_id, timestamp, from_vm_id, to_vm_id, triggered_by, risk_percent,
  downtime_seconds, status, checkpoint_key, checkpoint_index, resumed_index,
  provision_market, timeline, completed_at` — `timeline` is a JSON string of the
  step list.
- `POST /interruption` → `run_id, from_vm_id, to_vm_id, migration_id, status,
  checkpoint_key, downtime_seconds, timeline` — `timeline` (list of
  `{step, name, at_utc, elapsed_ms, …}`) **was added** to the response model;
  strictly additive, no existing field renamed or removed.