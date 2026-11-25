import { useCallback, useEffect, useState } from "react";
import {
  fetchDatabaseHealth,
  fetchServiceHealth,
  fetchSystemInfo,
  getApiBaseUrl,
} from "../api/client";

const MAX_HISTORY_POINTS = 20;

export function useSystemHealth() {
  const [serviceHealth, setServiceHealth] = useState(null);
  const [dbHealth, setDbHealth] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isPolling, setIsPolling] = useState(false);
  const [autoPoll, setAutoPoll] = useState(true);
  const [probeHistory, setProbeHistory] = useState([]);

  const runHealthProbe = useCallback(async () => {
    setIsPolling(true);
    try {
      const [serviceRes, dbRes, infoRes] = await Promise.all([
        fetchServiceHealth(),
        fetchDatabaseHealth(),
        fetchSystemInfo(),
      ]);

      setServiceHealth(serviceRes);
      setDbHealth(dbRes);
      setSystemInfo(infoRes);

      const timeLabel = new Date().toISOString().slice(11, 19);
      setProbeHistory((prev) => [
        ...prev.slice(-(MAX_HISTORY_POINTS - 1)),
        {
          time: timeLabel,
          apiLatencyMs: serviceRes.ok ? serviceRes.latencyMs : null,
          dbLatencyMs:
            dbRes.ok && typeof dbRes.data?.latency_ms === "number"
              ? dbRes.data.latency_ms
              : null,
        },
      ]);
    } finally {
      setIsPolling(false);
      setIsInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    runHealthProbe();
  }, [runHealthProbe]);

  useEffect(() => {
    if (!autoPoll) return undefined;
    const interval = setInterval(runHealthProbe, 10000);
    return () => clearInterval(interval);
  }, [autoPoll, runHealthProbe]);

  const backendState = !serviceHealth
    ? "checking"
    : serviceHealth.ok && serviceHealth.data?.status === "healthy"
    ? "online"
    : "offline";

  const dbState = !dbHealth
    ? "checking"
    : dbHealth.ok && dbHealth.data?.database === "connected"
    ? "online"
    : "offline";

  const systemState =
    backendState === "checking" || dbState === "checking"
      ? "checking"
      : backendState === "online" && dbState === "online"
      ? "online"
      : backendState === "online"
      ? "degraded"
      : "offline";

  return {
    apiBaseUrl: getApiBaseUrl(),
    serviceHealth,
    dbHealth,
    systemInfo,
    backendState,
    dbState,
    systemState,
    isInitialLoading,
    isPolling,
    autoPoll,
    probeHistory,
    toggleAutoPoll: () => setAutoPoll((prev) => !prev),
    refresh: runHealthProbe,
  };
}
