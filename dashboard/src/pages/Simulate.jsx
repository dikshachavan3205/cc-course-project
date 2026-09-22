import { useState } from "react";
import { Panel, PanelLabel, StatusPill } from "../components/ui.jsx";
import { StepStepper } from "../components/Stepper.jsx";
import { PageHead } from "../components/layout.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { fmtSeconds, parseTimeline } from "../lib/time.js";

const SOURCES = [
  { id: "imds", label: "Immediate reclaim signal", hint: "mimics an EC2 Spot reclaim notice arriving via IMDS" },
  { id: "prediction", label: "ML prediction", hint: "mimics the trained predictor flagging elevated interruption odds" },
  { id: "manual", label: "Manual test", hint: "an operator-triggered emergency hedge" },
];

export default function Simulate() {
  const { status, trigger, triggerState, triggerError, lastResult } = useChrono();
  const [source, setSource] = useState("imds");

  const run = async (e) => {
    e.preventDefault();
    await trigger(
      {
        run_id: status?.run_id || "run-local-dev",
        vm_id: status?.vm_id || "vm-local-dev",
        risk_percent: 100.0,
        threshold_exceeded: true,
      },
      source,
    );
  };

  const steps = lastResult ? parseTimeline(lastResult.timeline) : null;
  const current = SOURCES.find((s) => s.id === source);

  return (
    <>
      <PageHead
        title="Simulate"
        sub="Feed a threshold-exceeded interruption into the orchestrator and watch the full sequence run."
      />

      <form onSubmit={run} className="rounded-lg bg-elevated p-6 shadow-hero">
        <PanelLabel>Interruption signal</PanelLabel>
        <fieldset className="mt-4 grid grid-cols-1 gap-2">
          {SOURCES.map((s) => (
            <label
              key={s.id}
              className={`flex cursor-pointer items-start gap-3 rounded-sm border p-3 transition-colors ${
                source === s.id
                  ? "border-border-mid/70 bg-surface"
                  : "border-border-mid/30 bg-surface/40 hover:bg-surface"
              }`}
            >
              <input
                type="radio"
                name="source"
                value={s.id}
                checked={source === s.id}
                onChange={() => setSource(s.id)}
                className="mt-0.5 accent-[var(--text-primary)]"
              />
              <span>
                <span className="block text-sm text-primary">{s.label}</span>
                <span className="mt-0.5 block text-xs text-muted">{s.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={triggerState === "running"}
            className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-base transition-colors hover:bg-white disabled:cursor-wait disabled:opacity-60"
          >
            {triggerState === "running" ? "Migrating…" : "Simulate an interruption"}
          </button>
          {triggerState === "running" ? (
            <span className="text-sm text-muted">handing the event to the orchestrator…</span>
          ) : null}
        </div>
        {triggerError ? <div className="mt-3 text-sm text-risk-high">{triggerError}</div> : null}
      </form>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {lastResult && steps && steps.length ? (
          <>
            <Panel className="lg:col-span-2">
              <div className="flex items-center justify-between">
                <PanelLabel>7-step sequence</PanelLabel>
                <StatusPill status={lastResult.status} />
              </div>
              <StepStepper steps={steps} status={lastResult.status} />
            </Panel>
            <div className="flex flex-col gap-4">
              <Panel>
                <PanelLabel>Result</PanelLabel>
                <dl className="mt-3 space-y-2 text-sm">
                  <ResultRow k="Status" v={lastResult.status} pill />
                  <ResultRow k="Downtime" v={fmtSeconds(lastResult.downtime_seconds)} mono />
                  <ResultRow k="Migration ID" v={lastResult.migration_id} mono />
                  <ResultRow k="Checkpoint key" v={lastResult.checkpoint_key || "—"} mono />
                </dl>
              </Panel>
              {current ? (
                <Panel>
                  <PanelLabel>Trigger source</PanelLabel>
                  <p className="mt-2 text-sm text-muted">{current.hint}.</p>
                </Panel>
              ) : null}
            </div>
          </>
        ) : lastResult ? (
          <Panel className="lg:col-span-3">
            <PanelLabel>Result</PanelLabel>
            <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
              <StatusPill status={lastResult.status} />
              <span className="text-muted">
                downtime <span className="num text-primary">{fmtSeconds(lastResult.downtime_seconds)}</span>
              </span>
              <span className="num truncate text-muted">{lastResult.migration_id}</span>
            </div>
            <p className="mt-3 text-sm text-muted">
              No per-step timeline was returned for this run — the record shows only the summary.
            </p>
          </Panel>
        ) : (
          <Panel className="lg:col-span-3">
            <p className="py-6 text-sm text-muted">
              No simulation run yet in this session. Fire one above — the 7-step sequence renders
              here the moment it completes.
            </p>
          </Panel>
        )}
      </div>
    </>
  );
}

function ResultRow({ k, v, mono, pill }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className="truncate">
        {pill ? <StatusPill status={v} /> : <span className={`text-primary ${mono ? "num" : ""}`}>{v}</span>}
      </dd>
    </div>
  );
}