// ChronoNet brand mark — a bespoke, vector-style interlocking geometric
// clock/node icon. Neutral on purpose: it is drawn from the base token layer
// (--text-primary / --text-muted) only — risk accents stay reserved for the
// gauge and status pills.
//
// Geometry: a clock rim with tick marks, a slanted hand pair, a dashed
// orbital ring rotated over the rim (the "interlock"), and two node dots
// parked where the orbit meets the face.
export default function BrandLogo() {
  const primary = 'var(--text-primary)';
  const muted = 'var(--text-muted)';

  return (
    <svg
      viewBox="0 0 32 32"
      className="h-9 w-9 shrink-0"
      role="img"
      aria-label="ChronoNet brand mark"
    >
      {/* clock rim */}
      <circle cx="16" cy="16" r="13" fill="none" stroke={primary} strokeWidth="2" />
      {/* interlocking orbital ring */}
      <circle
        cx="16"
        cy="16"
        r="13"
        fill="none"
        stroke={muted}
        strokeWidth="1"
        strokeDasharray="3 5"
        strokeLinecap="round"
        transform="rotate(36 16 16)"
      />
      {/* hands */}
      <line x1="16" y1="16" x2="16" y2="7" stroke={primary} strokeWidth="2" strokeLinecap="round" />
      <line x1="16" y1="16" x2="21.5" y2="20.5" stroke={primary} strokeWidth="2" strokeLinecap="round" />
      {/* nodes at the orbit/face junction */}
      <circle cx="6" cy="23.5" r="2" fill={primary} />
      <circle cx="26.5" cy="8.5" r="2" fill={primary} />
    </svg>
  );
}