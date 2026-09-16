// Migration Audit tab — full-screen chronological ledger of every interrupt /
// migration event. Richer than the overview's compact table: adds trigger
// source, target market, risk at trigger, and the resume index. Same row shape
// as GET /history (chrononet-migrations, newest first).
//
// Alignment rules hold: numeric/time columns right-aligned mono, text columns
// left-aligned. Status pills are the only risk-accent carrier outside the gauge.
import { fmtClock } from '../lib/time';
import { fmtDowntime, fmtRisk, statusTone, TONES } from '../lib/migrations';

const dash = '—';

export default function MigrationAuditView({ migrations = [] }) {
  const rows = Array.isArray(migrations) ? migrations : [];

  return (
    <section className="panel p-5" aria-label="Migration audit">
      <div className="flex items-baseline justify-between gap-3">
        <p className="panel-label">migration audit</p>
        <span className="font-mono text-sm text-muted">{rows.length} events</span>
      </div>

      {rows.length === 0 ? (
        <p className="mt-4 text-base text-primary">
          No migration events recorded — telemetry stable.
        </p>
      ) : (
        // overflow-auto: wide keys scroll horizontally, dense rows scroll
        // vertically inside this panel; the sticky header keeps column
        // context while roving deep history. The page itself never scrolls.
        <div className="mt-3 max-h-[520px] overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted">
                <th className="sticky top-0 bg-surface px-2 py-2 text-right font-mono font-medium">time</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-left font-mono font-medium">from → to</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-left font-mono font-medium">triggered by</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-right font-mono font-medium">downtime (s)</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-left font-mono font-medium">market</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-right font-mono font-medium">risk</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-left font-mono font-medium">status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-mid">
              {rows.map((m, i) => {
                const tone = statusTone(m.status);
                return (
                  <tr key={m.timestamp ?? i}>
                    <td className="px-2 py-2 text-right font-mono text-primary">
                      {fmtClock(m.timestamp)}
                    </td>
                    <td className="px-2 py-2 text-left text-primary">
                      {m.from_vm_id || dash} → {m.to_vm_id || dash}
                    </td>
                    <td className="px-2 py-2 text-left font-mono text-primary">
                      {m.triggered_by || dash}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-primary">
                      {fmtDowntime(m.downtime_seconds)}
                    </td>
                    <td className="px-2 py-2 text-left font-mono text-primary">
                      {m.provision_market || dash}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-primary">
                      {fmtRisk(m.risk_percent)}
                    </td>
                    <td className="px-2 py-2 text-left">
                      <span className={`inline-block rounded-data px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
                        {m.status || dash}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}