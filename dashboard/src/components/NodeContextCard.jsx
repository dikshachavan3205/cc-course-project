// Node Context & Checkpoint Hub — the right-column identity block.
// Top: active node attributes (run id, vm id, region) from /status.
// Below a hairline divider: the checkpoint hub — S3 key this node resumed
// from (newest /history row) and its age as a live relative timestamp that
// re-renders every second without refetching.
import useNow from '../hooks/useNow';
import { relativeTime } from '../lib/time';

const dash = '—';

export default function NodeContextCard({ status, checkpointTime = null, checkpointKey = null }) {
  const now = useNow(1000); // keeps the relative age rolling without refetching
  const age = relativeTime(checkpointTime, now);

  // status arrives as null until the first /status poll lands — never assume
  // it is an object (a default parameter only covers undefined, not null).
  const s = status ?? {};

  return (
    <section className="panel p-5" aria-label="Node context and checkpoint hub">
      <p className="panel-label">node · checkpoint</p>

      <dl className="mt-3 space-y-3">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <div className="col-span-2">
            <dt className="text-sm text-muted">run</dt>
            <dd className="mt-0.5 break-all font-mono text-sm text-primary">
              {s.run_id || dash}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted">vm</dt>
            <dd className="mt-0.5 break-all font-mono text-sm text-primary">
              {s.vm_id || dash}
            </dd>
          </div>
          <div>
            <dt className="text-sm text-muted">region</dt>
            <dd className="mt-0.5 font-mono text-sm text-primary">
              {s.region || dash}
            </dd>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-3 border-t border-border-mid pt-3">
          <div>
            <dt className="text-sm text-muted">checkpoint age</dt>
            <dd className="mt-0.5 font-mono text-sm text-primary">{age ?? dash}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted">bucket</dt>
            <dd className="mt-0.5 font-mono text-sm text-primary">chrononet-checkpoints</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-sm text-muted">s3 key</dt>
            <dd className="mt-0.5 break-all font-mono text-sm text-primary">
              {checkpointKey || dash}
            </dd>
          </div>
        </div>
      </dl>
    </section>
  );
}