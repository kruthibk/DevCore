const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function requestEndpoint(path, options = {}) {
  const started = performance.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
    const latencyMs = Math.round((performance.now() - started) * 100) / 100;
    let payload = null;

    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    const errorMessage = response.ok
      ? null
      : payload?.error?.message || payload?.error || payload?.detail || `HTTP ${response.status}`;

    return {
      ok: response.ok,
      statusCode: response.status,
      latencyMs,
      data: payload,
      error: errorMessage,
      checkedAt: new Date().toISOString(),
    };
  } catch (err) {
    const latencyMs = Math.round((performance.now() - started) * 100) / 100;
    return {
      ok: false,
      statusCode: null,
      latencyMs,
      data: null,
      error:
        err?.name === "AbortError"
          ? "Request timed out after 8000ms"
          : err?.message || "Backend unreachable",
      checkedAt: new Date().toISOString(),
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export function fetchServiceHealth() {
  return requestEndpoint("/health");
}

export function fetchDatabaseHealth() {
  return requestEndpoint("/health/db");
}

export function fetchSystemInfo() {
  return requestEndpoint("/api/v1/info");
}

export function fetchSimulatorStatus() {
  return requestEndpoint("/api/v1/simulator/status");
}

export function startSimulator(intervalSeconds) {
  return requestEndpoint("/api/v1/simulator/start", {
    method: "POST",
    body: intervalSeconds ? { interval_seconds: intervalSeconds } : undefined,
  });
}

export function stopSimulator() {
  return requestEndpoint("/api/v1/simulator/stop", { method: "POST" });
}

export function injectSimulatorFault(faultType, targetSensor = null) {
  const body = targetSensor
    ? { fault_type: faultType, target_sensor: targetSensor }
    : { fault_type: faultType };
  return requestEndpoint("/api/v1/simulator/faults", {
    method: "POST",
    body,
  });
}

export function clearSimulatorFaults() {
  return requestEndpoint("/api/v1/simulator/faults/clear", { method: "POST" });
}

export function fetchLatestTelemetry(satelliteId = "SAT-01") {
  return requestEndpoint(`/api/v1/telemetry/latest?satellite_id=${encodeURIComponent(satelliteId)}`);
}

export function fetchTelemetryHistory({
  satelliteId = "SAT-01",
  sensorName = null,
  limit = 100,
  offset = 0,
} = {}) {
  const params = new URLSearchParams({
    satellite_id: satelliteId,
    limit: String(limit),
    offset: String(offset),
  });
  if (sensorName) {
    params.set("sensor_name", sensorName);
  }
  return requestEndpoint(`/api/v1/telemetry/history?${params.toString()}`);
}

export function fetchAlerts({
  satelliteId = null,
  sensorName = null,
  severity = null,
  alertType = null,
  status = null,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (satelliteId) params.set("satellite_id", satelliteId);
  if (sensorName) params.set("sensor_name", sensorName);
  if (severity) params.set("severity", severity);
  if (alertType) params.set("alert_type", alertType);
  if (status) params.set("status", status);
  return requestEndpoint(`/api/v1/alerts?${params.toString()}`);
}

export function fetchAlertDetail(alertId) {
  return requestEndpoint(`/api/v1/alerts/${encodeURIComponent(alertId)}`);
}

export function acknowledgeAlert(alertId) {
  return requestEndpoint(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    method: "POST",
  });
}

export function resolveAlert(alertId) {
  return requestEndpoint(`/api/v1/alerts/${encodeURIComponent(alertId)}/resolve`, {
    method: "POST",
  });
}

export function fetchDetectionStatus() {
  return requestEndpoint("/api/v1/detection/status");
}

export function fetchDetectionConfig() {
  return requestEndpoint("/api/v1/detection/config");
}

export function fetchFaultGraph({ satelliteId = "SAT-01", windowSeconds = 120 } = {}) {
  const params = new URLSearchParams({
    satellite_id: satelliteId,
    window_seconds: String(windowSeconds),
  });
  return requestEndpoint(`/api/v1/fault-graph?${params.toString()}`);
}

export function fetchCorrelations({
  satelliteId = null,
  status = null,
  suspectedSubsystem = null,
  windowSeconds = null,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (satelliteId) params.set("satellite_id", satelliteId);
  if (status) params.set("status", status);
  if (suspectedSubsystem) params.set("suspected_subsystem", suspectedSubsystem);
  if (windowSeconds) params.set("window_seconds", String(windowSeconds));
  return requestEndpoint(`/api/v1/fault-graph/correlations?${params.toString()}`);
}

export function fetchCorrelationDetail(correlationId) {
  return requestEndpoint(
    `/api/v1/fault-graph/correlations/${encodeURIComponent(correlationId)}`
  );
}

export function acknowledgeCorrelation(correlationId) {
  return requestEndpoint(
    `/api/v1/fault-graph/correlations/${encodeURIComponent(correlationId)}/acknowledge`,
    { method: "POST" }
  );
}

export function dismissCorrelation(correlationId) {
  return requestEndpoint(
    `/api/v1/fault-graph/correlations/${encodeURIComponent(correlationId)}/dismiss`,
    { method: "POST" }
  );
}
