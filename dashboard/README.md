# ChronoNet Dashboard

Ops console for ChronoNet — predicts EC2 Spot interruptions and migrates the
Dockerized workload with zero progress loss. This is a **systems/DevOps tool**
(CloudWatch / Grafana register of restraint), not a consumer marketing site.
Keep it that way.

## Stack

- Vite + React 18
- Tailwind CSS 3 (PostCSS) — classes are generated **only from tokens**
- chart.js + react-chartjs-2
- Axios (talks to `data_backend/main.py`, FastAPI on `:8000`, proxied by Vite)

## Design decisions — do not "fix" these back to defaults

### 1. Color tokens are the single source of truth
All colors live as CSS custom properties in
[`src/styles/tokens.css`](./src/styles/tokens.css) and are exposed to Tailwind
via `theme.extend.colors` in `tailwind.config.js` (usable as `bg-base`,
`text-primary`, `border-border-mid`, …). Never hardcode a hex in a component.

- Dark navy scale (`--bg-base #00002A`, `--bg-surface #1A3F75`, …
  `--text-primary #C9DAE8`) — long-session monitoring palette, not a landing
  page aesthetic.
- **Reserved risk-state accents** `--risk-low/medium/high` are allowed ONLY on
  the risk meter and status pills. No other component may reference them.
- `--border-mid` is drawn at ~30 % opacity as `--border-hairline` for actual
  borders — hairline dividers, not thick outlines.

### 2. Exactly two font families, distinct roles
- **Space Grotesk** (500/600/700) — headings, labels, UI chrome, buttons, body.
- **IBM Plex Mono** (400/500) — **every** numeric readout, without exception:
  CPU %, RAM %, risk %, downtime seconds, migration count, timestamps, numeric
  table columns. This is for tabular alignment, not decoration.

Loaded via `@fontsource` npm packages (offline, no CDN) in
`src/styles/index.css`.

Type scale is a real scale: **12 / 14 / 16 / 20 / 28 / 40 px** (`text-xs`
through `text-2xl`). Sentence case throughout. No tracked-out ALL-CAPS
eyebrow labels, no label-above-every-heading pattern.

### 3. Radius carries meaning — it is not uniform
- Data panels and table rows: **2–4 px** (`rounded-data`, technical feel).
- **12–16 px** (`rounded-prominent`) is reserved for exactly two elements:
  the risk meter card and the primary "Trigger event" button.

### 4. Flat, hairline, shadow-free panels
Separate panels with 1 px hairline borders (`--border-hairline`). **No drop
shadows anywhere.** The single exception: `--glow-risk` under the risk meter
card — that is the one bold element in the UI. No gradient washes as
decoration, ever.

### 5. Motion is one orchestrated moment
- **First load only:** the risk meter arc animates 0 → current value once
  (`arc-fill`, 1200 ms, ease-out expo). Not per-card entrance parades.
- **Every poll after:** values update via a smooth CSS transition
  (300 ms `--ease-value` on the changed number/arc). Never a re-triggered
  entrance animation.
- No fade-and-slide-up on section load. No hover-lift on every card.

### 6. Layout (12-column grid)
Wireframe — desktop columns → single column below 768px:

```
ChronoNet    ● connected · ap-south-1      [Trigger event]
[ risk (4) ] [ cpu/ram · live (5) ]        [ vm status (3) ]
[ checkpoint (4) ] [ migrations (4) ]      [ last downtime (4) ]
[ migration history (12, full width) ]
```

## Commands

```bash
npm run dev       # vite dev server :5173 (proxies to FastAPI :8000)
npm run build     # production build
npm run preview   # preview the production build
```

## File map

```
src/
  styles/tokens.css        design tokens (colors, type, radii, motion)
  styles/index.css         fonts + tailwind layers + base + .panel helpers
  api/client.js            axios client for /status /history /interruption
  hooks/usePolling.js      poll cadence hook (shell)
  components/              empty shells for the wireframe panels
```

## Contract reference

The dashboard consumes `data_backend/main.py` which strictly follows
`shared/contracts.md`:

- `GET /status` → `{run_id, vm_id, region, cpu_percent, ram_percent,
  risk_percent, migration_count, last_downtime_seconds}`
- `GET /history?run_id=` → `{run_id, migrations: [...]}`
- `POST /interruption` → RiskEvent `{run_id, vm_id, risk_percent,
  threshold_exceeded, timestamp}` and returns the migration summary