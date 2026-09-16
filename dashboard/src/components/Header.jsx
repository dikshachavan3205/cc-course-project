// Q-Deck command bar — ChronoNet brand lockup (interlocking clock/node mark +
// bold wordmark in Space Grotesk) with the elite version badge, plus the live
// connection pulse, region chip, and the primary "Trigger event" action with
// an inline result line. Pure presentational; all state is owned by App.
//
// Risk accents (risk-low/medium/high) are NOT used here — the reachability
// dot and feedback use --conn-on/--conn-off (connection token layer), which
// keeps status semantics separate from risk semantics.
import BrandLogo from './BrandLogo';

export default function Header({ connected, region, onTrigger, busy, feedback = null }) {
  // connected === null means "first probe hasn't returned yet".
  const dotStatus = connected === null
    ? { dot: 'bg-muted', label: 'checking' }
    : connected
      ? { dot: 'bg-conn-on', label: 'connected' }
      : { dot: 'bg-conn-off', label: 'offline' };

  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4 border-b border-border-mid pb-5">
      {/* brand lockup */}
      <div className="flex items-center gap-3">
        <BrandLogo />
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="font-sans text-xl font-bold tracking-tight text-primary">
              ChronoNet
            </h1>
            <span className="rounded-data border border-border-mid px-2 py-0.5 font-mono text-xs tracking-wide text-muted">
              Q-DECK v2.4 // PROD
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted">Q-Deck · spot migration control</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        {/* inline result/error line — inside the header, no toasts */}
        {feedback && (
          <span
            role={feedback.kind === 'error' ? 'alert' : 'status'}
            className={`text-sm ${feedback.kind === 'ok' ? 'text-conn-on' : 'text-conn-off'}`}
          >
            {feedback.text}
          </span>
        )}

        {/* connection dot — derived from /status reachability */}
        <span className="flex items-center gap-2 text-sm text-muted">
          <span
            aria-hidden="true"
            className={`inline-block h-2 w-2 rounded-full transition-colors duration-300 ${dotStatus.dot}`}
          />
          {dotStatus.label}
        </span>

        {/* region readout — mono, hairline-bordered chip */}
        <span className="rounded-data border border-border-mid px-3 py-1 font-mono text-sm text-primary">
          {region}
        </span>

        <button
          type="button"
          onClick={onTrigger}
          disabled={busy}
          aria-busy={busy}
          className="flex items-center gap-2 rounded-prominent border border-border-mid bg-surface px-5 py-2 text-sm font-semibold text-primary transition-all duration-150 hover:border-border-mid-strong hover:bg-base active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy && (
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="var(--border-mid)" strokeWidth="2.5" opacity="0.4" />
              <path d="M21 12a9 9 0 0 0-9-9" stroke="var(--text-primary)" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          )}
          {busy ? 'Triggering…' : 'Trigger event'}
        </button>
      </div>
    </header>
  );
}