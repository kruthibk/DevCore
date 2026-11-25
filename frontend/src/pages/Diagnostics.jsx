import DiagnosticsView from "../components/DiagnosticsView";
import LatencyChart from "../components/LatencyChart";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import DiagnosticsPanel from "../components/dashboard/DiagnosticsPanel";

export default function Diagnostics({ health }) {
  const {
    isInitialLoading,
    backendState,
    dbState,
    serviceHealth,
    dbHealth,
    systemInfo,
    probeHistory,
    autoPoll,
    toggleAutoPoll,
    refresh,
  } = health;

  return (
    <div className="space-y-6">
      {isInitialLoading && <LoadingState />}

      {!isInitialLoading && backendState === "offline" && (
        <ErrorState
          title="Backend Service Unreachable"
          message={serviceHealth?.error || "Unable to connect to FastAPI."}
          onRetry={refresh}
        />
      )}

      {!isInitialLoading && backendState === "online" && dbState === "offline" && (
        <ErrorState
          severity="warning"
          title="PostgreSQL Health Check Failed (HTTP 503)"
          message={dbHealth?.data?.error || dbHealth?.error || "Database disconnected."}
          onRetry={refresh}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-[#090f1e] px-4 py-3">
        <div className="text-xs font-mono text-slate-400">
          Last Probe:{" "}
          <span className="text-slate-200">
            {serviceHealth?.checkedAt
              ? new Date(serviceHealth.checkedAt).toISOString().replace("T", " ").slice(0, 19) + " UTC"
              : "Pending"}
          </span>
        </div>
        <button
          type="button"
          onClick={toggleAutoPoll}
          className={`px-3 py-1 rounded border text-xs font-mono transition-colors ${
            autoPoll
              ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300"
              : "border-slate-700 bg-slate-800/70 text-slate-400"
          }`}
        >
          AUTO-POLL: {autoPoll ? "ON (10s)" : "PAUSED"}
        </button>
      </div>

      <DiagnosticsPanel health={health} />
      <LatencyChart history={probeHistory} />
      <DiagnosticsView
        serviceHealth={serviceHealth}
        dbHealth={dbHealth}
        systemInfo={systemInfo}
      />
    </div>
  );
}
