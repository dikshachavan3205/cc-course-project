// Telemetry Stream tab — the expanded analytical deep-dive. Same rolling
// buffer the overview chart uses, but surfaced harder: windowed min/max/avg
// readouts, a taller combined chart, a scrolling per-point metric log, and a
// dedicated chart per resource. The buffer lives in App's usePolling
// instance, so it keeps filling across tab switches — this view only reads
// the slices it is given.
import LiveChart from '../components/LiveChart';
import MetricChart from '../components/MetricChart';
import { fmtClock } from '../lib/time';
import { readCssVarRgb } from '../lib/tokens';

function statsFor(key, series) {
  const vals = series.map((p) => p[key]).filter((v) => Number.isFinite(v));
  if (vals.length === 0) return { current: null, min: null, max: null, avg: null };
  const sum = vals.reduce((a, b) => a + b, 0);
  return {
    current: vals[vals.length - 1],
    min: Math.min(...vals),
    max: Math.max(...vals),
    avg: sum / vals.length,
  };
}

const pct = (v) => (v === null ? '—' : `${v.toFixed(1)}%`);

function MetricPanel({ label, dataKey, series }) {
  const s = statsFor(dataKey, series);
  const cells = [
    { n: 'current', v: s.current },
    { n: 'min', v: s.min },
    { n: 'avg', v: s.avg },
    { n: 'max', v: s.max },
  ];

  return (
    <section className="panel p-5" aria-label={`${label} metrics`}>
      <div className="flex items-baseline justify-between">
        <p className="panel-label">{label}</p>
        <span className="font-mono text-sm text-muted">5m window</span>
      </div>
      <dl className="mt-4 grid grid-cols-4 gap-4">
        {cells.map((c) => (
          <div key={c.n}>
            <dt className="text-sm text-muted">{c.n}</dt>
            <dd className="mt-0.5 font-mono text-xl text-primary">{pct(c.v)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function MetricLog({ series = [] }) {
  return (
    <section className="panel p-5" aria-label="Historical metric log">
      <div className="flex items-baseline justify-between">
        <p className="panel-label">metric log</p>
        <span className="font-mono text-sm text-muted">{series.length} pts</span>
      </div>
      {series.length === 0 ? (
        <p className="mt-4 text-sm text-muted">waiting for /status…</p>
      ) : (
        // The log is the only vertically scrollable surface here — dense
        // rows, sticky header, newest sample on top.
        <div className="mt-3 max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted">
                <th className="sticky top-0 bg-surface px-2 py-2 text-right font-mono font-medium">time</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-right font-mono font-medium">cpu</th>
                <th className="sticky top-0 bg-surface px-2 py-2 text-right font-mono font-medium">ram</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-mid">
              {[...series].reverse().map((p, i) => (
                <tr key={p.t ?? i}>
                  <td className="px-2 py-1.5 text-right font-mono text-primary">{fmtClock(p.t)}</td>
                  <td className="px-2 py-1.5 text-right font-mono text-primary">{p.cpu.toFixed(1)}%</td>
                  <td className="px-2 py-1.5 text-right font-mono text-primary">{p.ram.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function TelemetryView({ series = [] }) {
  return (
    <>
      {/* windowed readouts */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <MetricPanel label="cpu" dataKey="cpu" series={series} />
        <MetricPanel label="ram" dataKey="ram" series={series} />
      </div>

      {/* combined live chart + scrolling metric log */}
      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-12">
        <div className="md:col-span-8">
          <LiveChart series={series} heightClass="h-96" />
          <p className="mt-2 text-xs text-muted">
            rolling buffer · 60 points · /status every 3s
          </p>
        </div>
        <div className="md:col-span-4">
          <MetricLog series={series} />
        </div>
      </div>

      {/* dedicated analytical charts */}
      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
        <MetricChart
          title="cpu — dedicated"
          series={series}
          dataKey="cpu"
          rgb={readCssVarRgb('text-primary')}
          heightClass="h-48"
        />
        <MetricChart
          title="ram — dedicated"
          series={series}
          dataKey="ram"
          rgb={readCssVarRgb('border-mid')}
          heightClass="h-48"
        />
      </div>
    </>
  );
}