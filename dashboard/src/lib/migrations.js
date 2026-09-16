// Migration-row presentation helpers shared by the overview table and the
// full Migration Audit view. Keeps the risk-accent policy in one place: these
// pill classes are the ONLY sanctioned use of risk-low/risk-high outside the
// risk gauge.

export const TONES = {
  ok: 'bg-risk-low text-base',
  fail: 'bg-risk-high text-base',
  unknown: 'bg-muted text-base',
};

export function statusTone(status) {
  const s = String(status || '').toLowerCase();
  if (s.includes('completed') || s.includes('ok') || s.includes('success')) return 'ok';
  if (s.includes('failed') || s.includes('error')) return 'fail';
  return 'unknown';
}

/** Downtime in seconds, 2 decimal places; "—" when unparseable. */
export function fmtDowntime(seconds) {
  const v = Number(seconds);
  return `${Number.isFinite(v) ? v.toFixed(2) : '—'}`;
}

/** Risk percentage, 1 decimal; "—" when unparseable. */
export function fmtRisk(riskPercent) {
  const v = Number(riskPercent);
  return Number.isFinite(v) ? `${v.toFixed(1)}%` : '—';
}