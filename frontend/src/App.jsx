import { useCallback, useEffect, useState } from "react";
import {
  fetchDatabaseHealth,
  fetchServiceHealth,
  fetchSystemInfo,
  getApiBaseUrl,
} from "./api/client";
import DiagnosticsView from "./components/DiagnosticsView";
import Header from "./components/Header";
import LatencyChart from "./components/LatencyChart";
import Sidebar from "./components/Sidebar";
import StatusCards from "./components/StatusCards";

const MAX_HISTORY_POINTS = 20;

export default function App() {
  const [activeView, setActiveView] = useState("overview");
  const [serviceHealth, setServiceHealth] = useState(null);
  const [dbHealth, setDbHealth] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [autoPoll, setAutoPoll] = useState(true);
  const [history, setHistory] = useState([]);

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
      setHistory((prev) => [
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
    ? "healthy"
    : "unhealthy";

  const dbState = !dbHealth
    ? "checking"
    : dbHealth.ok && dbHealth.data?.database === "connected"
    ? "healthy"
    : "unhealthy";

  return (
    <div className="min-h-screen flex bg-[#050811] text-slate-100">
      <Sidebar
        activeView={activeView}
        onSelectView={setActiveView}
        team={systemInfo?.data?.team}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Header
          backendState={backendState}
          dbState={dbState}
          environment={systemInfo?.data?.environment}
          isPolling={isPolling}
          autoPoll={autoPoll}
          onToggleAutoPoll={() => setAutoPoll((prev) => !prev)}
          onManualRefresh={runHealthProbe}
        />

        <main className="flex-1 p-6 mission-grid overflow-y-auto">
          <div className="max-w-7xl mx-auto space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2">
              <div>
                <div className="text-[11px] font-mono uppercase tracking-widest text-cyan-400">
                  Phase 1 // Infrastructure & Telemetry Shell
                </div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-100 mt-1">
                  Satellite Telemetry Anomaly Triage Copilot
                </h1>
              </div>
              <div className="text-xs font-mono text-slate-400">
                Last Probe:{" "}
                <span className="text-slate-200">
                  {serviceHealth?.checkedAt
                    ? new Date(serviceHealth.checkedAt).toISOString().replace("T", " ").slice(0, 19) + "Z"
                    : "Pending"}
                </span>
              </div>
            </div>

            {activeView === "overview" ? (
              <>
                <StatusCards
                  serviceHealth={serviceHealth}
                  dbHealth={dbHealth}
                  systemInfo={systemInfo}
                  apiBaseUrl={getApiBaseUrl()}
                />
                <LatencyChart history={history} />
                <DiagnosticsView
                  serviceHealth={serviceHealth}
                  dbHealth={dbHealth}
                  systemInfo={systemInfo}
                />
              </>
            ) : (
              <DiagnosticsView
                serviceHealth={serviceHealth}
                dbHealth={dbHealth}
                systemInfo={systemInfo}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
