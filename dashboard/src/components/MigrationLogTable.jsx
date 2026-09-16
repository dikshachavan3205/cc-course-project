// Migration history table — maps 1:1 onto GET /history (chrononet-migrations
// rows, newest first). Columns: time · from → to · downtime · status.
//   * Numeric/time columns are monospace and right-aligned; text columns are
//     left-aligned (per the dashboard's mono/alignment rules).
//   * Status is the only other surface allowed the risk accents: success =
//     --risk-low, failed = --risk-high; anything unusual falls back to muted.
//   * Empty state speaks in the interface's own voice — no generic placeholder.
//   * `limit` truncates to a preview (used on Overview); `onShowAll` renders a
//     footer link that jumps to the full Migration Audit tab.
import { fmtClock } from '../lib/time';
import { fmtDowntime, statusTone, TONES } from '../lib/migrations';

export default function MigrationLogTable({ migrations = [], limit = null, onShowAll = null }) {
  const rows = Array.isArray(migrations) ? migrations : [];
  const shown = limit ? rows.slice(0, limit) : rows;
  const truncated = shown.length < rows.length;

  const thead = (
    <tr className="border-b border-border-mid text-muted">
      <th className="px-2 py-2 text-right font-mono font-medium">time</th>
      <th className="px-2 py-2 text-left font-mono font-medium">from → to</th>
      <th className="px-2 py-2 text-right font-mono font-medium">downtime (s)</th>
      <th className="px-2 py-2 text-left font-mono font-medium">status</th>
    </tr>
  );

  return (
    <section className="panel p-5" aria-label="Migration history">
      <div className="flex items-baseline justify-between gap-3">
        <p className="panel-label">recent migrations</p>
        {rows.length > 0 && (
          <span className="font-mono text-sm text-muted">{rows.length} total</span>
        )}
      </div>

      {rows.length === 0 ? (
        <p className="mt-4 text-base text-primary">
          No migrations yet — trigger a test event above, or wait for a real interruption.
        </p>
      ) : (
        // overflow-x-auto keeps long instance IDs inside the card at 375px —
        // the page never scrolls horizontally, only this container.
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
          <thead>{thead}</thead>
          <tbody className="divide-y divide-border-mid">
            {shown.map((m, i) => {
              const tone = statusTone(m.status);
              return (
                <tr key={m.timestamp ?? i}>
                  <td className="px-2 py-2 text-right font-mono text-primary">
                    {fmtClock(m.timestamp)}
                  </td>
                  <td className="px-2 py-2 text-left text-primary">
                    {m.from_vm_id || '—'} → {m.to_vm_id || '—'}
                  </td>
                  <td className="px-2 py-2 text-right font-mono text-primary">
                    {fmtDowntime(m.downtime_seconds)}
                  </td>
                  <td className="px-2 py-2 text-left">
                    <span className={`inline-block rounded-data px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
                      {m.status || '—'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          </table>
        </div>
      )}

      {truncated && onShowAll && (
        <button
          type="button"
          onClick={onShowAll}
          className="mt-3 text-sm font-medium text-primary transition-colors duration-200 hover:text-muted"
        >
          view full audit →
        </button>
      )}
    </section>
  );
}