import { Activity, AlertTriangle, ShieldCheck } from "lucide-react";
import StatusBadge from "../common/StatusBadge";

function integrityVariant(status) {
  if (status === "OK") return "online";
  if (status === "MISSING") return "critical";
  if (status === "INVALID") return "critical";
  if (status === "FROZEN" || status === "STALE") return "warning";
  if (status === "STREAM_INACTIVE") return "standby";
  return "muted";
}

export default function SensorIntegrityPanel({
  detectionStatus,
  detectionConfig,
  integrityIssues = [],
}) {
  const sensorStates = detectionStatus?.sensor_states || [];
  const streamInactive = detectionStatus?.stream_state === "STREAM_INACTIVE";

  return (
    <section className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-slate-100">
              Cross-Signal Sensor Integrity & Detection Engine
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Independent numerical inspection for missing, frozen, impossible/invalid, and stale sensor feeds.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            variant={detectionStatus?.engine_active ? "online" : "muted"}
            label={detectionStatus?.engine_active ? "ENGINE: ACTIVE" : "ENGINE: STANDBY"}
          />
          <StatusBadge
            variant={streamInactive ? "standby" : "online"}
            label={streamInactive ? "STREAM: INACTIVE" : "STREAM: ACTIVE"}
          />
          <StatusBadge
            variant={
              (detectionStatus?.integrity_issue_count ?? 0) > 0 ? "warning" : "nominal"
            }
            label={`ISSUES: ${detectionStatus?.integrity_issue_count ?? 0}`}
          />
        </div>
      </div>

      {/* Engine Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
        <div className="rounded border border-slate-800 bg-[#060b16] p-3">
          <div className="text-[10px] uppercase text-slate-500">Processed Samples</div>
          <div className="text-lg font-bold text-slate-100 mt-1">
            {detectionStatus?.processed_sample_count ?? 0}
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-[#060b16] p-3">
          <div className="text-[10px] uppercase text-slate-500">Open Alerts</div>
          <div className="text-lg font-bold text-amber-300 mt-1">
            {detectionStatus?.active_alert_count ?? 0}
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-[#060b16] p-3">
          <div className="text-[10px] uppercase text-slate-500">Persisted Updates</div>
          <div className="text-lg font-bold text-emerald-300 mt-1">
            {detectionStatus?.persisted_alerts_count ?? 0}
          </div>
        </div>
        <div className="rounded border border-slate-800 bg-[#060b16] p-3">
          <div className="text-[10px] uppercase text-slate-500">Last Evaluated</div>
          <div className="text-xs font-semibold text-slate-200 mt-1.5">
            {detectionStatus?.last_processed_at
              ? new Date(detectionStatus.last_processed_at).toISOString().slice(11, 19) + " UTC"
              : "No samples yet"}
          </div>
        </div>
      </div>

      {detectionStatus?.last_persistence_error && (
        <div className="rounded border border-rose-500/30 bg-rose-500/10 p-3 text-xs font-mono text-rose-200">
          Alert DB Persistence Error: {detectionStatus.last_persistence_error}
        </div>
      )}

      {/* 5-Channel Integrity Table */}
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800 bg-[#060b16] text-[10px] font-mono uppercase text-slate-400">
              <th className="py-2.5 px-3">Sensor Channel</th>
              <th className="py-2.5 px-3">Integrity Status</th>
              <th className="py-2.5 px-3">Latest Value</th>
              <th className="py-2.5 px-3">Rolling Baseline (n)</th>
              <th className="py-2.5 px-3">Last Received</th>
              <th className="py-2.5 px-3">Notes / Finding</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70 font-mono">
            {sensorStates.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-4 px-3 text-center text-slate-500">
                  Awaiting detection status from backend...
                </td>
              </tr>
            ) : (
              sensorStates.map((ch) => (
                <tr key={ch.sensor_name} className="hover:bg-slate-900/40">
                  <td className="py-2.5 px-3 font-semibold text-slate-200">
                    {ch.sensor_name}
                  </td>
                  <td className="py-2.5 px-3">
                    <StatusBadge
                      variant={integrityVariant(ch.integrity_status)}
                      label={ch.integrity_status}
                    />
                  </td>
                  <td className="py-2.5 px-3 text-slate-200">
                    {ch.last_value !== null && ch.last_value !== undefined
                      ? `${ch.last_value} ${ch.unit}`
                      : "—"}
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">
                    {ch.baseline_mean !== null && ch.baseline_mean !== undefined
                      ? `${ch.baseline_mean} ± ${ch.baseline_std ?? 0} (${ch.baseline_samples})`
                      : `0 samples`}
                  </td>
                  <td className="py-2.5 px-3 text-slate-400">
                    {ch.last_received_at
                      ? new Date(ch.last_received_at).toISOString().slice(11, 19) + " UTC"
                      : "—"}
                  </td>
                  <td className="py-2.5 px-3 text-slate-400 font-sans">
                    {ch.issue_reason || "Normal sensor cadence"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Recent Integrity Findings + Threshold Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded border border-slate-800 bg-[#060b16] p-3.5">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span>Recent Integrity Findings ({integrityIssues.length})</span>
          </div>
          {integrityIssues.length === 0 ? (
            <div className="text-xs text-slate-500 py-2">
              No sensor integrity defects observed in this session.
            </div>
          ) : (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {integrityIssues.slice(0, 6).map((issue, idx) => (
                <div
                  key={`${issue.sensor_name}-${issue.detected_at}-${idx}`}
                  className="rounded border border-slate-800 bg-[#090f1e] p-2 text-xs"
                >
                  <div className="flex items-center justify-between gap-2 font-mono">
                    <span className="text-slate-200 font-semibold">
                      {issue.sensor_name} ({issue.integrity_status})
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(issue.detected_at).toISOString().slice(11, 19)} UTC
                    </span>
                  </div>
                  <div className="text-slate-400 mt-0.5">{issue.reason}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded border border-slate-800 bg-[#060b16] p-3.5">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>Detection Threshold Summary</span>
          </div>
          {detectionConfig ? (
            <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
              <div>Rolling Window: {detectionConfig.rolling_window_size} samples</div>
              <div>Min Baseline: {detectionConfig.min_baseline_samples} samples</div>
              <div>Z-Score Warn: ±{detectionConfig.z_score_warning}σ</div>
              <div>Z-Score Crit: ±{detectionConfig.z_score_critical}σ</div>
              <div>Frozen Window: {detectionConfig.frozen_consecutive_samples} identical</div>
              <div>Stale Timeout: {detectionConfig.stale_timeout_seconds}s</div>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Loading config...</div>
          )}
        </div>
      </div>
    </section>
  );
}
