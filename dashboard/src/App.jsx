// ChronoNet Q-Deck — multi-tab cloud command center.
//
// Brand lockup (ChronoNet mark + Q-DECK v2.4 // PROD badge) → connection pulse
// + region → border-bottom tab bar → view. Four views — Overview, Telemetry
// Stream, Migration Audit, System Health & Config — all rendered from a single
// usePolling() instance mounted here at the top of the tree. Because polling
// never lives inside a tab, switching views is instant and never resets the
// connection state or the rolling chart buffer; the active tab id is plain
// component state (local memory), lost only on a full page reload.
//
//  * /status  every 3s — arc, stats, chart buffer, connection dot
//  * /history every 10s — migrations / checkpoint metadata
import { useEffect, useRef, useState } from 'react';

import Header from './components/Header';
import TabBar from './components/TabBar';
import ErrorBoundary from './components/ErrorBoundary';

import OverviewView from './views/OverviewView';
import TelemetryView from './views/TelemetryView';
import MigrationAuditView from './views/MigrationAuditView';
import SystemConfigView from './views/SystemConfigView';

import usePolling from './hooks/usePolling';
import { triggerInterruption } from './api/client';

// A convenience default so the demo trigger works against the dev backend
// without configuring env vars (backend falls back to run-local-dev anyway).
const DEMO_EVENT = {
  run_id: 'run-local-dev',
  vm_id: 'vm-local-dev',
  risk_percent: 100,
  threshold_exceeded: true,
  timestamp: () => new Date().toISOString(),
};

// How long the inline trigger confirmation/error stays visible (brief flash).
const FEEDBACK_FLASH_MS = 4000;

export default function App() {
  const { status, history, connected, series, refreshHistory, refreshStatus } = usePolling();

  const region = status?.region || '—';

  const [activeTab, setActiveTab] = useState('overview');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null); // { kind: 'ok' | 'error', text }
  const feedbackTimer = useRef(null);

  // Unmount safety: never let a pending "clear feedback" fire after teardown.
  useEffect(() => () => clearTimeout(feedbackTimer.current), []);

  const flash = (kind, text) => {
    setFeedback({ kind, text });
    clearTimeout(feedbackTimer.current);
    feedbackTimer.current = setTimeout(() => setFeedback(null), FEEDBACK_FLASH_MS);
  };

  const handleTrigger = async () => {
    if (busy) return;
    setBusy(true);
    setFeedback(null);
    try {
      const res = await triggerInterruption({
        ...DEMO_EVENT,
        timestamp: DEMO_EVENT.timestamp(),
      });
      const st = res?.status || 'completed';
      if (st === 'noop') {
        flash('ok', 'event under threshold — no migration needed');
      } else if (st === 'failed') {
        flash('error', 'migration failed — check the history panel');
      } else {
        const id = res?.migration_id && res.migration_id !== 'none' ? ` — ${res.migration_id}` : '';
        flash('ok', `migration ${st}${id}`);
      }
      // Pull the fresh row into the table immediately instead of waiting out
      // the 10s history cadence, and hit /status so the risk gauge settles to
      // its post-migration value right now instead of on the next 3s tick.
      void refreshHistory().catch(() => {});
      void refreshStatus().catch(() => {});
    } catch (err) {
      flash('error', `couldn't trigger migration — ${err?.message || 'request failed'}`);
    } finally {
      setBusy(false);
    }
  };

  // The checkpoint panel reads the newest migration row (chrononet-migrations
  // is returned newest-first): its timestamp is the last checkpoint time and
  // checkpoint_key is the S3 object key it was restored from. /status (shape
  // #2) deliberately has no checkpoint fields, so /history is the source.
  const lastMigration = history[0] ?? null;
  const checkpointTime = lastMigration?.timestamp ?? null;
  const checkpointKey = lastMigration?.checkpoint_key ?? null;

  return (
    <div className="min-h-screen bg-base px-6 py-6 text-primary">
      <div className="mx-auto max-w-7xl">
        <Header
          connected={connected}
          region={region}
          onTrigger={handleTrigger}
          busy={busy}
          feedback={feedback}
        />

        {/* tabs sit directly beneath the header — instant, local-memory state */}
        <div className="mt-5">
          <TabBar active={activeTab} onChange={setActiveTab} />
        </div>

        {/* Quiet offline banner — calm and informative, no flashing. */}
        {connected === false && (
          <div
            className="mt-5 flex items-center gap-3 border border-border-mid bg-surface px-4 py-3 text-sm text-muted"
            role="status"
          >
            <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full bg-conn-off" />
            <span>
              Can't reach the ChronoNet backend — start the FastAPI server
              (uvicorn data_backend.main:app) and this will reconnect automatically.
            </span>
          </div>
        )}

        <main className="mt-6">
          {/* keyed per tab: a crash in one view never blanks the others, and
              switching tabs resets the boundary */}
          <ErrorBoundary key={activeTab}>
            {activeTab === 'overview' && (
              <OverviewView
                status={status}
                series={series}
                history={history}
                checkpointTime={checkpointTime}
                checkpointKey={checkpointKey}
                lastMigration={lastMigration}
                onShowAll={() => setActiveTab('audit')}
              />
            )}

            {activeTab === 'telemetry' && <TelemetryView series={series} />}

            {activeTab === 'audit' && <MigrationAuditView migrations={history} />}

            {activeTab === 'system' && (
              <SystemConfigView
                status={status}
                checkpointTime={checkpointTime}
                checkpointKey={checkpointKey}
                lastMigration={lastMigration}
              />
            )}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}