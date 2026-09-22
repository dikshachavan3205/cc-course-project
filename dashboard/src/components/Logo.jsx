export default function Logo({ compact = false }) {
  return (
    <span className="flex items-center gap-2.5 select-none">
      <svg
        width="30"
        height="30"
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        className="shrink-0"
      >
        <path d="M8 22 Q16 8 24 14" stroke="#8FB0C9" strokeWidth="1.5" fill="none" />
        <circle cx="8" cy="22" r="5" fill="#1A3F75" stroke="#C9DAE8" strokeWidth="1.5" />
        <circle cx="24" cy="14" r="5" fill="#1A3F75" stroke="#5FBF8F" strokeWidth="1.5" />
      </svg>
      {!compact && (
        <span className="text-base font-semibold tracking-tight text-primary">
          Chrono<span style={{ color: "var(--risk-low)" }}>Net</span>
          <span className="text-primary">.</span>
        </span>
      )}
    </span>
  );
}