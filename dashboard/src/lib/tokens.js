// Runtime token reader — chart colors, metric interpolation, and any JS that
// needs a color value reads tokens.css via CSS variables so the CSS file stays
// the single source of truth. Falls back to the spec hex values defensively.

const FALLBACKS = {
  'risk-low': '#5FBF8F',
  'risk-medium': '#E0A84D',
  'risk-high': '#E0654D',
  'text-primary': '#C9DAE8',
  'text-muted': '#8FB0C9',
  'border-mid': '#4D728F',
};

const _cache = {};

function parseHex(hex) {
  const m = /^#([0-9a-fA-F]{6})$/.exec(String(hex).trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function getValue(name) {
  if (name in _cache) return _cache[name];
  let raw = '';
  if (typeof document !== 'undefined') {
    raw = getComputedStyle(document.documentElement)
      .getPropertyValue(`--${name}`)
      .trim();
  }
  const value = raw || FALLBACKS[name] || '';
  _cache[name] = value;
  return value;
}

/** RGB array for a token, e.g. readCssVarRgb('text-primary') -> [201, 218, 232] */
export function readCssVarRgb(name) {
  return parseHex(getValue(name)) ?? parseHex(FALLBACKS[name]) ?? [0, 0, 0];
}

/** css color string for an [r,g,b] array with optional alpha. */
export function rgbString(rgb, alpha = 1) {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

/** Linear interpolation between two [r,g,b] tuples. */
export function lerpRgb(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

const clamp01 = (v) => Math.max(0, Math.min(1, v));

/**
 * Continuous risk color across the three token bands:
 *   0-40 low→medium, 40-70 medium→high, >=70 high.
 */
export function interpolateRisk(colors, value) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  if (v <= 40) return lerpRgb(colors.low, colors.middle, clamp01(v / 40));
  if (v < 70) return lerpRgb(colors.middle, colors.high, clamp01((v - 40) / 30));
  return colors.high;
}