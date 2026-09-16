// Migration counter for the run — compact stat panel. Numeric readout in
// IBM Plex Mono (tabular figures). Source: GET /status migration_count.
export default function Migrations({ count = 0 }) {
  const value = Number.isFinite(Number(count)) ? Number(count) : 0;

  return (
    <section className="panel p-5" aria-label="Migration count">
      <p className="panel-label">migrations</p>
      <p className="mt-2 font-mono text-2xl text-primary">{value}</p>
    </section>
  );
}