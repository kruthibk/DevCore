import { useState } from "react";
import {
  Activity,
  BatteryWarning,
  Compass,
  Flame,
  PauseOctagon,
  Play,
  RotateCcw,
  Slash,
  Square,
} from "lucide-react";
import ErrorState from "../common/ErrorState";
import StatusBadge from "../common/StatusBadge";

const SENSOR_OPTIONS = [
  { value: "battery_voltage", label: "Battery Voltage (V)" },
  { value: "temperature", label: "Temperature (°C)" },
  { value: "roll", label: "Attitude — Roll (°)" },
  { value: "pitch", label: "Attitude — Pitch (°)" },
  { value: "yaw", label: "Attitude — Yaw (°)" },
];

export default function SimulatorControls({ stream }) {
  const {
    simulatorStatus,
    socketStatus,
    pendingAction,
    actionError,
    clearActionError,
    start,
    stop,
    injectFault,
    clearFaults,
  } = stream;

  const [targetSensor, setTargetSensor] = useState("temperature");
  const isRunning = Boolean(simulatorStatus?.running);
  const activeFaults = simulatorStatus?.active_faults || [];
  const isBusy = Boolean(pendingAction);

  return (
    <section className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-4">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-slate-100">
              Synthetic Telemetry Simulator Control
            </h2>
            <StatusBadge
              variant="standby"
              label={simulatorStatus?.data_origin || "SYNTHETIC SIMULATION DATA"}
            />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Backend-driven NumPy generator ({simulatorStatus?.interval_seconds ?? 1.0}s interval). Fault injections alter synthetic sensor streams; anomaly classification is deferred to Phase 4.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            variant={isRunning ? "online" : "muted"}
            label={isRunning ? "SIM: RUNNING" : "SIM: STOPPED"}
          />
          <StatusBadge
            variant={
              socketStatus === "connected"
                ? "online"
                : socketStatus === "connecting"
                ? "checking"
                : "offline"
            }
            label={`SIO: ${socketStatus.toUpperCase()}`}
          />
        </div>
      </div>

      {actionError && (
        <ErrorState
          title="Simulator Control Request Failed"
          message={actionError}
          onRetry={clearActionError}
        />
      )}

      {/* Primary Start / Stop + Target Sensor Selector */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => start()}
            disabled={isRunning || isBusy}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-emerald-500/40 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 text-xs font-mono font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{pendingAction === "start" ? "Starting..." : "Start Simulation"}</span>
          </button>

          <button
            type="button"
            onClick={() => stop()}
            disabled={!isRunning || isBusy}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-rose-500/40 bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 text-xs font-mono font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Square className="w-3.5 h-3.5" />
            <span>{pendingAction === "stop" ? "Stopping..." : "Stop Simulation"}</span>
          </button>

          <button
            type="button"
            onClick={() => clearFaults()}
            disabled={activeFaults.length === 0 || isBusy}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-700 bg-slate-800/70 hover:bg-slate-700/80 text-slate-200 text-xs font-mono disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>{pendingAction === "clear_faults" ? "Clearing..." : "Clear Faults"}</span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <label htmlFor="fault-target-sensor" className="text-slate-400">
            Target Sensor:
          </label>
          <select
            id="fault-target-sensor"
            value={targetSensor}
            onChange={(e) => setTargetSensor(e.target.value)}
            disabled={isBusy}
            className="rounded border border-slate-700 bg-[#050913] px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            {SENSOR_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Fault Injection Controls */}
      <div className="pt-2 border-t border-slate-800/80">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2.5">
          Fault Injection Scenarios
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          <button
            type="button"
            disabled={isBusy}
            onClick={() => injectFault("battery_drop")}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-200 text-xs font-mono disabled:opacity-40 transition-colors"
          >
            <BatteryWarning className="w-3.5 h-3.5 shrink-0" />
            <span>Battery Drop</span>
          </button>

          <button
            type="button"
            disabled={isBusy}
            onClick={() => injectFault("temperature_spike")}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-200 text-xs font-mono disabled:opacity-40 transition-colors"
          >
            <Flame className="w-3.5 h-3.5 shrink-0" />
            <span>Temp Spike</span>
          </button>

          <button
            type="button"
            disabled={isBusy}
            onClick={() => injectFault("attitude_disturbance")}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-200 text-xs font-mono disabled:opacity-40 transition-colors"
          >
            <Compass className="w-3.5 h-3.5 shrink-0" />
            <span>Attitude Disturbance</span>
          </button>

          <button
            type="button"
            disabled={isBusy}
            onClick={() => injectFault("frozen_sensor", targetSensor)}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-200 text-xs font-mono disabled:opacity-40 transition-colors"
          >
            <PauseOctagon className="w-3.5 h-3.5 shrink-0" />
            <span>Frozen Sensor</span>
          </button>

          <button
            type="button"
            disabled={isBusy}
            onClick={() => injectFault("missing_data", targetSensor)}
            className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-200 text-xs font-mono disabled:opacity-40 transition-colors"
          >
            <Slash className="w-3.5 h-3.5 shrink-0" />
            <span>Missing Data</span>
          </button>
        </div>
      </div>

      {/* Active Faults + Pipeline Counters */}
      <div className="pt-2 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] font-mono">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-slate-500">Active Faults:</span>
          {activeFaults.length === 0 ? (
            <span className="text-emerald-400">None (Nominal Synthetic Profile)</span>
          ) : (
            activeFaults.map((f, idx) => (
              <StatusBadge
                key={`${f.fault_type}-${f.target_sensor || "global"}-${idx}`}
                variant="warning"
                label={
                  f.target_sensor ? `${f.fault_type} (${f.target_sensor})` : f.fault_type
                }
              />
            ))
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-slate-400">
          <span>Generated: {simulatorStatus?.generated_count ?? 0}</span>
          <span>Streamed: {simulatorStatus?.streamed_count ?? 0}</span>
          <span>Persisted: {simulatorStatus?.persisted_count ?? 0}</span>
          {simulatorStatus?.last_persistence_error && (
            <span className="text-rose-400" title={simulatorStatus.last_persistence_error}>
              DB Persist Error
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
