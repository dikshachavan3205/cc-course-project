import { useState } from "react";
import { Panel, PanelLabel } from "../components/ui.jsx";
import { PageHead } from "../components/layout.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { fetchStatus } from "../api/client.js";
import { fmtPct } from "../lib/time.js";

const INTERVALS = [
  { ms: 2000, label: "2s" },
  { ms: 3000, label: "3s" },
  { ms: 5000, label: "5s" },
  { ms: 10000, label: "10s" },
];

export default function Settings() {
  const {
    apiBase,
    setApiBase,
    pollMs,
    setPollMs,
    demo,
    setDemo,
  } = useChrono();

  const [draft, setDraft] = useState(apiBase);
  const [probe, setProbe] = useState(null); // null idle | true ok | false err

  const saveBase = async (e) => {
    e.preventDefault();
    const next = draft.trim().replace(/\/+$/, "");
    if (!next) return;
    setApiBase(next);
    setProbe(null);
    try {
      const s = await fetchStatus(next);
      setProbe(Boolean(s?.run_id));
    } catch {
      setProbe(false);
    }
  };

  return (
    <>
      <PageHead title="Settings" sub="Local preferences only — nothing here changes the backend." />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Panel>
          <PanelLabel>API base URL</PanelLabel>
          <form onSubmit={saveBase} className="mt-3 flex flex-col gap-2">
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="http://127.0.0.1:8000"
              spellCheck={false}
              className="num w-full rounded-sm border border-border-mid/40 bg-surface px-3 py-2 text-sm text-primary"
            />
            <div className="flex items-center gap-2">
              <button
                type="submit"
                className="rounded-sm border border-border-mid/40 bg-elevated px-3 py-1.5 text-xs text-primary transition-colors hover:bg-surface"
              >
                Save & test
              </button>
              {probe === true ? <span className="text-xs text-risk-low">reachable ✓</span> : null}
              {probe === false ? (
                <span className="text-xs text-risk-high">unreachable — check the backend</span>
              ) : null}
            </div>
            <p className="text-xs text-muted">
              Overrides <code className="num">VITE_API_BASE_URL</code> for this browser only.
            </p>
          </form>
        </Panel>

        <Panel>
          <PanelLabel>Status poll interval</PanelLabel>
          <div className="mt-3 flex flex-wrap gap-2">
            {INTERVALS.map((iv) => (
              <button
                key={iv.ms}
                type="button"
                onClick={() => setPollMs(iv.ms)}
                className={`rounded-sm px-3 py-1.5 text-xs transition-colors ${
                  pollMs === iv.ms
                    ? "bg-elevated text-primary"
                    : "border border-border-mid/40 text-muted hover:bg-surface"
                }`}
              >
                {iv.label}
              </button>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">
            History re-fetches every 10s regardless; offset not included.
          </p>
        </Panel>

        <Panel>
          <PanelLabel>Demo data</PanelLabel>
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-sm text-muted">
              Show sample telemetry that is shape-identical to the live API.
            </span>
            <button
              type="button"
              role="switch"
              aria-checked={demo}
              onClick={() => setDemo(!demo)}
              className={`relative h-6 w-11 shrink-0 rounded-sm border transition-colors ${
                demo ? "border-risk-medium/60 bg-risk-medium/25" : "border-border-mid/40 bg-surface"
              }`}
            >
              <span
                className="absolute top-0.5 left-0.5 rounded-sm bg-primary transition-all"
                style={{ width: 18, height: 18, left: demo ? 22 : 2 }}
              />
            </button>
          </div>
          <p className="mt-3 text-xs text-muted">
            While on, the <span className="font-semibold text-muted">Demo data</span> badge shows in
            the top bar so sample data is never mistaken for live state.
          </p>
        </Panel>
      </div>

      <Panel className="mt-4">
        <PanelLabel>Resolved configuration</PanelLabel>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-muted">API base</dt>
            <dd className="num mt-0.5 truncate text-primary">{apiBase}</dd>
          </div>
          <div>
            <dt className="text-muted">Risk thresholds (a = risk)</dt>
            <dd className="num mt-0.5 text-primary">
              {fmtPct(40, 0)} / {fmtPct(70, 0)}
            </dd>
          </div>
          <div>
            <dt className="text-muted">Provision mode</dt>
            <dd className="mt-0.5 text-primary">Spot → On-Demand</dd>
          </div>
          <div>
            <dt className="text-muted">Checkpoint cadence</dt>
            <dd className="num mt-0.5 text-primary">30 steps</dd>
          </div>
        </dl>
      </Panel>
    </>
  );
}