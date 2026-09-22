import { useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import { NavTabs, Panel, PanelLabel, StatCard, StatusPill } from "../components/ui.jsx";
import { ChartPanel, LineChart, RiskArc } from "../components/Charts.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { getRiskColor, getRiskLabel } from "../utils/risk.js";
import { fmtDateTime, fmtPct, fmtSeconds, todayHMS, timeAgo } from "../lib/time.js";

const OVERVIEW_TABS = [
  { to: "/overview", label: "Overview" },
  { to: "/overview/timeline", label: "Timeline" },
];

function verdictFor(risk) {
  const label = getRiskLabel(risk);
  if (label === "Healthy") return "All stable";
  if (label === "Elevated") return "Risk elevated";
  return "Migrating now";
}

export default function Overview() {
  const { status, history, series, lastResult, trigger, triggerState } = useChrono();
  const [source, setSource] = useState("imds");

  const risk = status ? Number(status.risk_percent) : null;
  const headline = status ? verdictFor(risk) : "Connecting…";
  const subline = status
    ? `${status.region} · run ${status.run_id}`
    : "waiting for the ChronoNet API to report state";

  const latestCp = useMemo(
    // A real checkpoint row carries a numeric resumed_index; client-side
    // trigger rows have checkpoint_key but resumed_index=null and must not
    // win the "latest" slot.
    () => (history || []).find((h) => h.checkpoint_key && Number.isFinite(h.resumed_index)),
    [history],
  );
  const cpAge = latestCp ? timeAgo(latestCp.timestamp) : "—";

  const now = Date.now();
  const recent = (history || []).slice(0, 3);

  // StatusResponse aggregates (migration_count / last_downtime_seconds) reset
  // whenever the backend process restarts, so derive the real numbers from the
  // run-scoped migration history instead.
  const completedMig = useMemo(
    () => (history || []).filter((h) => h.status === "completed").length,
    [history],
  );
  const lastDowntime = useMemo(
    () => (history || []).find((h) => Number.isFinite(h?.downtime_seconds)),
    [history],
  );

  const chartWindow = (series || []).slice(-60);
  const chartLabels = chartWindow.map((p) => todayHMS(p.t));
  const cpuSeries = chartWindow.map((p) => p.cpu);
  const ramSeries = chartWindow.map((p) => p.ram);

  const runTrigger = async (e) => {
    e.preventDefault();
    await trigger(
      {
        run_id: status?.run_id || "run-local-dev",
        vm_id: status?.vm_id || "vm-local-dev",
        risk_percent: 100.0,
        threshold_exceeded: true,
        timestamp: new Date().toISOString(),
      },
      source,
    );
  };

  const hero = (
    <div className="flex flex-col items-center gap-1 rounded-lg bg-elevated p-6 shadow-hero">
      <PanelLabel>Risk posture</PanelLabel>
      <RiskArc risk={risk ?? 0} />
      <div className="mt-1 text-xs text-muted">last checkpoint {cpAge}</div>
    </div>
  );

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-primary">{headline}</h1>
          <p className="mt-1 text-sm text-muted">{subline}</p>
          <div className="mt-3">
            <NavTabs items={OVERVIEW_TABS} />
          </div>
        </div>
        {hero}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          label="Current risk"
          value={risk === null ? "—" : fmtPct(risk)}
          sub={risk === null ? "" : getRiskLabel(risk)}
          accent={risk === null ? "var(--text-muted)" : getRiskColor(risk)}
          icon="activity"
        />
        <StatCard
          label="Migrations"
          value={completedMig}
          sub="completed this run"
          accent="var(--risk-low)"
          icon="swap"
        />
        <StatCard
          label="Last downtime"
          value={lastDowntime ? fmtSeconds(lastDowntime.downtime_seconds) : "—"}
          sub="latest migration trigger → resume"
          accent="var(--risk-medium)"
          icon="zap"
        />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          label="CPU load"
          value={risk === null ? "—" : fmtPct(status.cpu_percent)}
          sub="current instance"
          accent="var(--text-primary)"
          icon="box"
        />
        <StatCard
          label="Memory"
          value={Number.isFinite(status?.ram_percent) && status.ram_percent > 0 ? fmtPct(status.ram_percent) : "N/A"}
          sub={
            Number.isFinite(status?.ram_percent) && status.ram_percent > 0
              ? "current instance"
              : "not available (no CloudWatch Agent)"
          }
          accent="var(--text-primary)"
          icon="box"
        />
        <StatCard
          label="Checkpoint age"
          value={cpAge}
          sub={latestCp ? `resumed at step ${latestCp.resumed_index ?? "—"}` : "none recorded yet"}
          accent="var(--text-primary)"
          icon="bookmark"
        />
      </div>

      <form onSubmit={runTrigger} className="panel mt-5 flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <PanelLabel>Simulate an interruption</PanelLabel>
          <p className="mt-1 max-w-md text-sm text-muted">
            Feed a threshold-exceeded signal to the orchestrator and watch the 7-step
            migration sequence run end to end.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="rounded-sm border border-border-mid/40 bg-surface px-3 py-2 text-sm text-primary focus:outline-none"
            aria-label="Trigger source"
          >
            <option value="imds">Immediate reclaim signal</option>
            <option value="prediction">ML prediction</option>
            <option value="manual">Manual test</option>
          </select>
          <button
            type="submit"
            disabled={triggerState === "running"}
            className="rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-base transition-colors hover:bg-white disabled:cursor-wait disabled:opacity-60"
          >
            {triggerState === "running" ? "Migrating…" : "Simulate"}
          </button>
        </div>
      </form>

      {lastResult ? (
        <div className="mt-3 flex items-center gap-3 rounded-sm border border-border-mid/30 bg-surface/60 px-4 py-2.5 text-sm">
          <StatusPill status={lastResult.status} />
          <span className="text-muted">
            downtime <span className="num text-primary">{fmtSeconds(lastResult.downtime_seconds)}</span>
          </span>
          {lastResult.timeline ? (
            <NavLink to="/overview/timeline" className="text-primary underline-offset-2 hover:underline">
              view step timeline →
            </NavLink>
          ) : null}
        </div>
      ) : null}

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ChartPanel title="Live telemetry" height={240}>
            <LineChart
              labels={chartLabels}
              datasets={[
                { label: "CPU %", data: cpuSeries, stroke: "rgba(201,218,232,0.95)" },
                { label: "RAM %", data: ramSeries, stroke: "rgba(143,176,201,0.7)" },
              ]}
              yFormat={(v) => `${v.toFixed(1)}%`}
            />
          </ChartPanel>
        </div>
        <Panel className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <PanelLabel>Recent migrations</PanelLabel>
            <NavLink to="/migrations" className="text-xs text-muted underline-offset-2 hover:text-primary hover:underline">
              view all →
            </NavLink>
          </div>
          {recent.length ? (
            <ul className="divide-y divide-border-mid/20">
              {recent.map((row, i) => (
                <li key={`${row.timestamp}-${i}`} className="flex items-center justify-between gap-2 py-2.5">
                  <div className="min-w-0">
                    <div className="num truncate text-xs text-muted">
                      {row.from_vm_id} → {row.to_vm_id}
                    </div>
                    <div className="mt-0.5 text-xs text-muted">{fmtDateTime(row.timestamp)}</div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <StatusPill status={row.status} />
                    <span className="num text-xs text-muted">{fmtSeconds(row.downtime_seconds)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-sm text-muted">No migration events recorded — telemetry stable.</p>
          )}
        </Panel>
      </div>
    </>
  );
}