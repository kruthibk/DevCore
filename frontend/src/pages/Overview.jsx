import { BatteryCharging, Compass, ShieldCheck, Thermometer } from "lucide-react";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import AlertSummary from "../components/dashboard/AlertSummary";
import DiagnosticsPanel from "../components/dashboard/DiagnosticsPanel";
import IncidentSummary from "../components/dashboard/IncidentSummary";
import MetricCard from "../components/dashboard/MetricCard";
import SatelliteStatus from "../components/dashboard/SatelliteStatus";
import TelemetryChart from "../components/dashboard/TelemetryChart";

export default function Overview({ health }) {
  const {
    isInitialLoading,
    backendState,
    dbState,
    serviceHealth,
    dbHealth,
    refresh,
  } = health;

  return (
    <div className="space-y-6">
      {isInitialLoading && <LoadingState />}

      {!isInitialLoading && backendState === "offline" && (
        <ErrorState
          title="Backend API Unreachable"
          message={serviceHealth?.error || "Unable to contact FastAPI backend."}
          details="Verify Uvicorn is running on port 8000 and CORS_ORIGINS includes this frontend origin."
          onRetry={refresh}
        />
      )}

      {!isInitialLoading && backendState === "online" && dbState === "offline" && (
        <ErrorState
          severity="warning"
          title="PostgreSQL Database Disconnected"
          message={dbHealth?.data?.error || dbHealth?.error || "Database health probe returned 503."}
          details="API service remains online. Start the PostgreSQL container via Docker Compose to restore persistence."
          onRetry={refresh}
        />
      )}

      {/* A. Satellite Status Panel */}
      <SatelliteStatus lastProbeAt={serviceHealth?.checkedAt} />

      {/* B. Telemetry Metric Cards */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-mono uppercase tracking-widest text-slate-400">
            Spacecraft Telemetry Channels
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            Source: Phase 3 Simulator (Pending)
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard
            title="Battery Voltage"
            icon={BatteryCharging}
            value="—"
            unit="V"
            statusLabel="Waiting for telemetry"
            details="EPS bus voltage nominal range: 24.0V – 29.4V"
          />

          <MetricCard
            title="Temperature"
            icon={Thermometer}
            value="—"
            unit="°C"
            statusLabel="Waiting for telemetry"
            details="Thermal subsystem deck sensors on standby"
          />

          <MetricCard
            title="Satellite Attitude"
            icon={Compass}
            statusLabel="Waiting for telemetry"
            details="ADCS 3-axis orientation (degrees)"
          >
            <div className="grid grid-cols-3 gap-2 font-mono">
              <div className="rounded border border-slate-800 bg-[#060b16] p-2 text-center">
                <div className="text-[10px] text-slate-500 uppercase">Roll</div>
                <div className="text-base font-bold text-slate-200 mt-0.5">—°</div>
              </div>
              <div className="rounded border border-slate-800 bg-[#060b16] p-2 text-center">
                <div className="text-[10px] text-slate-500 uppercase">Pitch</div>
                <div className="text-base font-bold text-slate-200 mt-0.5">—°</div>
              </div>
              <div className="rounded border border-slate-800 bg-[#060b16] p-2 text-center">
                <div className="text-[10px] text-slate-500 uppercase">Yaw</div>
                <div className="text-base font-bold text-slate-200 mt-0.5">—°</div>
              </div>
            </div>
          </MetricCard>

          <MetricCard
            title="Sensor Integrity"
            icon={ShieldCheck}
            value="Standby"
            statusLabel="Waiting for telemetry"
            details="Sensor-quality issues: — (Pending Phase 3)"
          />
        </div>
      </section>

      {/* C. Telemetry Charts (Recharts with explicit empty states) */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-mono uppercase tracking-widest text-slate-400">
            Telemetry Time-Series Channels
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            No synthetic readings generated in Phase 2
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <TelemetryChart
            title="Battery Voltage"
            subtitle="EPS Bus Potential"
            unit="V"
            data={[]}
            series={[{ dataKey: "voltage", name: "Battery (V)", color: "#22d3ee" }]}
          />
          <TelemetryChart
            title="Thermal Profile"
            subtitle="Internal Payload Temperature"
            unit="°C"
            data={[]}
            series={[{ dataKey: "temperature", name: "Temp (°C)", color: "#10b981" }]}
          />
          <TelemetryChart
            title="Satellite Attitude"
            subtitle="Three-Axis Orientation (Roll / Pitch / Yaw)"
            unit="deg"
            data={[]}
            series={[
              { dataKey: "roll", name: "Roll", color: "#22d3ee" },
              { dataKey: "pitch", name: "Pitch", color: "#10b981" },
              { dataKey: "yaw", name: "Yaw", color: "#f59e0b" },
            ]}
          />
        </div>
      </section>

      {/* D. Alert Summary & E. Incident Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AlertSummary />
        <IncidentSummary />
      </div>

      {/* Phase 1 Diagnostics Integration */}
      <DiagnosticsPanel health={health} />
    </div>
  );
}
