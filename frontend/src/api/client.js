const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export const STORAGE_KEYS = {
  token: "sat_triage_token",
};

function getAuthHeaders() {
  try {
    const token = localStorage.getItem(STORAGE_KEYS.token);
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  } catch {
    // Ignore storage read errors
  }
  return {};
}

async function requestEndpoint(path, options = {}) {
  const started = performance.now();
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs || 8000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        ...getAuthHeaders(),
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

    if (response.status === 401 && !options.skipUnauthorizedEvent) {
      try {
        window.dispatchEvent(
          new CustomEvent("sat_triage:unauthorized", {
            detail: payload?.error?.message || payload?.detail || "Session expired or unauthorized",
          })
        );
      } catch {
        // Ignore event dispatch errors
      }
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
          ? `Request timed out after ${timeoutMs}ms`
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

export function fetchCopilotStatus() {
  return requestEndpoint("/api/v1/copilot/status");
}

export function reindexCopilot() {
  return requestEndpoint("/api/v1/copilot/reindex", {
    method: "POST",
    timeoutMs: 45000,
  });
}

export function askCopilot(payload) {
  return requestEndpoint("/api/v1/copilot/ask", {
    method: "POST",
    body: payload,
    timeoutMs: 35000,
  });
}

export function registerUser(username, email, password) {
  return requestEndpoint("/api/v1/auth/register", {
    method: "POST",
    body: { username, email, password },
    skipUnauthorizedEvent: true,
  });
}

export function loginUser(username, password) {
  return requestEndpoint("/api/v1/auth/login", {
    method: "POST",
    body: { username, password },
    skipUnauthorizedEvent: true,
  });
}

export function logoutUser() {
  return requestEndpoint("/api/v1/auth/logout", {
    method: "POST",
    skipUnauthorizedEvent: true,
  });
}

export function fetchAuthMe() {
  return requestEndpoint("/api/v1/auth/me");
}

export function evaluateVerification(payload) {
  return requestEndpoint("/api/v1/verification/evaluate", {
    method: "POST",
    body: payload,
  });
}

export function fetchRecommendations({ status = null, limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) params.set("status", status);
  return requestEndpoint(`/api/v1/verification/recommendations?${params.toString()}`);
}

export function fetchRecommendationDetail(recommendationId) {
  return requestEndpoint(
    `/api/v1/verification/recommendations/${encodeURIComponent(recommendationId)}`
  );
}

export function approveRecommendation(recommendationId, notes = null) {
  return requestEndpoint(
    `/api/v1/decisions/${encodeURIComponent(recommendationId)}/approve`,
    {
      method: "POST",
      body: { notes },
    }
  );
}

export function rejectRecommendation(recommendationId, reason, notes = null) {
  return requestEndpoint(
    `/api/v1/decisions/${encodeURIComponent(recommendationId)}/reject`,
    {
      method: "POST",
      body: { reason, notes },
    }
  );
}

export function requestInvestigation(recommendationId, reason, notes = null) {
  return requestEndpoint(
    `/api/v1/decisions/${encodeURIComponent(recommendationId)}/request-investigation`,
    {
      method: "POST",
      body: { reason, notes },
    }
  );
}

export function fetchDecisionHistory({ limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return requestEndpoint(`/api/v1/decisions/history?${params.toString()}`);
}

export function fetchAdminUsers() {
  return requestEndpoint("/api/v1/admin/users");
}

export function updateAdminUserRole(userId, role) {
  return requestEndpoint(`/api/v1/admin/users/${encodeURIComponent(userId)}/role`, {
    method: "PATCH",
    body: { role },
  });
}

export function updateAdminUserStatus(userId, isActive) {
  return requestEndpoint(`/api/v1/admin/users/${encodeURIComponent(userId)}/status`, {
    method: "PATCH",
    body: { is_active: isActive },
  });
}

export function fetchIncidents({
  status = null,
  severity = null,
  subsystem = null,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) params.set("status", status);
  if (severity) params.set("severity", severity);
  if (subsystem) params.set("subsystem", subsystem);
  return requestEndpoint(`/api/v1/incidents?${params.toString()}`);
}

export function createIncident(payload) {
  return requestEndpoint("/api/v1/incidents", {
    method: "POST",
    body: payload,
  });
}

export function fetchIncidentDetail(incidentId) {
  return requestEndpoint(`/api/v1/incidents/${encodeURIComponent(incidentId)}`);
}

export function updateIncident(incidentId, payload) {
  return requestEndpoint(`/api/v1/incidents/${encodeURIComponent(incidentId)}`, {
    method: "PATCH",
    body: payload,
  });
}

export function addIncidentLog(incidentId, note) {
  return requestEndpoint(`/api/v1/incidents/${encodeURIComponent(incidentId)}/logs`, {
    method: "POST",
    body: { note },
  });
}
