import { BatteryCharging, Compass, ShieldCheck, Thermometer } from "lucide-react";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import AlertSummary from "../components/dashboard/AlertSummary";
import DiagnosticsPanel from "../components/dashboard/DiagnosticsPanel";
import IncidentSummary from "../components/dashboard/IncidentSummary";
import MetricCard from "../components/dashboard/MetricCard";
import SatelliteStatus from "../components/dashboard/SatelliteStatus";
import SimulatorControls from "../components/dashboard/SimulatorControls";
import TelemetryChart from "../components/dashboard/TelemetryChart";

function qualityVariant(qualityStatus) {
  if (!qualityStatus) return "muted";
  if (qualityStatus === "NOMINAL") return "nominal";
  if (qualityStatus === "MISSING") return "critical";
  return "warning";
}

function formatMetric(sample) {
  if (!sample) return "—";
  if (sample.sensor_value === null || sample.sensor_value === undefined) return "MISSING";
  return String(sample.sensor_value);
}

export default function Overview({ health, stream }) {
  const {
    isInitialLoading,
    backendState,
    dbState,
    serviceHealth,
    dbHealth,
    refresh,
  } = health;

  const {
    latestReadings,
    chartHistory,
    lastDataUpdate,
    simulatorStatus,
    socketStatus,
    alerts,
    alertSummary,
    alertsError,
  } = stream;

  const battery = latestReadings.battery_voltage;
  const temp = latestReadings.temperature;
  const roll = latestReadings.roll;
  const pitch = latestReadings.pitch;
  const yaw = latestReadings.yaw;

  const samplesList = [battery, temp, roll, pitch, yaw].filter(Boolean);
  const issueSamples = samplesList.filter((s) => s.quality_status !== "NOMINAL");
  const integrityStatus =
    samplesList.length === 0
      ? "Waiting for telemetry"
      : issueSamples.length === 0
      ? "All Nominal"
      : `${issueSamples.length} Altered`;
  const integrityVariant =
    samplesList.length === 0
      ? "muted"
      : issueSamples.length === 0
      ? "nominal"
      : "warning";

  const attitudeVariant =
    !roll && !pitch && !yaw
      ? "muted"
      : [roll, pitch, yaw].some((s) => s?.quality_status === "MISSING")
      ? "critical"
      : [roll, pitch, yaw].some((s) => s && s.quality_status !== "NOMINAL")
      ? "warning"
      : "nominal";

  const attitudeLabel =
    !roll && !pitch && !yaw
      ? "Waiting for telemetry"
      : [roll, pitch, yaw].find((s) => s && s.quality_status !== "NOMINAL")?.quality_status ||
        "NOMINAL";

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
      <SatelliteStatus
        lastProbeAt={serviceHealth?.checkedAt}
        lastDataUpdate={lastDataUpdate}
        simulatorRunning={Boolean(simulatorStatus?.running)}
        socketStatus={socketStatus}
      />

      {/* Synthetic Simulator Controls */}
      <SimulatorControls stream={stream} />

      {/* B. Telemetry Metric Cards */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-mono uppercase tracking-widest text-slate-400">
            Spacecraft Telemetry Channels
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            Source: SYNTHETIC SIMULATION DATA
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard
            title="Battery Voltage"
            icon={BatteryCharging}
            value={formatMetric(battery)}
            unit={battery ? "V" : "V"}
            statusLabel={battery?.quality_status || "Waiting for telemetry"}
            statusVariant={qualityVariant(battery?.quality_status)}
            details="EPS bus voltage nominal range: 24.0V – 29.4V"
          />

          <MetricCard
            title="Temperature"
            icon={Thermometer}
            value={formatMetric(temp)}
            unit="°C"
            statusLabel={temp?.quality_status || "Waiting for telemetry"}
            statusVariant={qualityVariant(temp?.quality_status)}
            details="Thermal subsystem deck sensors"
          />

          <MetricCard
            title="Satellite Attitude"
            icon={Compass}
            statusLabel={attitudeLabel}
            statusVariant={attitudeVariant}
            details="ADCS 3-axis orientation (degrees)"
          >
            <div className="grid grid-cols-3 gap-2 font-mono">
              <div className="rounded border border-slate-800 bg-[#060b16] p-2 text-center">
                <div className="text-[10px] text-slate-500 uppercase">Roll</div>
                <div className="text-sm font-bold text-slate-200 mt-0.5">
                  {roll?.sensor_value !== undefined && roll?.sensor_value !== null
                    ? `${roll.sensor_value}°`
                    : roll?.quality_status === "MISSING"
                    ? "N/A"
                    : "—°"}
                </div>
              </div>
              <div className="rounded border border-slate-800 bg-[#060b16] p-2 text-center">
                <div className="text-[10px] text-slate-500 uppercase">Pitch</div>
                <div className="text-sm font-bold text-slate-200 mt-0.5">
                  {pitch?.sensor_value !== undefined && pitch?.sensor_value !== null
                    ? `${pitch.sensor_value}°`
                    : pitch?.quality_status === "MISSING"
                    ? "N/A"
                    : "—°"}
                </div>
              </div>
              <div className="rounded border border-slate-800 bg-[#060b16] p-2 text-center">
                <div className="text-[10px] text-slate-500 uppercase">Yaw</div>
                <div className="text-sm font-bold text-slate-200 mt-0.5">
                  {yaw?.sensor_value !== undefined && yaw?.sensor_value !== null
                    ? `${yaw.sensor_value}°`
                    : yaw?.quality_status === "MISSING"
                    ? "N/A"
                    : "—°"}
                </div>
              </div>
            </div>
          </MetricCard>

          <MetricCard
            title="Sensor Integrity"
            icon={ShieldCheck}
            value={
              samplesList.length === 0
                ? "Standby"
                : `${samplesList.length - issueSamples.length}/${samplesList.length} OK`
            }
            statusLabel={integrityStatus}
            statusVariant={integrityVariant}
            details={
              samplesList.length === 0
                ? "Sensor-quality issues: — (Start simulator)"
                : `Sensor quality altered: ${issueSamples.length} channel(s)`
            }
          />
        </div>
      </section>

      {/* C. Telemetry Charts (Recharts live Socket.IO bounded history) */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-mono uppercase tracking-widest text-slate-400">
            Telemetry Time-Series Channels (Last 60 Frames)
          </h2>
          <span className="text-[11px] font-mono text-slate-500">
            Buffered samples: {chartHistory.length} / 60
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <TelemetryChart
            title="Battery Voltage"
            subtitle="EPS Bus Potential"
            unit="V"
            data={chartHistory}
            series={[{ dataKey: "battery_voltage", name: "Battery (V)", color: "#22d3ee" }]}
          />
          <TelemetryChart
            title="Thermal Profile"
            subtitle="Internal Payload Temperature"
            unit="°C"
            data={chartHistory}
            series={[{ dataKey: "temperature", name: "Temp (°C)", color: "#10b981" }]}
          />
          <TelemetryChart
            title="Satellite Attitude"
            subtitle="Three-Axis Orientation (Roll / Pitch / Yaw)"
            unit="deg"
            data={chartHistory}
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
        <AlertSummary summary={alertSummary} alerts={alerts} error={alertsError} />
        <IncidentSummary />
      </div>

      {/* Phase 1 Diagnostics Integration */}
      <DiagnosticsPanel health={health} />
    </div>
  );
}
