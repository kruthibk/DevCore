import { useCallback, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import {
  acknowledgeAlert,
  acknowledgeCorrelation,
  clearSimulatorFaults,
  dismissCorrelation,
  fetchAlerts,
  fetchCorrelations,
  fetchDetectionConfig,
  fetchDetectionStatus,
  fetchFaultGraph,
  fetchLatestTelemetry,
  fetchSimulatorStatus,
  getApiBaseUrl,
  injectSimulatorFault,
  resolveAlert,
  startSimulator,
  stopSimulator,
} from "../api/client";

const MAX_CHART_POINTS = 60;
const MAX_INTEGRITY_EVENTS = 25;

function toChartPoint(timestampIso, readingsMap) {
  const timeLabel = timestampIso ? timestampIso.slice(11, 19) : new Date().toISOString().slice(11, 19);
  return {
    timestamp: timeLabel,
    isoTimestamp: timestampIso,
    battery_voltage: readingsMap.battery_voltage?.sensor_value ?? null,
    temperature: readingsMap.temperature?.sensor_value ?? null,
    roll: readingsMap.roll?.sensor_value ?? null,
    pitch: readingsMap.pitch?.sensor_value ?? null,
    yaw: readingsMap.yaw?.sensor_value ?? null,
  };
}

export function useTelemetryStream() {
  const [socketStatus, setSocketStatus] = useState("connecting");
  const [socketError, setSocketError] = useState(null);
  const [simulatorStatus, setSimulatorStatus] = useState(null);
  const [latestReadings, setLatestReadings] = useState({});
  const [chartHistory, setChartHistory] = useState([]);
  const [lastDataUpdate, setLastDataUpdate] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Phase 4: Alerts & Sensor Integrity state
  const [alerts, setAlerts] = useState([]);
  const [alertSummary, setAlertSummary] = useState(null);
  const [alertsTotal, setAlertsTotal] = useState(0);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState(null);
  const [alertFilters, setAlertFilters] = useState({
    severity: "",
    alertType: "",
    status: "",
  });
  const [pendingAlertAction, setPendingAlertAction] = useState(null);
  const [alertActionError, setAlertActionError] = useState(null);

  const [detectionStatus, setDetectionStatus] = useState(null);
  const [detectionConfig, setDetectionConfig] = useState(null);
  const [integrityIssues, setIntegrityIssues] = useState([]);

  // Phase 5: Fault Graph & Correlation state
  const [faultGraph, setFaultGraph] = useState(null);
  const [correlations, setCorrelations] = useState([]);
  const [correlationSummary, setCorrelationSummary] = useState(null);
  const [faultGraphLoading, setFaultGraphLoading] = useState(true);
  const [faultGraphError, setFaultGraphError] = useState(null);
  const [graphWindowSeconds, setGraphWindowSeconds] = useState(120);
  const [correlationStatusFilter, setCorrelationStatusFilter] = useState("");
  const [pendingCorrelationAction, setPendingCorrelationAction] = useState(null);
  const [correlationActionError, setCorrelationActionError] = useState(null);

  const socketRef = useRef(null);
  const filtersRef = useRef(alertFilters);
  filtersRef.current = alertFilters;
  const graphWindowRef = useRef(graphWindowSeconds);
  graphWindowRef.current = graphWindowSeconds;
  const corrStatusRef = useRef(correlationStatusFilter);
  corrStatusRef.current = correlationStatusFilter;

  const refreshAlerts = useCallback(async (overrideFilters = null) => {
    const activeFilters = overrideFilters || filtersRef.current;
    const res = await fetchAlerts({
      severity: activeFilters.severity || null,
      alertType: activeFilters.alertType || null,
      status: activeFilters.status || null,
      limit: 50,
      offset: 0,
    });
    if (res.ok && res.data) {
      setAlerts(res.data.items || []);
      setAlertsTotal(res.data.total ?? 0);
      setAlertSummary(res.data.summary || null);
      setAlertsError(null);
    } else {
      setAlertsError(res.error || "Unable to fetch alerts from backend.");
    }
    setAlertsLoading(false);
    return res;
  }, []);

  const refreshFaultGraph = useCallback(
    async (overrideWindow = null, overrideCorrStatus = null) => {
      const winSec = overrideWindow ?? graphWindowRef.current;
      const statusVal =
        overrideCorrStatus !== null ? overrideCorrStatus : corrStatusRef.current;

      const [graphRes, corrRes] = await Promise.all([
        fetchFaultGraph({ satelliteId: "SAT-01", windowSeconds: winSec }),
        fetchCorrelations({
          satelliteId: "SAT-01",
          status: statusVal || null,
          limit: 50,
          offset: 0,
        }),
      ]);

      if (graphRes.ok && graphRes.data) {
        setFaultGraph(graphRes.data);
        setFaultGraphError(null);
      } else {
        setFaultGraphError(graphRes.error || "Unable to fetch fault graph.");
      }

      if (corrRes.ok && corrRes.data) {
        setCorrelations(corrRes.data.items || []);
        setCorrelationSummary(corrRes.data.summary || null);
      }

      setFaultGraphLoading(false);
      return graphRes;
    },
    []
  );

  const syncInitialState = useCallback(async () => {
    const [statusRes, latestRes, detStatusRes, detConfigRes] = await Promise.all([
      fetchSimulatorStatus(),
      fetchLatestTelemetry("SAT-01"),
      fetchDetectionStatus(),
      fetchDetectionConfig(),
    ]);

    if (statusRes.ok && statusRes.data) {
      setSimulatorStatus(statusRes.data);
    }
    if (detStatusRes.ok && detStatusRes.data) {
      setDetectionStatus(detStatusRes.data);
    }
    if (detConfigRes.ok && detConfigRes.data) {
      setDetectionConfig(detConfigRes.data);
    }
    if (latestRes.ok && latestRes.data?.readings) {
      const readings = latestRes.data.readings;
      if (Object.keys(readings).length > 0) {
        setLatestReadings(readings);
        const firstSample = Object.values(readings)[0];
        if (firstSample?.timestamp) {
          setLastDataUpdate(firstSample.timestamp);
          setChartHistory((prev) =>
            prev.length === 0 ? [toChartPoint(firstSample.timestamp, readings)] : prev
          );
        }
      }
    }

    await Promise.all([refreshAlerts(), refreshFaultGraph()]);
  }, [refreshAlerts, refreshFaultGraph]);

  useEffect(() => {
    syncInitialState();

    const socket = io(getApiBaseUrl(), {
      path: "/socket.io",
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    });
    socketRef.current = socket;

    socket.on("connect", () => {
      setSocketStatus("connected");
      setSocketError(null);
      refreshAlerts();
      refreshFaultGraph();
    });

    socket.on("disconnect", (reason) => {
      setSocketStatus("disconnected");
      setSocketError(reason ? `Disconnected (${reason})` : "Disconnected");
    });

    socket.on("connect_error", (err) => {
      setSocketStatus("error");
      setSocketError(err?.message || "Socket.IO connection error");
    });

    socket.on("simulation:status", (payload) => {
      if (payload) {
        setSimulatorStatus(payload);
      }
    });

    socket.on("simulation:fault", (payload) => {
      if (payload?.active_faults) {
        setSimulatorStatus((prev) =>
          prev ? { ...prev, active_faults: payload.active_faults } : prev
        );
      }
    });

    socket.on("telemetry:update", (payload) => {
      if (!payload || !Array.isArray(payload.readings)) return;

      const readingsMap = {};
      for (const sample of payload.readings) {
        readingsMap[sample.sensor_name] = sample;
      }

      setLatestReadings(readingsMap);
      setLastDataUpdate(payload.timestamp);
      setSimulatorStatus((prev) =>
        prev
          ? {
              ...prev,
              running: payload.simulator_running ?? prev.running,
              active_faults: payload.active_faults ?? prev.active_faults,
              generated_count: payload.generated_count ?? prev.generated_count,
              streamed_count: payload.streamed_count ?? prev.streamed_count,
              persisted_count: payload.persisted_count ?? prev.persisted_count,
              last_persistence_error:
                payload.last_persistence_error !== undefined
                  ? payload.last_persistence_error
                  : prev.last_persistence_error,
              last_generated_at: payload.timestamp,
            }
          : prev
      );

      setChartHistory((prev) => [
        ...prev.slice(-(MAX_CHART_POINTS - 1)),
        toChartPoint(payload.timestamp, readingsMap),
      ]);
    });

    socket.on("detection:status", (payload) => {
      if (payload) {
        setDetectionStatus(payload);
      }
    });

    socket.on("integrity:issue", (finding) => {
      if (!finding) return;
      setIntegrityIssues((prev) => [finding, ...prev.slice(0, MAX_INTEGRITY_EVENTS - 1)]);
    });

    socket.on("alert:new", () => {
      refreshAlerts();
    });

    socket.on("alert:updated", () => {
      refreshAlerts();
    });

    socket.on("fault_graph:update", (payload) => {
      if (payload) {
        setFaultGraph(payload);
      }
    });

    socket.on("correlation:new", () => {
      refreshFaultGraph();
    });

    socket.on("correlation:updated", () => {
      refreshFaultGraph();
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [syncInitialState, refreshAlerts, refreshFaultGraph]);

  const updateAlertFilters = useCallback(
    (nextFilters) => {
      setAlertFilters(nextFilters);
      setAlertsLoading(true);
      refreshAlerts(nextFilters);
    },
    [refreshAlerts]
  );

  const runControlAction = useCallback(async (actionKey, fn) => {
    setPendingAction(actionKey);
    setActionError(null);
    try {
      const res = await fn();
      if (!res.ok) {
        setActionError(res.error || "Simulator control request failed.");
        return res;
      }
      if (actionKey === "start" || actionKey === "stop") {
        setSimulatorStatus(res.data);
      } else {
        const statusRes = await fetchSimulatorStatus();
        if (statusRes.ok && statusRes.data) {
          setSimulatorStatus(statusRes.data);
        }
      }
      return res;
    } finally {
      setPendingAction(null);
    }
  }, []);

  const handleAcknowledgeAlert = useCallback(
    async (alertId) => {
      setPendingAlertAction(`ack:${alertId}`);
      setAlertActionError(null);
      try {
        const res = await acknowledgeAlert(alertId);
        if (!res.ok) {
          setAlertActionError(res.error || "Failed to acknowledge alert.");
          return res;
        }
        await refreshAlerts();
        return res;
      } finally {
        setPendingAlertAction(null);
      }
    },
    [refreshAlerts]
  );

  const handleResolveAlert = useCallback(
    async (alertId) => {
      setPendingAlertAction(`resolve:${alertId}`);
      setAlertActionError(null);
      try {
        const res = await resolveAlert(alertId);
        if (!res.ok) {
          setAlertActionError(res.error || "Failed to resolve alert.");
          return res;
        }
        await refreshAlerts();
        return res;
      } finally {
        setPendingAlertAction(null);
      }
    },
    [refreshAlerts]
  );

  const handleAcknowledgeCorrelation = useCallback(
    async (correlationId) => {
      setPendingCorrelationAction(`ack:${correlationId}`);
      setCorrelationActionError(null);
      try {
        const res = await acknowledgeCorrelation(correlationId);
        if (!res.ok) {
          setCorrelationActionError(res.error || "Failed to acknowledge correlation.");
          return res;
        }
        await refreshFaultGraph();
        return res;
      } finally {
        setPendingCorrelationAction(null);
      }
    },
    [refreshFaultGraph]
  );

  const handleDismissCorrelation = useCallback(
    async (correlationId) => {
      setPendingCorrelationAction(`dismiss:${correlationId}`);
      setCorrelationActionError(null);
      try {
        const res = await dismissCorrelation(correlationId);
        if (!res.ok) {
          setCorrelationActionError(res.error || "Failed to dismiss correlation.");
          return res;
        }
        await refreshFaultGraph();
        return res;
      } finally {
        setPendingCorrelationAction(null);
      }
    },
    [refreshFaultGraph]
  );

  const updateGraphWindow = useCallback(
    (winSec) => {
      setGraphWindowSeconds(winSec);
      setFaultGraphLoading(true);
      refreshFaultGraph(winSec, null);
    },
    [refreshFaultGraph]
  );

  const updateCorrelationStatusFilter = useCallback(
    (statusVal) => {
      setCorrelationStatusFilter(statusVal);
      setFaultGraphLoading(true);
      refreshFaultGraph(null, statusVal);
    },
    [refreshFaultGraph]
  );

  return {
    socketStatus,
    socketError,
    simulatorStatus,
    latestReadings,
    chartHistory,
    lastDataUpdate,
    pendingAction,
    actionError,
    clearActionError: () => setActionError(null),
    start: (intervalSeconds) =>
      runControlAction("start", () => startSimulator(intervalSeconds)),
    stop: () => runControlAction("stop", () => stopSimulator()),
    injectFault: (faultType, targetSensor = null) =>
      runControlAction(`fault:${faultType}`, () =>
        injectSimulatorFault(faultType, targetSensor)
      ),
    clearFaults: () =>
      runControlAction("clear_faults", () => clearSimulatorFaults()),
    refreshStatus: syncInitialState,
    // Phase 4 exports
    alerts,
    alertSummary,
    alertsTotal,
    alertsLoading,
    alertsError,
    alertFilters,
    updateAlertFilters,
    refreshAlerts,
    pendingAlertAction,
    alertActionError,
    clearAlertActionError: () => setAlertActionError(null),
    acknowledgeAlert: handleAcknowledgeAlert,
    resolveAlert: handleResolveAlert,
    detectionStatus,
    detectionConfig,
    integrityIssues,
    // Phase 5 exports
    faultGraph,
    correlations,
    correlationSummary,
    faultGraphLoading,
    faultGraphError,
    graphWindowSeconds,
    updateGraphWindow,
    correlationStatusFilter,
    updateCorrelationStatusFilter,
    refreshFaultGraph,
    pendingCorrelationAction,
    correlationActionError,
    clearCorrelationActionError: () => setCorrelationActionError(null),
    acknowledgeCorrelation: handleAcknowledgeCorrelation,
    dismissCorrelation: handleDismissCorrelation,
  };
}
