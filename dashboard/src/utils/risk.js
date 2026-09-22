// Risk color scale used across every display surface.
export function getRiskColor(riskPercent) {
  const clamp = (v) => Math.max(0, Math.min(1, v));
  const t = clamp(riskPercent / 100);
  // lerp stops: low (0) -> medium (0.4) -> high (0.7) -> 100
  const stops = [
    { at: 0.0, r: 95, g: 191, b: 143 },
    { at: 0.4, r: 224, g: 168, b: 77 },
    { at: 0.7, r: 224, g: 101, b: 77 },
  ];
  const lerp = (a, b, x) => Math.round(a + (b - a) * x);
  let left = stops[0];
  let right = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i += 1) {
    if (t >= stops[i].at && t <= stops[i + 1].at) {
      left = stops[i];
      right = stops[i + 1];
    }
  }
  const span = right.at - left.at || 1;
  const x = (t - left.at) / span;
  return `rgb(${lerp(left.r, right.r, x)}, ${lerp(left.g, right.g, x)}, ${lerp(left.b, right.b, x)})`;
}

export function getRiskLabel(riskPercent) {
  if (riskPercent < 40) return "Healthy";
  if (riskPercent < 70) return "Elevated";
  return "Critical";
}