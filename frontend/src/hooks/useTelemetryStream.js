import { useCallback, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import {
  clearSimulatorFaults,
  fetchLatestTelemetry,
  fetchSimulatorStatus,
  getApiBaseUrl,
  injectSimulatorFault,
  startSimulator,
  stopSimulator,
} from "../api/client";

const MAX_CHART_POINTS = 60;

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
  const socketRef = useRef(null);

  const syncInitialState = useCallback(async () => {
    const [statusRes, latestRes] = await Promise.all([
      fetchSimulatorStatus(),
      fetchLatestTelemetry("SAT-01"),
    ]);

    if (statusRes.ok && statusRes.data) {
      setSimulatorStatus(statusRes.data);
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
  }, []);

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

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [syncInitialState]);

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
  };
}
