// Overview tab — the primary command center telemetry grid, arranged as three
// engines in a row with a stat strip and migration preview below:
//   Left   — Risk Telemetry Engine (SVG gauge, backlit, status badge)
//   Center — Live Infrastructure Telemetry (CPU/RAM line chart)
//   Right  — Node Context & Checkpoint Hub (run/vm/region + checkpoint age)
// Bottom  — compact metric strip + summarized migration preview table.
// All data is passed in from App's single usePolling instance, so nothing
// here fetches or remounts anything.
import RiskMeter from '../components/RiskMeter';
import LiveChart from '../components/LiveChart';
import NodeContextCard from '../components/NodeContextCard';
import MetricStrip from '../components/MetricStrip';
import MigrationLogTable from '../components/MigrationLogTable';

export default function OverviewView({
  status,
  series,
  history,
  checkpointTime,
  checkpointKey,
  lastMigration,
  onShowAll,
}) {
  return (
    <>
      {/* three-engine row (3 / 6 / 3). Single column stacks in order:
          gauge → chart → node hub. */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-12">
        <div className="md:col-span-3">
          <RiskMeter riskPercent={status?.risk_percent ?? 0} />
        </div>
        <div className="md:col-span-6">
          <LiveChart series={series} />
        </div>
        <div className="md:col-span-3">
          <NodeContextCard
            status={status}
            checkpointTime={checkpointTime}
            checkpointKey={checkpointKey}
          />
        </div>
      </div>

      {/* compact metric strip */}
      <div className="mt-5">
        <MetricStrip
          migrationCount={status?.migration_count ?? 0}
          seconds={status?.last_downtime_seconds ?? 0}
          history={history}
          lastMigration={lastMigration}
        />
      </div>

      {/* summarized live migration preview */}
      <div className="mt-5">
        <MigrationLogTable migrations={history} limit={5} onShowAll={onShowAll} />
      </div>
    </>
  );
}