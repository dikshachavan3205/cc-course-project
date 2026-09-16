// Q-Deck view switcher — a border-bottom tab bar directly beneath the header.
//
// Pure presentational: App owns the active id (local component memory) and the
// polling hook, so switching tabs never remounts usePolling — the connection
// state, rolling chart buffer, and /history data all survive the switch.
//
// Active tab = 2px primary underline + primary text; inactive tabs sit muted
// and gain primary on hover. No risk accents here.
export const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'telemetry', label: 'Telemetry Stream' },
  { id: 'audit', label: 'Migration Audit' },
  { id: 'system', label: 'System Health & Config' },
];

export default function TabBar({ active = 'overview', onChange }) {
  return (
    <nav role="tablist" aria-label="Deck views" className="border-b border-border-mid">
      <div className="flex gap-1 overflow-x-auto">
        {TABS.map((t) => {
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onChange(t.id)}
              className={`shrink-0 border-b-2 px-3 py-2 text-sm transition-colors duration-200 ${
                isActive
                  ? 'border-primary font-semibold text-primary'
                  : 'border-transparent text-muted hover:text-primary'
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}