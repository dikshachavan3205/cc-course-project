import { useMemo } from "react";
import { Panel, PanelLabel, StatusPill } from "../components/ui.jsx";
import { PageHead } from "../components/layout.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { fmtDateTime } from "../lib/time.js";

export default function Instances() {
  const { status, history, connected } = useChrono();

  const market = useMemo(() => {
    const latest = (history || []).find((h) => h.provision_market);
    return latest ? latest.provision_market : null;
  }, [history]);

  const nodes = useMemo(() => {
    const seen = new Map(); // vmId -> { role, kind, lastSeen }
    (history || []).forEach((row) => {
      if (row.from_vm_id) {
        const prev = seen.get(row.from_vm_id);
        seen.set(row.from_vm_id, {
          id: row.from_vm_id,
          role: "Previous",
          kind: prev?.kind || "source",
          lastSeen: prev?.lastSeen || row.timestamp,
        });
      }
      if (row.to_vm_id) {
        const prev = seen.get(row.to_vm_id);
        seen.set(row.to_vm_id, {
          id: row.to_vm_id,
          role: "Target",
          kind: prev?.kind || "target",
          lastSeen: prev?.lastSeen || row.timestamp,
        });
      }
    });
    if (status?.vm_id) {
      seen.set(status.vm_id, {
        id: status.vm_id,
        role: "Current",
        kind: "current",
        lastSeen: new Date().toISOString(),
      });
    }
    return [...seen.values()].sort((a, b) => (a.lastSeen < b.lastSeen ? 1 : -1));
  }, [history, status]);

  return (
    <>
      <PageHead
        title="Instances"
        sub="Every node this run has touched — current, replaced, and provisioned targets."
      />

      <div className="rounded-lg bg-elevated p-6 shadow-hero">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <PanelLabel>Current instance</PanelLabel>
            <div className="num mt-2 text-xl text-primary">{status?.vm_id || "—"}</div>
            <div className="mt-1 text-sm text-muted">
              {status?.region || "—"} · run {status?.run_id || "—"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill status={connected ? (status?.vm_id ? "running" : "unknown") : "offline"} />
            <span className="num text-xs text-muted">{market === "ondemand" ? "On-Demand" : market ? "Spot" : "—"}</span>
          </div>
        </div>
      </div>

      <Panel className="mt-4">
        <PanelLabel>Nodes in migration history</PanelLabel>
        {nodes.length ? (
          <table className="mt-3 w-full text-sm">
            <thead>
              <tr className="border-b border-border-mid/30 text-left text-xs text-muted">
                <th className="pb-2 pr-4 font-medium">Node</th>
                <th className="pb-2 pr-4 font-medium">Role</th>
                <th className="pb-2 font-medium">Last active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-mid/15">
              {nodes.map((n) => (
                <tr key={n.id} className="text-muted">
                  <td className="num py-2.5 pr-4 text-primary">{n.id}</td>
                  <td className="py-2.5 pr-4 capitalize">{n.role}</td>
                  <td className="num py-2.5">{fmtDateTime(n.lastSeen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="py-6 text-sm text-muted">No instances recorded yet.</p>
        )}
      </Panel>
    </>
  );
}