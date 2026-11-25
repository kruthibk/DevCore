import { BatteryCharging, Clock, Compass, Radio, Thermometer } from "lucide-react";
import StatusBadge from "../components/common/StatusBadge";
import MetricCard from "../components/dashboard/MetricCard";
import SimulatorControls from "../components/dashboard/SimulatorControls";
import TelemetryChart from "../components/dashboard/TelemetryChart";

function qualityVariant(qualityStatus) {
  if (!qualityStatus) return "muted";
  if (qualityStatus === "NOMINAL") return "nominal";
  if (qualityStatus === "MISSING") return "critical";
  return "warning";
}

function formatVal(sample) {
  if (!sample) return "—";
  if (sample.sensor_value === null || sample.sensor_value === undefined) return "MISSING";
  return String(sample.sensor_value);
}

export default function Telemetry({ health, stream }) {
  const { latestReadings, chartHistory, lastDataUpdate, simulatorStatus, socketStatus } = stream;
  const isRunning = Boolean(simulatorStatus?.running);

  const battery = latestReadings.battery_voltage;
  const temp = latestReadings.temperature;
  const roll = latestReadings.roll;
  const pitch = latestReadings.pitch;
  const yaw = latestReadings.yaw;

  return (
    <div className="space-y-6">
      {/* Connection & Synthetic Data Banner */}
      <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <Radio className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-cyan-200">
              {isRunning
                ? "Streaming SYNTHETIC SIMULATION DATA from Python NumPy Backend"
                : "Synthetic Telemetry Simulator Ready (Standby)"}
            </div>
            <p className="text-xs text-cyan-200/75 mt-0.5">
              All readings originate from the FastAPI simulator and stream over Socket.IO. No telemetry is generated in the browser.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge
            variant={health.backendState}
            label={`API: ${health.backendState.toUpperCase()}`}
          />
          <StatusBadge
            variant={health.dbState}
            label={`DB: ${health.dbState.toUpperCase()}`}
          />
          <StatusBadge
            variant={socketStatus === "connected" ? "online" : "offline"}
            label={`SIO: ${socketStatus.toUpperCase()}`}
          />
        </div>
      </div>

      {/* Simulator Control Panel */}
      <SimulatorControls stream={stream} />

      {/* Channel Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        <MetricCard
          title="Battery Voltage"
          icon={BatteryCharging}
          value={formatVal(battery)}
          unit="V"
          statusLabel={battery?.quality_status || "Standby"}
          statusVariant={qualityVariant(battery?.quality_status)}
          details="EPS Bus Potential"
        />

        <MetricCard
          title="Temperature"
          icon={Thermometer}
          value={formatVal(temp)}
          unit="°C"
          statusLabel={temp?.quality_status || "Standby"}
          statusVariant={qualityVariant(temp?.quality_status)}
          details="Thermal Sensor Deck"
        />

        <MetricCard
          title="Attitude — Roll"
          icon={Compass}
          value={formatVal(roll)}
          unit="deg"
          statusLabel={roll?.quality_status || "Standby"}
          statusVariant={qualityVariant(roll?.quality_status)}
          details="ADCS X-axis gyro"
        />

        <MetricCard
          title="Attitude — Pitch"
          icon={Compass}
          value={formatVal(pitch)}
          unit="deg"
          statusLabel={pitch?.quality_status || "Standby"}
          statusVariant={qualityVariant(pitch?.quality_status)}
          details="ADCS Y-axis gyro"
        />

        <MetricCard
          title="Attitude — Yaw"
          icon={Compass}
          value={formatVal(yaw)}
          unit="deg"
          statusLabel={yaw?.quality_status || "Standby"}
          statusVariant={qualityVariant(yaw?.quality_status)}
          details="ADCS Z-axis gyro"
        />
      </div>

      {/* Last Update & Stream Metadata */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-2 text-slate-300">
          <Clock className="w-4 h-4 text-cyan-400" />
          <span>Last Telemetry Update:</span>
          <span className="text-slate-200">
            {lastDataUpdate
              ? new Date(lastDataUpdate).toISOString().replace("T", " ").slice(0, 19) + " UTC"
              : "No frames received yet"}
          </span>
        </div>
        <div className="flex items-center gap-3 text-slate-400">
          <span>Chart Buffer: {chartHistory.length} / 60 points</span>
          <StatusBadge
            variant={isRunning ? "online" : "muted"}
            label={isRunning ? "Streaming Active" : "Idle"}
          />
        </div>
      </div>

      {/* 5 Dedicated Live Recharts Containers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TelemetryChart
          title="Battery Voltage Telemetry"
          subtitle="EPS Bus Potential (V)"
          unit="V"
          data={chartHistory}
          series={[{ dataKey: "battery_voltage", name: "Battery (V)", color: "#22d3ee" }]}
        />

        <TelemetryChart
          title="Spacecraft Temperature Telemetry"
          subtitle="Thermal Sensor Deck (°C)"
          unit="°C"
          data={chartHistory}
          series={[{ dataKey: "temperature", name: "Temperature (°C)", color: "#10b981" }]}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <TelemetryChart
          title="Roll Angle Telemetry"
          subtitle="ADCS X-Axis (degrees)"
          unit="deg"
          data={chartHistory}
          series={[{ dataKey: "roll", name: "Roll (deg)", color: "#22d3ee" }]}
        />
        <TelemetryChart
          title="Pitch Angle Telemetry"
          subtitle="ADCS Y-Axis (degrees)"
          unit="deg"
          data={chartHistory}
          series={[{ dataKey: "pitch", name: "Pitch (deg)", color: "#10b981" }]}
        />
        <TelemetryChart
          title="Yaw Angle Telemetry"
          subtitle="ADCS Z-Axis (degrees)"
          unit="deg"
          data={chartHistory}
          series={[{ dataKey: "yaw", name: "Yaw (deg)", color: "#f59e0b" }]}
        />
      </div>
    </div>
  );
}
