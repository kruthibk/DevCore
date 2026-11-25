import { BatteryCharging, Clock, Compass, Radio, Thermometer } from "lucide-react";
import StatusBadge from "../components/common/StatusBadge";
import MetricCard from "../components/dashboard/MetricCard";
import TelemetryChart from "../components/dashboard/TelemetryChart";

export default function Telemetry() {
  return (
    <div className="space-y-6">
      {/* Phase 3 Waiting Notice */}
      <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <Radio className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-cyan-200">
              Waiting for telemetry — simulator will be connected in Phase 3
            </div>
            <p className="text-xs text-cyan-200/75 mt-0.5">
              Channel schemas and chart containers are ready for SAT-01 ingestion. No fabricated telemetry values are displayed.
            </p>
          </div>
        </div>
        <StatusBadge variant="standby" label="SAT-01 // STANDBY" />
      </div>

      {/* Channel Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        <MetricCard
          title="Battery Voltage"
          icon={BatteryCharging}
          value="—"
          unit="V"
          statusLabel="Standby"
          details="Sensor status: Waiting for stream"
        />

        <MetricCard
          title="Temperature"
          icon={Thermometer}
          value="—"
          unit="°C"
          statusLabel="Standby"
          details="Sensor status: Waiting for stream"
        />

        <MetricCard
          title="Attitude — Roll"
          icon={Compass}
          value="—"
          unit="deg"
          statusLabel="Standby"
          details="ADCS X-axis gyro"
        />

        <MetricCard
          title="Attitude — Pitch"
          icon={Compass}
          value="—"
          unit="deg"
          statusLabel="Standby"
          details="ADCS Y-axis gyro"
        />

        <MetricCard
          title="Attitude — Yaw"
          icon={Compass}
          value="—"
          unit="deg"
          statusLabel="Standby"
          details="ADCS Z-axis gyro"
        />
      </div>

      {/* Last Update & Stream Metadata */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] px-4 py-3 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-2 text-slate-300">
          <Clock className="w-4 h-4 text-cyan-400" />
          <span>Last Telemetry Update:</span>
          <span className="text-slate-400">No frames received (awaiting Phase 3)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-500">Ingestion State:</span>
          <StatusBadge variant="muted" label="Idle / Disconnected" />
        </div>
      </div>

      {/* Chart Containers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TelemetryChart
          title="Battery Voltage Telemetry"
          subtitle="EPS Bus Potential (V)"
          unit="V"
          data={[]}
          emptyTitle="Waiting for telemetry — simulator will be connected in Phase 3"
          emptyDescription="Real-time EPS voltage frames will plot here once the Phase 3 stream starts."
          series={[{ dataKey: "voltage", name: "Voltage (V)", color: "#22d3ee" }]}
        />

        <TelemetryChart
          title="Spacecraft Temperature Telemetry"
          subtitle="Thermal Sensor Deck (°C)"
          unit="°C"
          data={[]}
          emptyTitle="Waiting for telemetry — simulator will be connected in Phase 3"
          emptyDescription="Thermal sensor telemetry will plot here once the Phase 3 stream starts."
          series={[{ dataKey: "temperature", name: "Temperature (°C)", color: "#10b981" }]}
        />
      </div>

      <TelemetryChart
        title="Three-Axis Attitude Telemetry (Roll / Pitch / Yaw)"
        subtitle="ADCS Orientation Angles (degrees)"
        unit="deg"
        data={[]}
        emptyTitle="Waiting for telemetry — simulator will be connected in Phase 3"
        emptyDescription="Roll, pitch, and yaw attitude channels will plot here once the Phase 3 stream starts."
        series={[
          { dataKey: "roll", name: "Roll", color: "#22d3ee" },
          { dataKey: "pitch", name: "Pitch", color: "#10b981" },
          { dataKey: "yaw", name: "Yaw", color: "#f59e0b" },
        ]}
      />
    </div>
  );
}
