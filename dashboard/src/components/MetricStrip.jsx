// Compact metric strip at the bottom of the Overview deck. Four quiet stat
// tiles: total migrations (counter), average downtime across this run's
// history, last measured downtime, and last checkpoint status. The two
// existing stat components (Migrations, LastDowntime) are composed in here;
// the new tiles follow the identical panel language. The status tile is the
// only risk-accent carrier on the strip (a status pill).
import Migrations from './Migrations';
import LastDowntime from './LastDowntime';
import { statusTone, TONES } from '../lib/migrations';

function AverageDowntime({ history = [] }) {
  const secs = (Array.isArray(history) ? history : [])
    .map((r) => Number(r.downtime_seconds))
    .filter(Number.isFinite);
  const avg = secs.length ? secs.reduce((a, b) => a + b, 0) / secs.length : 0;

  return (
    <section className="panel p-5" aria-label="Average downtime">
      <p className="panel-label">avg downtime</p>
      <p className="mt-2 font-mono text-2xl text-primary">
        {avg.toFixed(2)}
        <span className="ml-1 text-sm text-muted">s</span>
      </p>
    </section>
  );
}

function LastCheckpointStatus({ lastMigration = null }) {
  const status = lastMigration?.status ?? null;
  const tone = statusTone(status);

  return (
    <section className="panel p-5" aria-label="Last checkpoint status">
      <p className="panel-label">checkpoint status</p>
      <div className="mt-2">
        {status ? (
          <span className={`inline-block rounded-data px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}>
            {status}
          </span>
        ) : (
          <p className="font-mono text-2xl text-primary">—</p>
        )}
      </div>
    </section>
  );
}

export default function MetricStrip({ migrationCount = 0, seconds = 0, history = [], lastMigration = null }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 md:grid-cols-4">
      <Migrations count={migrationCount} />
      <AverageDowntime history={history} />
      <LastDowntime seconds={seconds} />
      <LastCheckpointStatus lastMigration={lastMigration} />
    </div>
  );
}