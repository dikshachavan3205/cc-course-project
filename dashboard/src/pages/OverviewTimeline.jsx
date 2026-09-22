import { NavLink } from "react-router-dom";
import { NavTabs, Panel, PanelLabel, StatusPill } from "../components/ui.jsx";
import { StepStepper } from "../components/Stepper.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { fmtSeconds, parseTimeline } from "../lib/time.js";

const OVERVIEW_TABS = [
  { to: "/overview", label: "Overview" },
  { to: "/overview/timeline", label: "Timeline" },
];

export default function OverviewTimeline() {
  const { lastResult } = useChrono();
  const steps = lastResult ? parseTimeline(lastResult.timeline) : null;

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-primary">Timeline</h1>
        <p className="mt-1 text-sm text-muted">
          The exact 7-step sequence the orchestrator executed for the most recent
          interruption.
        </p>
        <div className="mt-3">
          <NavTabs items={OVERVIEW_TABS} />
        </div>
      </div>

      {steps && steps.length ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-2">
            <div className="flex items-center justify-between">
              <PanelLabel>Step timeline</PanelLabel>
              {lastResult ? <StatusPill status={lastResult.status} /> : null}
            </div>
            <StepStepper steps={steps} status={lastResult?.status} />
          </Panel>
          <div className="flex flex-col gap-4">
            {lastResult ? (
              <Panel>
                <PanelLabel>Migration summary</PanelLabel>
                <dl className="mt-3 space-y-2 text-sm">
                  <Row k="Run" v={lastResult.run_id} mono />
                  <Row k="From" v={lastResult.from_vm_id} mono />
                  <Row k="To" v={lastResult.to_vm_id} mono />
                  <Row k="Downtime" v={fmtSeconds(lastResult.downtime_seconds)} mono />
                  <Row k="Migration ID" v={lastResult.migration_id} mono />
                </dl>
              </Panel>
            ) : null}
            <Panel>
              <PanelLabel>Why this matters</PanelLabel>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                Each entry is timestamped and carries a monotonic elapsed time, so downtime is
                measured from trigger receipt to app resume — never an estimate.
              </p>
            </Panel>
          </div>
        </div>
      ) : (
        <Panel>
          <p className="py-8 text-sm text-muted">
            No migration timeline recorded yet —{" "}
            <NavLink to="/simulate" className="text-primary underline-offset-2 hover:underline">
              run a simulation
            </NavLink>{" "}
            to capture the 7-step sequence.
          </p>
        </Panel>
      )}
    </>
  );
}

function Row({ k, v, mono }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className={`truncate text-primary ${mono ? "num" : ""}`} title={v}>
        {v}
      </dd>
    </div>
  );
}