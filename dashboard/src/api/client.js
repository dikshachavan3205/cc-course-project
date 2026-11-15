const DEFAULT_BASE = "http://127.0.0.1:8000";

export function resolveApiBase() {
  return (import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE).replace(/\/+$/, "");
}

async function parse(resp) {
  const text = await resp.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!resp.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : `${resp.status} ${resp.statusText}`;
    throw new Error(`ChronoNet API ${resp.status}: ${detail}`);
  }
  return body;
}

// GET /status — contract shape #2
export async function fetchStatus(base = resolveApiBase()) {
  const resp = await fetch(`${base}/status`);
  return parse(resp);
}

// GET /history?run_id=... — newest first; requires the run_id query param.
export async function fetchHistory(runId, base = resolveApiBase()) {
  const url = `${base}/history?run_id=${encodeURIComponent(runId)}`;
  const resp = await fetch(url);
  return parse(resp);
}

// POST /interruption (shape #3). Returns the migration summary incl. timeline.
export async function triggerInterruption(payload, triggeredBy, base = resolveApiBase()) {
  const resp = await fetch(`${base}/interruption`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-ChronoNet-Trigger": triggeredBy,
    },
    body: JSON.stringify(payload),
  });
  return parse(resp);
}

// GET /predictions?run_id=... — risk history (newest first) from chrononet-predictions.
export async function fetchPredictions(runId, base = resolveApiBase()) {
  const resp = await fetch(`${base}/predictions?run_id=${encodeURIComponent(runId)}`);
  return parse(resp);
}

// GET /config — thresholds and provision mode.
export async function fetchConfig(base = resolveApiBase()) {
  const resp = await fetch(`${base}/config`);
  return parse(resp);
}

// GET /checkpoint-status?run_id=... — latest live checkpoint in S3.
export async function fetchCheckpointStatus(runId, base = resolveApiBase()) {
  const resp = await fetch(`${base}/checkpoint-status?run_id=${encodeURIComponent(runId)}`);
  return parse(resp);
}
