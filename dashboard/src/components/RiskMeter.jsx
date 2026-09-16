// Risk meter — the one prominent card in the UI (rounded-prominent + glow).
// SVG arc gauge driven by /status risk_percent (0-100). Stroke color is
// interpolated continuously across the three risk tokens (no hard cutoff
// jump); the headline number is IBM Plex Mono. A live status badge
// (Nominal / Elevated / Critical) rides under the gauge with its border, dot,
// and text tinted to the current risk color, and the card's box-shadow is a
// dynamic backlight tuned to that same interpolated color — so the whole card
// "breathes" with risk level instead of sitting in a static glow.
//
// A thin threshold tick marks RISK_THRESHOLD (80) on the arc track.
import useAnimatedValue from '../hooks/useAnimatedValue';
import { interpolateRisk, readCssVarRgb, rgbString } from '../lib/tokens';

const SWEEP_UNITS = 75; // 270° of 360° (=100 units) drawn, gap at bottom
const ROTATE = 135;     // shift arc start to bottom-left
const THRESHOLD_FRAC = 80 / 100; // matches shared/constants.RISK_THRESHOLD

function statusWord(value) {
  if (value < 40) return 'Nominal';
  if (value < 70) return 'Elevated';
  return 'Critical';
}

export default function RiskMeter({ riskPercent = 0 }) {
  const colors = {
    low: readCssVarRgb('risk-low'),
    middle: readCssVarRgb('risk-medium'),
    high: readCssVarRgb('risk-high'),
  };
  const target = Number(riskPercent) || 0;
  const value = useAnimatedValue(target);
  const word = statusWord(target);
  const rgba = (rgb, a = 1) => rgbString(rgb, a);
  const accent = rgba(interpolateRisk(colors, value));
  const accentTransparent = rgba(interpolateRisk(colors, value), 0.28);

  // Threshold tick geometry — a short radial line at the 80% position on the
  // 270° sweep (start angle 135°, clocking through the top).
  const a = ((ROTATE + THRESHOLD_FRAC * 270) * Math.PI) / 180;
  const tick = (r) => [100 + r * Math.cos(a), 100 + r * Math.sin(a)];
  const inner = tick(64);
  const outer = tick(86);

  return (
    <section
      className="panel-prominent relative overflow-hidden p-6"
      aria-label={`Risk meter — ${word}`}
      style={{ boxShadow: `0 0 64px ${rgba(interpolateRisk(colors, value), 0.35)}` }}
    >
      {/* atmospheric backlight — radial halo dyed to the interpolated risk
          color, clipped inside the card (overflow-hidden above). */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-10 top-4 bottom-14"
        style={{
          background: `radial-gradient(closest-side, ${accentTransparent}, transparent 72%)`,
        }}
      />

      <p className="panel-label">risk</p>
      <div className="relative mt-1 flex flex-col items-center">
        <svg viewBox="0 0 200 150" className="w-full" role="img" aria-label={`Risk ${word}, ${Math.round(value)} percent`}>
          <g transform={`rotate(${ROTATE} 100 100)`}>
            <circle
              pathLength={100}
              cx={100}
              cy={100}
              r={75}
              fill="none"
              stroke={rgba(readCssVarRgb('border-mid'), 0.25)}
              strokeWidth={10}
              strokeDasharray={`${SWEEP_UNITS} ${100 - SWEEP_UNITS}`}
            />
            <circle
              pathLength={100}
              cx={100}
              cy={100}
              r={75}
              fill="none"
              stroke={rgba(interpolateRisk(colors, value))}
              strokeWidth={10}
              strokeLinecap="round"
              strokeDasharray={`${(value / 100) * SWEEP_UNITS} ${100}`}
            />
          </g>
          {/* threshold marker — neutral token, not a risk accent */}
          <line
            x1={inner[0]} y1={inner[1]}
            x2={outer[0]} y2={outer[1]}
            stroke={rgba(readCssVarRgb('text-primary'), 0.45)}
            strokeWidth={3}
            strokeLinecap="round"
          />
          <text
            x={100}
            y={144}
            textAnchor="middle"
            fontFamily="IBM Plex Mono, ui-monospace, monospace"
            fontSize={40}
            fill={rgba(readCssVarRgb('text-primary'))}
          >
            {Math.round(value)}%
          </text>
        </svg>

        {/* real-time status badge — border + dot + word in the live risk color */}
        <span
          className="mt-3 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium"
          style={{ borderColor: rgba(interpolateRisk(colors, value), 0.55), color: accent }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accent }} />
          {word}
        </span>
        <p className="mt-1.5 font-mono text-xs text-muted">threshold 80</p>
      </div>
    </section>
  );
}