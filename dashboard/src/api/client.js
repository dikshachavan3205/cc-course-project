// ChronoNet API client — axios instance pointed at the FastAPI hub.
//
// Base URL comes from VITE_API_BASE_URL (Vite env, .env or shell) and only
// falls back to the local dev backend when unset — never hardcoded in JS.
// The backend runs CORS with allow_origins="*" by default, so direct
// cross-origin calls work in dev and in static production.
//
// Endpoints (contracts in shared/contracts.md):
//   GET  /status        shape #2
//   GET  /history       chrononet-migrations rows (newest first)
//   POST /interruption  shape #3 (RiskEvent) -> migration summary
import axios from 'axios';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';

const configured = (import.meta.env.VITE_API_BASE_URL || '').trim();
const BASE_URL = configured.replace(/\/+$/, '') || DEFAULT_BASE_URL;

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

/** GET /status — current run/VM state + metrics (contract shape #2). */
export async function getStatus() {
  const { data } = await client.get('/status');
  return data;
}

/** GET /history?run_id= — migration history (chrononet-migrations rows). */
export async function getHistory(run_id) {
  const { data } = await client.get('/history', { params: { run_id } });
  return data;
}

/** POST /interruption — inject a high-risk event (contract shape #3). */
export async function triggerInterruption(payload) {
  const { data } = await client.post('/interruption', payload);
  return data;
}

export default client;