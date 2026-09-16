// Last measured migration downtime — compact stat panel. Numeric readout in
// IBM Plex Mono (tabular figures) with a muted unit. Source: GET /status
// last_downtime_seconds (contract shape #2), two decimal places.
export default function LastDowntime({ seconds = 0 }) {
  const value = Number.isFinite(Number(seconds)) ? Number(seconds) : 0;

  return (
    <section className="panel p-5" aria-label="Last downtime">
      <p className="panel-label">last downtime</p>
      <p className="mt-2 font-mono text-2xl text-primary">
        {value.toFixed(2)}
        <span className="ml-1 text-sm text-muted">s</span>
      </p>
    </section>
  );
}