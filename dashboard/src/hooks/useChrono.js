import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { fetchHistory, fetchStatus, resolveApiBase, triggerInterruption } from "../api/client.js";
import { demoHistory, demoResult, demoSeries, demoStatus } from "../lib/demo.js";

const ChronoContext = createContext(null);

const MAX_FAILURES = 2;
const HISTORY_MS = 10_000;
const SERIES_CAP = 600; // ~50 min at the default 5s poll

const readLs = (key) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};
const writeLs = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    // storage unavailable — settings stay in memory
  }
};

export function ChronoProvider({ children }) {
  const [apiBase, setApiBase] = useState(() => readLs("chrono.apiBase") || resolveApiBase());
  const [pollMs, setPollMs] = useState(() => Number(readLs("chrono.pollMs")) || 5000);
  const [demo, setDemoRaw] = useState(() => readLs("chrono.demo") === "1");

  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [series, setSeries] = useState([]);
  const [connected, setConnected] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [triggerState, setTriggerState] = useState("idle"); // idle | running | error
  const [triggerError, setTriggerError] = useState("");

  const failsRef = useRef(0);
  const runIdRef = useRef(null);
  const demoCounterRef = useRef(0);

  const reflectStatus = useCallback((s) => {
    setStatus(s);
    runIdRef.current = s?.run_id || runIdRef.current;
  }, []);

  const setDemo = useCallback((value) => {
    setDemoRaw(value);
    writeLs("chrono.demo", value ? "1" : "0");
  }, []);

  const persistBase = useCallback((value) => {
    const next = value.trim().replace(/\/+$/, "") || resolveApiBase();
    setApiBase(next);
    writeLs("chrono.apiBase", next);
  }, []);

  const persistPoll = useCallback((value) => {
    setPollMs(value);
    writeLs("chrono.pollMs", String(value));
  }, []);

  // ── demo mode: drive every surface from synthetic-but-shape-exact data ────
  useEffect(() => {
    if (!demo) return undefined;
    demoCounterRef.current = 0;
    setSeries(demoSeries());
    const tick = setInterval(() => {
      demoCounterRef.current += 1;
      const i = demoCounterRef.current;
      const drift = (i * 7) % 13;
      setStatus({
        ...demoStatus(),
        cpu_percent: 41 + drift,
        ram_percent: 38 + (i % 5),
        risk_percent: 22 + ((i * 3) % 7),
      });
      setSeries((prev) => {
        const next = [...prev, { t: Date.now(), cpu: 41 + drift, ram: 38 + (i % 5), risk: 22 + ((i * 3) % 7) }];
        return next.length > SERIES_CAP ? next.slice(next.length - SERIES_CAP) : next;
      });
      setHistory((prev) => (prev.length ? prev : demoHistory().migrations));
      setConnected(true);
    }, pollMs);
    return () => clearInterval(tick);
  }, [demo, pollMs]);

  // ── live mode: poll /status and /history on two independent timers ──────
  useEffect(() => {
    if (demo) return undefined;

    let cancelled = false;

    const loadStatus = async () => {
      try {
        const s = await fetchStatus(apiBase);
        if (cancelled) return;
        failsRef.current = 0;
        setConnected(true);
        reflectStatus(s);
        setSeries((prev) => {
          const next = [...prev, { t: Date.now(), cpu: s.cpu_percent, ram: s.ram_percent, risk: s.risk_percent }];
          return next.length > SERIES_CAP ? next.slice(next.length - SERIES_CAP) : next;
        });
      } catch {
        if (cancelled) return;
        failsRef.current += 1;
        if (failsRef.current >= MAX_FAILURES) setConnected(false);
      }
    };

    const loadHistory = async () => {
      const runId = runIdRef.current || "run-local-dev";
      try {
        const body = await fetchHistory(runId, apiBase);
        if (!cancelled) setHistory(body?.migrations || []);
      } catch {
        // history lagging behind status is fine; status owns connectivity
      }
    };

    loadStatus();
    loadHistory();
    const statusTimer = setInterval(loadStatus, pollMs);
    const historyTimer = setInterval(loadHistory, HISTORY_MS);
    return () => {
      cancelled = true;
      clearInterval(statusTimer);
      clearInterval(historyTimer);
    };
  }, [demo, apiBase, pollMs, reflectStatus]);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchStatus(apiBase);
      failsRef.current = 0;
      setConnected(true);
      reflectStatus(s);
    } catch {
      failsRef.current += 1;
      if (failsRef.current >= MAX_FAILURES) setConnected(false);
    }
    try {
      const body = await fetchHistory(runIdRef.current || "run-local-dev", apiBase);
      setHistory(body?.migrations || []);
    } catch {
      // keep whatever we have
    }
  }, [apiBase, reflectStatus]);

  const trigger = useCallback(
    async (payload, triggeredBy) => {
      setTriggerState("running");
      setTriggerError("");
      try {
        let result;
        if (demo) {
          await new Promise((resolve) => setTimeout(resolve, 900));
          result = demoResult();
        } else {
          result = await triggerInterruption(payload, triggeredBy, apiBase);
        }
        setLastResult(result);
        if (result?.status === "completed") {
          const row = {
            timestamp: new Date().toISOString(),
            from_vm_id: result.from_vm_id,
            to_vm_id: result.to_vm_id,
            triggered_by: triggeredBy,
            risk_percent: payload.risk_percent,
            downtime_seconds: result.downtime_seconds,
            status: result.status,
            checkpoint_key: result.checkpoint_key,
            resumed_index: result.timeline ? null : null,
            timeline: result.timeline ? JSON.stringify(result.timeline) : null,
            completed_at: new Date().toISOString(),
          };
          setHistory((prev) => {
            const next = [row, ...prev];
            return next.slice(0, 40);
          });
          setStatus((prev) =>
            prev
              ? {
                  ...prev,
                  vm_id: result.to_vm_id,
                  migration_count: (prev.migration_count || 0) + 1,
                  last_downtime_seconds: result.downtime_seconds,
                }
              : prev,
          );
        }
        setTriggerState("idle");
        return result;
      } catch (err) {
        setTriggerError(err?.message || "Trigger failed");
        setTriggerState("error");
        return null;
      }
    },
    [apiBase, demo],
  );

  const value = useMemo(
    () => ({
      status,
      history,
      series,
      connected,
      demo,
      setDemo,
      apiBase,
      setApiBase: persistBase,
      pollMs,
      setPollMs: persistPoll,
      lastResult,
      trigger,
      triggerState,
      triggerError,
      refresh,
    }),
    [status, history, series, connected, demo, setDemo, apiBase, persistBase, pollMs, persistPoll, lastResult, trigger, triggerState, triggerError, refresh],
  );

  return createElement(ChronoContext.Provider, { value }, children);
}

export function useChrono() {
  return useContext(ChronoContext);
}