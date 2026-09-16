// Polling hook — owns the dashboard's data cadence and connectivity signal.
//
//   * /status  every 3s  (drives the arc, stats, chart buffer, connection dot)
//   * /history every 10s (migrations change far less often, no point hammering)
//
// `connected` flips false only after 2 CONSECUTIVE failed /status polls — a
// single slow response must not flicker the top bar to "offline". Any success
// resets the counter and flips it (back) on. History failures never affect
// connectivity: /history hiccups are independent of backend health.
//
// Returns { status, history, connected, error, series, refreshHistory }.
import { useCallback, useEffect, useRef, useState } from 'react';

import { getHistory, getStatus } from '../api/client';

const STATUS_INTERVAL_MS = 3000;
const HISTORY_INTERVAL_MS = 10_000;
const FAILS_BEFORE_OFFLINE = 2;
const SERIES_CAP = 60; // ~5 minutes of points at the 3s cadence

const toNum = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

export default function usePolling() {
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [connected, setConnected] = useState(null); // null = checking
  const [error, setError] = useState(null);
  const [series, setSeries] = useState([]);

  const failsRef = useRef(0);
  const runIdRef = useRef('run-local-dev');

  // Status poll.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await getStatus();
        if (!alive) return;
        failsRef.current = 0;
        setConnected(true);
        setError(null);
        setStatus(s);
        if (s.run_id) runIdRef.current = s.run_id;
        const cpu = toNum(s.cpu_percent);
        const ram = toNum(s.ram_percent);
        if (cpu !== null && ram !== null) {
          const point = { t: Date.now(), cpu, ram };
          setSeries((prev) => [...prev.slice(-(SERIES_CAP - 1)), point]);
        }
      } catch (err) {
        if (!alive) return;
        failsRef.current += 1;
        setError(err?.message || String(err));
        if (failsRef.current >= FAILS_BEFORE_OFFLINE) setConnected(false);
      }
    };
    tick();
    const id = setInterval(tick, STATUS_INTERVAL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // History poll — and an explicit refresh entry point so the app can pull a
  // fresh row into the table immediately after a trigger instead of waiting
  // for the slow cadence.
  const refreshHistory = useCallback(async () => {
    const h = await getHistory(runIdRef.current);
    setHistory(h?.migrations || []);
    return h;
  }, []);

  // Explicit status refresh — mirrors the tick so a trigger response can
  // update the risk gauge (and the chart buffer) instantly instead of waiting
  // out the 3s cadence.
  const refreshStatus = useCallback(async () => {
    const s = await getStatus();
    failsRef.current = 0;
    setConnected(true);
    setError(null);
    setStatus(s);
    if (s.run_id) runIdRef.current = s.run_id;
    const cpu = toNum(s.cpu_percent);
    const ram = toNum(s.ram_percent);
    if (cpu !== null && ram !== null) {
      const point = { t: Date.now(), cpu, ram };
      setSeries((prev) => [...prev.slice(-(SERIES_CAP - 1)), point]);
    }
    return s;
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const h = await getHistory(runIdRef.current);
        if (alive) setHistory(h?.migrations || []);
      } catch {
        // history is not connectivity — stay silent.
      }
    };
    tick();
    const id = setInterval(tick, HISTORY_INTERVAL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [refreshHistory]);

  return { status, history, connected, error, series, refreshHistory, refreshStatus };
}