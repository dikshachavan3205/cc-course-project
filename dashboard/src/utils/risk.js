// Risk display scale. The model's real output spans roughly 4-25%, so the
// thresholds mirror shared/constants.py (RISK_THRESHOLD_WARN / RISK_THRESHOLD),
// not a generic 0-100 scale.
export const RISK_WARN = 10;
export const RISK_MIGRATE = 15;
export const RISK_SCALE_MAX = 30; // the risk arc is full at this value

const STOPS = [
  { at: 0, r: 95, g: 191, b: 143 },
  { at: RISK_WARN, r: 224, g: 168, b: 77 },
  { at: RISK_MIGRATE, r: 224, g: 101, b: 77 },
];

export function getRiskColor(riskPercent) {
  const v = Math.max(0, Math.min(RISK_MIGRATE, Number(riskPercent) || 0));
  let i = 0;
  while (i < STOPS.length - 2 && v > STOPS[i + 1].at) i += 1;
  const a = STOPS[i];
  const b = STOPS[i + 1];
  const x = (v - a.at) / (b.at - a.at || 1);
  const lerp = (p, q) => Math.round(p + (q - p) * x);
  return `rgb(${lerp(a.r, b.r)}, ${lerp(a.g, b.g)}, ${lerp(a.b, b.b)})`;
}

export function getRiskLabel(riskPercent) {
  if (riskPercent < RISK_WARN) return "Healthy";
  if (riskPercent < RISK_MIGRATE) return "Elevated";
  return "Critical";
}
