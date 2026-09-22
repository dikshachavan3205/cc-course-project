import { Fragment, useMemo, useState } from "react";
import { Panel, PanelLabel, StatusPill } from "../components/ui.jsx";
import { MiniSteps } from "../components/Stepper.jsx";
import { PageHead } from "../components/layout.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { fmtDateTime, fmtSeconds, parseTimeline } from "../lib/time.js";

const COLUMNS = [
  { key: "timestamp", label: "Time", sortable: true },
  { key: "route", label: "From → To", sortable: false },
  { key: "downtime_seconds", label: "Downtime", sortable: true, numeric: true },
  { key: "triggered_by", label: "Trigger", sortable: false },
  { key: "status", label: "Status", sortable: false },
];

export default function Migrations() {
  const { history } = useChrono();
  const [sortKey, setSortKey] = useState("timestamp");
  const [asc, setAsc] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const rows = useMemo(() => {
    const list = [...(history || [])];
    if (!list.length) return list;
    const dir = asc ? 1 : -1;
    list.sort((a, b) => {
      let av = a[sortKey];
      let bv = b[sortKey];
      if (sortKey === "timestamp") {
        av = new Date(av).getTime();
        bv = new Date(bv).getTime();
      }
      if ((av ?? 0) < (bv ?? 0)) return -1 * dir;
      if ((av ?? 0) > (bv ?? 0)) return 1 * dir;
      return 0;
    });
    return list;
  }, [history, sortKey, asc]);

  const toggleSort = (key) => {
    if (key === "route" || key === "triggered_by" || key === "status") return;
    if (sortKey === key) {
      setAsc((v) => !v);
    } else {
      setSortKey(key);
      setAsc(false);
    }
  };

  return (
    <>
      <PageHead
        title="Migrations"
        sub="Click a row to expand the per-step detail, when the orchestrator recorded it."
      />

      <Panel className="overflow-hidden p-0">
        <div className="max-h-[640px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-elevated">
              <tr className="border-b border-border-mid/30 text-left">
                {COLUMNS.map((col) => (
                  <th key={col.key} className="px-4 py-3 font-medium">
                    <button
                      type="button"
                      onClick={() => toggleSort(col.key)}
                      className={`inline-flex items-center gap-1 text-xs text-muted hover:text-primary ${
                        !col.sortable ? "cursor-default" : ""
                      }`}
                      tabIndex={col.sortable ? 0 : -1}
                      aria-disabled={!col.sortable}
                    >
                      {col.label}
                      {col.sortable ? (
                        <span className="num text-[10px]" aria-hidden="true">
                          {sortKey === col.key ? (asc ? "↑" : "↓") : ""}
                        </span>
                      ) : null}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-mid/15">
              {rows.map((row, i) => {
                const key = `${row.timestamp}-${i}`;
                const isOpen = expanded === key;
                const detail = isOpen ? parseTimeline(row.timeline) : null;
                return (
                  <Fragment key={key}>
                    <tr
                      onClick={() => setExpanded(isOpen ? null : key)}
                      className="cursor-pointer transition-colors hover:bg-surface/50"
                      aria-expanded={isOpen}
                    >
                      <td className="px-4 py-3 text-xs text-muted">{fmtDateTime(row.timestamp)}</td>
                      <td className="num px-4 py-3 text-xs text-primary">
                        {row.from_vm_id} → {row.to_vm_id}
                      </td>
                      <td className="num px-4 py-3 text-xs">{fmtSeconds(row.downtime_seconds)}</td>
                      <td className="px-4 py-3 text-xs text-muted">{row.triggered_by || "imds"}</td>
                      <td className="px-4 py-3">
                        <StatusPill status={row.status} />
                      </td>
                    </tr>
                    {isOpen ? (
                      <tr className="bg-surface/30">
                        <td colSpan={COLUMNS.length} className="px-4 pb-3">
                          {detail && detail.length ? (
                            <div>
                              <PanelLabel>Step detail</PanelLabel>
                              <MiniSteps steps={detail} />
                            </div>
                          ) : (
                            <span className="text-xs text-muted">
                              No per-step detail recorded for this migration.
                            </span>
                          )}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          {!rows.length ? (
            <p className="py-10 text-center text-sm text-muted">
              No migration events recorded — telemetry stable.
            </p>
          ) : null}
        </div>
      </Panel>
    </>
  );
}