import { CheckCircle2, Database, Server, ShieldAlert, XCircle } from "lucide-react";

function badgeClass(state) {
  if (state === "healthy") {
    return "bg-emerald-500/10 text-emerald-300 border-emerald-500/30";
  }
  if (state === "unhealthy") {
    return "bg-rose-500/10 text-rose-300 border-rose-500/30";
  }
  return "bg-amber-500/10 text-amber-300 border-amber-500/30";
}

export default function StatusCards({ serviceHealth, dbHealth, systemInfo, apiBaseUrl }) {
  const backendState = serviceHealth
    ? serviceHealth.ok && serviceHealth.data?.status === "healthy"
      ? "healthy"
      : "unhealthy"
    : "checking";

  const dbState = dbHealth
    ? dbHealth.ok && dbHealth.data?.database === "connected"
      ? "healthy"
      : "unhealthy"
    : "checking";

  const appState = systemInfo
    ? systemInfo.ok
      ? "healthy"
      : "unhealthy"
    : "checking";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Application Status */}
      <div className="rounded-xl border border-slate-800 bg-[#0b1222]/90 p-5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
              Application Status
            </span>
            <span
              className={`px-2 py-0.5 rounded-full border text-[11px] font-mono uppercase ${badgeClass(
                appState
              )}`}
            >
              {systemInfo?.ok
                ? systemInfo.data?.status || "operational"
                : systemInfo
                ? "unreachable"
                : "checking"}
            </span>
          </div>
          <div className="mt-3 text-xl font-semibold text-slate-100">
            {systemInfo?.data?.application || "SAT-TRIAGE"}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            {systemInfo?.data?.team?.problem_statement ||
              "11 — Satellite Telemetry Anomaly Triage Copilot"}
          </div>
        </div>

        <div className="mt-5 pt-3 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-xs font-mono">
          <div>
            <div className="text-slate-500">API Version</div>
            <div className="text-slate-200 mt-0.5">
              {systemInfo?.data?.api_version || "—"} (v{systemInfo?.data?.version || "—"})
            </div>
          </div>
          <div>
            <div className="text-slate-500">Endpoint Base</div>
            <div className="text-cyan-300 mt-0.5 truncate" title={apiBaseUrl}>
              {apiBaseUrl}
            </div>
          </div>
        </div>
      </div>

      {/* Backend Connectivity */}
      <div className="rounded-xl border border-slate-800 bg-[#0b1222]/90 p-5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Server className="w-3.5 h-3.5 text-cyan-400" />
              Backend Connectivity
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-mono uppercase ${badgeClass(
                backendState
              )}`}
            >
              {backendState === "healthy" ? (
                <CheckCircle2 className="w-3 h-3" />
              ) : backendState === "unhealthy" ? (
                <XCircle className="w-3 h-3" />
              ) : null}
              {backendState === "healthy"
                ? "Connected"
                : backendState === "unhealthy"
                ? "Disconnected"
                : "Probing"}
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-slate-100">
              {serviceHealth ? `${serviceHealth.latencyMs} ms` : "—"}
            </span>
            <span className="text-xs font-mono text-slate-500">HTTP round-trip</span>
          </div>

          {serviceHealth && !serviceHealth.ok && (
            <div className="mt-2 p-2 rounded bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300 flex items-start gap-2">
              <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>{serviceHealth.error}</span>
            </div>
          )}
        </div>

        <div className="mt-5 pt-3 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-xs font-mono">
          <div>
            <div className="text-slate-500">Service Uptime</div>
            <div className="text-slate-200 mt-0.5">
              {serviceHealth?.data?.uptime_seconds !== undefined
                ? `${serviceHealth.data.uptime_seconds}s`
                : "—"}
            </div>
          </div>
          <div>
            <div className="text-slate-500">HTTP Status</div>
            <div className="text-slate-200 mt-0.5">
              {serviceHealth?.statusCode ?? "No response"}
            </div>
          </div>
        </div>
      </div>

      {/* Database Connectivity */}
      <div className="rounded-xl border border-slate-800 bg-[#0b1222]/90 p-5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-cyan-400" />
              Database Connectivity
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-mono uppercase ${badgeClass(
                dbState
              )}`}
            >
              {dbState === "healthy" ? (
                <CheckCircle2 className="w-3 h-3" />
              ) : dbState === "unhealthy" ? (
                <XCircle className="w-3 h-3" />
              ) : null}
              {dbState === "healthy"
                ? "Connected"
                : dbState === "unhealthy"
                ? "Disconnected"
                : "Probing"}
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-slate-100">
              {dbHealth?.data?.latency_ms !== null &&
              dbHealth?.data?.latency_ms !== undefined
                ? `${dbHealth.data.latency_ms} ms`
                : "—"}
            </span>
            <span className="text-xs font-mono text-slate-500">SQL SELECT 1 probe</span>
          </div>

          {dbHealth && !dbHealth.ok && (
            <div className="mt-2 p-2 rounded bg-rose-500/10 border border-rose-500/20 text-xs font-mono text-rose-300 flex items-start gap-2">
              <ShieldAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>{dbHealth.data?.error || dbHealth.error}</span>
            </div>
          )}
        </div>

        <div className="mt-5 pt-3 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-xs font-mono">
          <div>
            <div className="text-slate-500">Dialect</div>
            <div className="text-slate-200 mt-0.5 uppercase">
              {dbHealth?.data?.dialect || "—"}
            </div>
          </div>
          <div>
            <div className="text-slate-500">HTTP Status</div>
            <div className="text-slate-200 mt-0.5">
              {dbHealth?.statusCode ?? "No response"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
