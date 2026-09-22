import { useEffect, useMemo, useState } from "react";
import { Icon, Panel, PanelLabel } from "../components/ui.jsx";
import { PageHead } from "../components/layout.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { alpha } from "../components/ui.jsx";
import { timeAgo } from "../lib/time.js";

function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

function CopyKey({ value }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // clipboard unavailable (http/file context) — nothing else to do
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  return (
    <button
      type="button"
      onClick={copy}
      className="group inline-flex max-w-full items-center gap-2 text-left"
      aria-label="Copy checkpoint key"
    >
      <span className="num truncate text-xs text-muted group-hover:text-primary" title={value}>
        {value}
      </span>
      <span
        className="grid h-6 w-6 shrink-0 place-items-center rounded-sm border"
        style={{
          borderColor: alpha("var(--border-mid)", 0.4),
          color: copied ? "var(--risk-low)" : "var(--text-muted)",
        }}
      >
        <Icon name="copy" className="h-3.5 w-3.5" />
      </span>
      {copied ? <span className="num text-[10px] text-risk-low">copied</span> : null}
    </button>
  );
}

export default function Checkpoints() {
  const { history } = useChrono();
  const now = useNow();

  const latest = useMemo(() => (history || []).find((h) => h.checkpoint_key && Number.isFinite(h.resumed_index)), [history]);
  const archived = useMemo(
    () => (history || []).filter((h) => h.checkpoint_key && Number.isFinite(h.resumed_index)).slice(0, 5),
    [history],
  );

  return (
    <>
      <PageHead
        title="Checkpoints"
        sub="Off-box checkpoints are the zero-progress-loss backbone of every migration."
      />

      {latest ? (
        <div className="rounded-lg bg-elevated p-6 shadow-hero">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <PanelLabel>Latest checkpoint</PanelLabel>
              <div className="mt-3">
                <CopyKey value={latest.checkpoint_key} />
              </div>
              <div className="mt-4 grid grid-cols-1 gap-6 sm:grid-cols-3">
                <Meta k="Age" v={timeAgo(latest.timestamp, now)} />
                <Meta k="Resumed at step" v={latest.resumed_index ?? "—"} />
                <Meta k="Save cadence" v="every 30 steps" sub="configured default" />
              </div>
            </div>
          </div>
        </div>
      ) : (
        <Panel>
          <p className="py-8 text-sm text-muted">
            No checkpoints recorded yet — run a migration to capture the first one.
          </p>
        </Panel>
      )}

      {archived.length ? (
        <Panel className="mt-4">
          <PanelLabel>Recent checkpoints</PanelLabel>
          <ul className="mt-2 divide-y divide-border-mid/15">
            {archived.map((row, i) => (
              <li key={`${row.timestamp}-${i}`} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <CopyKey value={row.checkpoint_key} />
                <span className="num shrink-0 text-xs text-muted">
                  {timeAgo(row.timestamp, now)} · step {row.resumed_index ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </>
  );
}

function Meta({ k, v, sub }) {
  return (
    <div>
      <PanelLabel>{k}</PanelLabel>
      <div className="num mt-1 text-lg text-primary">{v}</div>
      {sub ? <div className="mt-0.5 text-xs text-muted">{sub}</div> : null}
    </div>
  );
}