const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function requestEndpoint(path) {
  const started = performance.now();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    const latencyMs = Math.round((performance.now() - started) * 100) / 100;
    let payload = null;

    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    return {
      ok: response.ok,
      statusCode: response.status,
      latencyMs,
      data: payload,
      error: response.ok
        ? null
        : payload?.error || payload?.detail || `HTTP ${response.status}`,
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
