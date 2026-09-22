export function fmtSeconds(value, digits = 2) {
  const n = Number.isFinite(value) ? value : 0;
  return `${n.toFixed(digits)}s`;
}

export function fmtPct(value, digits = 1) {
  const n = Number.isFinite(value) ? value : 0;
  return `${n.toFixed(digits)}%`;
}

export function todayHMS(ts = Date.now()) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour12: false });
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, Math.floor((now - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ${m % 60}m ago`;
}

export function stepNumber(name) {
  const m = typeof name === "string" ? name.match(/^(\d+)\/7/) : null;
  return m ? parseInt(m[1], 10) : null;
}

// History rows persist the timeline as a JSON string; the live POST response
// returns it as an object array. Normalize both into a step list.
export function parseTimeline(value) {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      // fall through
    }
  }
  return null;
}