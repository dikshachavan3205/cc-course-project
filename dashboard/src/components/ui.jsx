import { NavLink } from "react-router-dom";

const ICON_PATHS = {
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </>
  ),
  box: (
    <>
      <path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z" />
      <path d="M3 7.5 12 12l9-4.5M12 12v9" />
    </>
  ),
  bookmark: (
    <>
      <path d="M6 4h12a1 1 0 0 1 1 1v16l-7-4-7 4V5a1 1 0 0 1 1-1Z" />
      <path d="M9 9h6" />
    </>
  ),
  swap: (
    <>
      <path d="M8 3 4 7l4 4" />
      <path d="M4 7h13" />
      <path d="M16 21l4-4-4-4" />
      <path d="M20 17H7" />
    </>
  ),
  pulse: (
    <>
      <path d="M3 12h4l2.5-6 4 12 2.5-6h5" />
    </>
  ),
  zap: (
    <>
      <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 12a8 8 0 1 1-3-6.2" />
      <path d="M20 3v5h-5" />
    </>
  ),
  copy: (
    <>
      <rect x="9" y="9" width="12" height="12" rx="1" />
      <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </>
  ),
};

export function Icon({ name, className = "h-4 w-4" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {ICON_PATHS[name] || null}
    </svg>
  );
}

export function alpha(color, a = 0.12) {
  if (!color) return "transparent";
  let m = color.match(/^#([0-9a-f]{6})$/i);
  if (m) {
    const n = parseInt(m[1], 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  m = color.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
  if (m) return `rgba(${m[1]},${m[2]},${m[3]},${a})`;
  return color;
}

export function Panel({ children, className = "", ...rest }) {
  return (
    <section className={`panel p-5 ${className}`} {...rest}>
      {children}
    </section>
  );
}

export function PanelLabel({ children, className = "" }) {
  return <span className={`panel-label ${className}`}>{children}</span>;
}

export function StatCard({ label, value, sub, accent, icon }) {
  return (
    <div className="panel relative p-4">
      <span
        className="absolute top-3 right-3 grid h-8 w-8 place-items-center rounded-full"
        style={{ background: alpha(accent, 0.12), color: accent }}
        aria-hidden="true"
      >
        <Icon name={icon} className="h-4 w-4" />
      </span>
      <span className="panel-label pr-10">{label}</span>
      <div className="num mt-2 truncate text-xl leading-none" title={value}>
        {value}
      </div>
      {sub ? <div className="mt-1.5 truncate text-xs text-muted">{sub}</div> : null}
    </div>
  );
}

function pillTone(status) {
  const s = String(status || "").toLowerCase();
  if (s.includes("completed")) return { color: "var(--risk-low)" };
  if (s.includes("fail")) return { color: "var(--risk-high)" };
  if (s.includes("noop")) return { color: "var(--risk-medium)" };
  if (s.includes("started") || s.includes("running") || s.includes("migrating"))
    return { color: "var(--risk-medium)" };
  return { color: "var(--text-muted)" };
}

export function StatusPill({ status }) {
  const tone = pillTone(status);
  return (
    <span
      className="inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium"
      style={{
        color: tone.color,
        background: alpha(tone.color, 0.14),
        border: `1px solid ${alpha(tone.color, 0.35)}`,
      }}
    >
      {status || "unknown"}
    </span>
  );
}

export function OfflineBanner() {
  return (
    <div className="border-b border-border-mid/30 bg-surface/60 px-4 py-2 text-sm text-muted">
      Can't reach the ChronoNet backend — start the FastAPI server and this will reconnect
      automatically
    </div>
  );
}

export function ConnectionDot({ connected }) {
  const color = connected ? "var(--risk-low)" : "var(--risk-high)";
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted">
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: color, boxShadow: connected ? `0 0 6px ${alpha(color, 0.7)}` : "none" }}
        aria-hidden="true"
      />
      {connected ? "Online" : "Offline"}
    </span>
  );
}

export function DemoBadge() {
  return (
    <span
      className="inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-semibold tracking-wide"
      style={{
        color: "var(--risk-medium)",
        background: alpha("var(--risk-medium)", 0.16),
        border: `1px solid ${alpha("var(--risk-medium)", 0.4)}`,
      }}
    >
      Demo data
    </span>
  );
}

export function NavTabs({ items }) {
  return (
    <nav className="flex gap-1" aria-label="Section tabs">
      {items.map((item) => (
        <NavTab key={item.to} to={item.to}>
          {item.label}
        </NavTab>
      ))}
    </nav>
  );
}

function NavTab({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-sm px-3 py-1.5 text-sm transition-colors ${
          isActive ? "bg-elevated text-primary" : "text-muted hover:bg-surface hover:text-primary"
        }`
      }
    >
      {children}
    </NavLink>
  );
}