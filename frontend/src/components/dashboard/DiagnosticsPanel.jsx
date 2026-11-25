import { Database, Server } from "lucide-react";
import { Link } from "react-router-dom";
import StatusBadge from "../common/StatusBadge";

export default function DiagnosticsPanel({ health }) {
  const {
    serviceHealth,
    dbHealth,
    systemInfo,
    backendState,
    dbState,
    apiBaseUrl,
  } = health;

  return (
    <section className="rounded-lg border border-slate-800 bg-[#090f1e] p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            Ground-Station API & Database Diagnostics
          </h2>
          <p className="text-xs text-slate-400">
            Live connectivity verified via GET /health, GET /health/db, and GET /api/v1/info
          </p>
        </div>
        <Link
          to="/diagnostics"
          className="text-xs font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
        >
          Open Full Diagnostics →
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Application / System Info */}
        <div className="rounded border border-slate-800 bg-[#060b16] p-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-mono uppercase text-slate-400">
              Application Info
            </span>
            <StatusBadge
              variant={systemInfo?.ok ? "online" : systemInfo ? "offline" : "checking"}
              label={systemInfo?.ok ? "operational" : systemInfo ? "unreachable" : "probing"}
            />
          </div>
          <div className="mt-2.5 text-sm font-mono font-semibold text-slate-100">
            {systemInfo?.data?.application || "SAT-TRIAGE"}{" "}
            <span className="text-xs text-slate-400 font-normal">
              ({systemInfo?.data?.api_version || "—"} / v{systemInfo?.data?.version || "—"})
            </span>
          </div>
          <div className="mt-1 text-[11px] font-mono text-slate-500 truncate" title={apiBaseUrl}>
            {apiBaseUrl}
          </div>
        </div>

        {/* Backend Health */}
        <div className="rounded border border-slate-800 bg-[#060b16] p-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-cyan-400" />
              Backend (/health)
            </span>
            <StatusBadge
              variant={backendState}
              label={
                backendState === "online"
                  ? "Connected"
                  : backendState === "offline"
                  ? "Disconnected"
                  : "Probing"
              }
            />
          </div>
          <div className="mt-2.5 text-sm font-mono text-slate-200">
            {serviceHealth ? `${serviceHealth.latencyMs} ms` : "—"}
            <span className="text-xs text-slate-500 ml-2">
              HTTP {serviceHealth?.statusCode ?? "ERR"}
            </span>
          </div>
          <div className="mt-1 text-[11px] font-mono text-slate-500">
            {serviceHealth?.ok
              ? `Uptime: ${serviceHealth.data?.uptime_seconds ?? "—"}s`
              : serviceHealth?.error || "Probing endpoint..."}
          </div>
        </div>

        {/* Database Health */}
        <div className="rounded border border-slate-800 bg-[#060b16] p-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-emerald-400" />
              PostgreSQL (/health/db)
            </span>
            <StatusBadge
              variant={dbState}
              label={
                dbState === "online"
                  ? "Connected"
                  : dbState === "offline"
                  ? "Disconnected"
                  : "Probing"
              }
            />
          </div>
          <div className="mt-2.5 text-sm font-mono text-slate-200">
            {dbHealth?.data?.latency_ms !== undefined && dbHealth?.data?.latency_ms !== null
              ? `${dbHealth.data.latency_ms} ms`
              : "—"}
            <span className="text-xs text-slate-500 ml-2">
              HTTP {dbHealth?.statusCode ?? "ERR"}
            </span>
          </div>
          <div className="mt-1 text-[11px] font-mono text-slate-500 truncate">
            {dbHealth?.ok
              ? `Dialect: ${(dbHealth.data?.dialect || "postgresql").toUpperCase()}`
              : dbHealth?.data?.error || dbHealth?.error || "Probing database..."}
          </div>
        </div>
      </div>
    </section>
  );
}
