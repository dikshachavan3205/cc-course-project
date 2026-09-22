import { alpha } from "./ui.jsx";
import { fmtDateTime, stepNumber } from "../lib/time.js";

const FILLED = "var(--risk-low)";
const TRACK = "rgba(77,114,143,0.28)";

function cleanName(name) {
  if (typeof name !== "string") return name;
  return name.replace(/^\d+\/7\s*/, "").replace(/-/g, " ");
}

function toSorted(steps) {
  const uniq = [...(steps || [])]
    .filter(Boolean)
    .filter((s, i, arr) => arr.findIndex((o) => o.name === s.name) === i);
  return uniq.sort((a, b) => (a.elapsed_ms || 0) - (b.elapsed_ms || 0));
}

// Vertical, filling-connector 7-step stepper for the Simulate page.
export function StepStepper({ steps, status }) {
  const list = toSorted(steps);
  if (!list.length) return null;

  return (
    <ol className="mt-2">
      {list.map((s, i) => {
        const number = stepNumber(s.name) || i + 1;
        const filled = status === "completed" || i < list.length - 1;
        const isLast = i === list.length - 1;
        return (
          <li key={`${s.name}-${i}`} className="relative flex gap-3 pb-5 last:pb-0">
            <div className="flex flex-col items-center">
              <span
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs font-medium"
                style={{
                  borderColor: alpha(FILLED, 0.5),
                  color: filled ? FILLED : "var(--text-muted)",
                  background: filled ? alpha(FILLED, 0.12) : "var(--bg-surface)",
                }}
              >
                <span className="num">{String(number).padStart(2, "0")}</span>
              </span>
              {!isLast && (
                <span
                  className="w-px flex-1 transition-colors"
                  style={{
                    background: filled ? alpha(FILLED, 0.45) : TRACK,
                  }}
                  aria-hidden="true"
                />
              )}
            </div>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-sm text-primary">{cleanName(s.name)}</span>
                <span className="num text-xs text-muted">
                  +{Number(s.elapsed_ms || 0).toFixed(1)} ms
                </span>
              </div>
              {s.at_utc ? <div className="mt-0.5 text-xs text-muted">{fmtDateTime(s.at_utc)}</div> : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// Compact horizontal chips for expanding a migration row.
export function MiniSteps({ steps }) {
  const list = toSorted(steps).slice(0, 7);
  if (!list.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      {list.map((s, i) => {
        const number = stepNumber(s.name) || i + 1;
        return (
          <span
            key={`${s.name}-${i}`}
            className="inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs"
            style={{
              borderColor: alpha("var(--risk-low)", 0.35),
              background: alpha("var(--risk-low)", 0.08),
              color: "var(--text-primary)",
            }}
            title={`${s.name} · +${Number(s.elapsed_ms || 0).toFixed(1)} ms`}
          >
            <span className="num text-[10px]" style={{ color: "var(--risk-low)" }}>
              {String(number).padStart(2, "0")}
            </span>
            {cleanName(s.name)}
          </span>
        );
      })}
    </div>
  );
}