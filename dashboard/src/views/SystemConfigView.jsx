// System Health & Config tab — the ops-facing readout: active node identity,
// checkpoint metadata from the newest migration row, and the orchestration
// environment the hub was started with. Everything is read-only telemetry;
// nothing here mutates state.
//
// Environment values are presented as documented defaults from shared/
// constants.py (matching the dev backend), each annotated with its source.
import useNow from '../hooks/useNow';
import { relativeTime } from '../lib/time';

const dash = '—';

function Field({ label, value, mono = true }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={`mt-0.5 ${mono ? 'font-mono' : 'font-sans'} text-sm text-primary`}>
        {value}
      </dd>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section className="panel p-5" aria-label={title}>
      <p className="panel-label">{title}</p>
      <dl className="mt-3 space-y-3">{children}</dl>
    </section>
  );
}

export default function SystemConfigView({ status, checkpointTime, checkpointKey, lastMigration }) {
  const now = useNow(1000);
  const checkpointAge = relativeTime(checkpointTime, now);

  const nodeFields = [
    { label: 'run', value: status?.run_id || dash },
    { label: 'vm', value: status?.vm_id || dash },
    { label: 'region', value: status?.region || dash },
    {
      label: 'instance type',
      value: 't3.micro',
      mono: true,
      note: 'shared/constants.py',
    },
    { label: 'migrations', value: status?.migration_count ?? dash },
    {
      label: 'last event',
      value: lastMigration?.status || dash,
    },
    {
      label: 'last downtime (s)',
      value: Number.isFinite(Number(status?.last_downtime_seconds))
        ? `${Number(status.last_downtime_seconds).toFixed(2)}`
        : dash,
    },
  ];

  const checkpointFields = [
    { label: 'bucket', value: 's3://chrononet-checkpoints', mono: true, note: 'shared/constants.py' },
    { label: 'latest key', value: checkpointKey || dash },
    { label: 'age', value: checkpointAge ?? dash },
    { label: 'resume index', value: lastMigration?.resumed_index ?? dash },
    { label: 'market', value: lastMigration?.provision_market || dash },
  ];

  const envRows = [
    { name: 'CHRONONET_REGION', value: 'ap-south-1', note: 'orchestration region' },
    { name: 'CHRONONET_INSTANCE_TYPE', value: 't3.micro', note: 'provision instance' },
    { name: 'CHRONONET_RISK_THRESHOLD', value: '0.8', note: 'migration trigger line' },
    { name: 'CHRONONET_ALLOW_REAL_EC2', value: 'false', note: 'simulate mode' },
    { name: 'CHRONONET_DISABLE_ALERTS', value: 'false', note: 'SNS publish gate' },
    { name: 'CHRONONET_CHECKPOINT_BUCKET', value: 'chrononet-checkpoints', note: 'S3 bucket' },
    { name: 'CHRONONET_SNS_TOPIC', value: 'chrononet-alerts', note: 'alert channel' },
    { name: 'CHRONONET_RUN_ID', value: status?.run_id || dash, note: 'active run' },
    { name: 'CHRONONET_VM_ID', value: status?.vm_id || dash, note: 'active node' },
    {
      name: 'VITE_API_BASE_URL',
      value: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
      note: 'dashboard API base',
    },
    { name: 'DASHBOARD_POLL_STATUS', value: '3s', note: 'frontend /status cadence', mono: true, span: true },
    { name: 'DASHBOARD_POLL_HISTORY', value: '10s', note: 'frontend /history cadence', mono: true, span: true },
  ];

  return (
    <>
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <Panel title="active node">
          {nodeFields.map((f) => (
            <Field key={f.label} label={f.label} value={f.value} mono={f.mono ?? true} />
          ))}
        </Panel>

        <Panel title="checkpoint metadata">
          {checkpointFields.map((f) => (
            <Field key={f.label} label={f.label} value={f.value} mono={f.mono ?? true} />
          ))}
        </Panel>
      </div>

      <section className="panel mt-5 p-5" aria-label="Orchestration environment">
        <p className="panel-label">orchestration env</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-mid text-muted">
                <th className="px-2 py-2 text-left font-mono font-medium">variable</th>
                <th className="px-2 py-2 text-left font-mono font-medium">value</th>
                <th className="px-2 py-2 text-left font-mono font-medium">note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-mid">
              {envRows.map((e) => (
                <tr key={e.name}>
                  <td className="px-2 py-2 font-mono text-primary">{e.name}</td>
                  <td className="px-2 py-2 font-mono text-primary">{e.value}</td>
                  <td className="px-2 py-2 text-muted">{e.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">
          defaults from shared/constants.py — the hub overrides these at boot via
          CHRONONET_* environment variables.
        </p>
      </section>
    </>
  );
}