import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BellOff,
  CheckCheck,
  Eye,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import StatusBadge from "../components/common/StatusBadge";

function severityVariant(severity) {
  if (severity === "CRITICAL") return "critical";
  if (severity === "WARNING") return "warning";
  return "info";
}

function statusVariant(status) {
  if (status === "ACTIVE") return "critical";
  if (status === "ACKNOWLEDGED") return "warning";
  return "nominal";
}

export default function Alerts({ stream }) {
  const {
    alerts,
    alertSummary,
    alertsTotal,
    alertsLoading,
    alertsError,
    alertFilters,
    updateAlertFilters,
    refreshAlerts,
    pendingAlertAction,
    alertActionError,
    clearAlertActionError,
    acknowledgeAlert,
    resolveAlert,
    detectionStatus,
  } = stream;

  const [selectedAlertId, setSelectedAlertId] = useState(null);

  useEffect(() => {
    if (alerts.length === 0) {
      setSelectedAlertId(null);
      return;
    }
    if (!selectedAlertId || !alerts.some((a) => a.alert_id === selectedAlertId)) {
      setSelectedAlertId(alerts[0].alert_id);
    }
  }, [alerts, selectedAlertId]);

  const selectedAlert = alerts.find((a) => a.alert_id === selectedAlertId) || null;

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-slate-100">
              Telemetry Anomaly & Sensor Integrity Alerts
            </div>
            <div className="text-xs text-slate-400">
              Live database-persisted alerts detected by statistical and cross-signal integrity checks ({alertsTotal} matching).
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge
            variant="critical"
            label={`Critical: ${alertSummary ? alertSummary.critical_active : "—"}`}
          />
          <StatusBadge
            variant="warning"
            label={`Warning: ${alertSummary ? alertSummary.warning_active : "—"}`}
          />
          <StatusBadge
            variant="info"
            label={`Info: ${alertSummary ? alertSummary.info_active : "—"}`}
          />
          <StatusBadge
            variant={detectionStatus?.engine_active ? "online" : "muted"}
            label={detectionStatus?.engine_active ? "Detector Active" : "Detector Standby"}
          />
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Severity:</span>
            <select
              aria-label="Filter by severity"
              value={alertFilters.severity}
              onChange={(e) =>
                updateAlertFilters({ ...alertFilters, severity: e.target.value })
              }
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="WARNING">WARNING</option>
              <option value="INFO">INFO</option>
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Type:</span>
            <select
              aria-label="Filter by alert type"
              value={alertFilters.alertType}
              onChange={(e) =>
                updateAlertFilters({ ...alertFilters, alertType: e.target.value })
              }
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All Types</option>
              <option value="STATISTICAL_ANOMALY">STATISTICAL_ANOMALY</option>
              <option value="RATE_OF_CHANGE">RATE_OF_CHANGE</option>
              <option value="ENGINEERING_LIMIT">ENGINEERING_LIMIT</option>
              <option value="SENSOR_MISSING">SENSOR_MISSING</option>
              <option value="SENSOR_FROZEN">SENSOR_FROZEN</option>
              <option value="SENSOR_INVALID">SENSOR_INVALID</option>
              <option value="SENSOR_STALE">SENSOR_STALE</option>
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Status:</span>
            <select
              aria-label="Filter by alert status"
              value={alertFilters.status}
              onChange={(e) =>
                updateAlertFilters({ ...alertFilters, status: e.target.value })
              }
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={() => refreshAlerts()}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Refresh</span>
        </button>
      </div>

      {alertsError && (
        <ErrorState
          title="Unable to Load Alerts"
          message={alertsError}
          onRetry={() => refreshAlerts()}
        />
      )}

      {alertActionError && (
        <ErrorState
          title="Alert Update Failed"
          message={alertActionError}
          onRetry={clearAlertActionError}
        />
      )}

      {/* Main Split Layout: Alert List + Alert Details */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Alert List Layout */}
        <div className="xl:col-span-2 rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Persisted Alert Queue ({alerts.length})
            </span>
            <span className="text-[11px] font-mono text-slate-500">
              Active: {alertSummary?.active ?? 0} // Ack: {alertSummary?.acknowledged ?? 0} // Resolved: {alertSummary?.resolved ?? 0}
            </span>
          </div>

          {alertsLoading ? (
            <div className="p-5">
              <LoadingState title="Loading alerts from PostgreSQL..." subtitle="Fetching persisted findings." />
            </div>
          ) : alerts.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={BellOff}
                title="No alert data available yet."
                description="Start the telemetry simulator and inject a fault scenario (or wait for an anomaly/integrity violation) to generate persisted alerts."
                phaseBadge="Real-Time Detection Ready"
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#060b16] text-[10px] font-mono uppercase text-slate-400">
                    <th className="py-2.5 px-3">Severity</th>
                    <th className="py-2.5 px-3">Type</th>
                    <th className="py-2.5 px-3">Target</th>
                    <th className="py-2.5 px-3">Explanation</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Detected</th>
                    <th className="py-2.5 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {alerts.map((alert) => {
                    const isSelected = alert.alert_id === selectedAlertId;
                    const ackBusy = pendingAlertAction === `ack:${alert.alert_id}`;
                    const resBusy = pendingAlertAction === `resolve:${alert.alert_id}`;
                    return (
                      <tr
                        key={alert.alert_id}
                        onClick={() => setSelectedAlertId(alert.alert_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? "bg-cyan-500/10" : "hover:bg-slate-900/50"
                        }`}
                      >
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <StatusBadge
                            variant={severityVariant(alert.severity)}
                            label={alert.severity}
                          />
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300 whitespace-nowrap">
                          {alert.alert_type}
                        </td>
                        <td className="py-2.5 px-3 font-mono whitespace-nowrap">
                          <div className="text-slate-200 font-semibold">{alert.sensor_name}</div>
                          <div className="text-[10px] text-slate-500">
                            {alert.satellite_id} // ×{alert.occurrence_count}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 max-w-xs">
                          <div className="font-medium text-slate-200">{alert.title}</div>
                          <div className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">
                            {alert.description}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <StatusBadge
                            variant={statusVariant(alert.status)}
                            label={alert.status}
                          />
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                          {new Date(alert.last_detected_at).toISOString().slice(11, 19)} UTC
                        </td>
                        <td
                          className="py-2.5 px-3 whitespace-nowrap"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex items-center gap-1.5">
                            <button
                              type="button"
                              disabled={alert.status !== "ACTIVE" || ackBusy || resBusy}
                              onClick={() => acknowledgeAlert(alert.alert_id)}
                              className="px-2 py-1 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-[10px] font-mono disabled:opacity-35 disabled:cursor-not-allowed"
                            >
                              {ackBusy ? "..." : "Ack"}
                            </button>
                            <button
                              type="button"
                              disabled={alert.status === "RESOLVED" || ackBusy || resBusy}
                              onClick={() => resolveAlert(alert.alert_id)}
                              className="px-2 py-1 rounded border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 text-[10px] font-mono disabled:opacity-35 disabled:cursor-not-allowed"
                            >
                              {resBusy ? "..." : "Resolve"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Alert Details & Evidence Panel */}
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-slate-100">Alert Details & Evidence</h2>
              </div>
              {selectedAlert && (
                <StatusBadge
                  variant={statusVariant(selectedAlert.status)}
                  label={selectedAlert.status}
                />
              )}
            </div>

            {!selectedAlert ? (
              <div className="mt-4 space-y-3 text-xs font-mono">
                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px]">Selected Alert ID</div>
                  <div className="text-slate-300 mt-1">None selected</div>
                </div>
                <div className="rounded border border-slate-800 bg-[#060b16] p-3 text-slate-400 font-sans">
                  Select an alert row to inspect measured baselines, z-scores, reason codes, and JSON evidence.
                </div>
              </div>
            ) : (
              <div className="mt-4 space-y-3 text-xs font-mono">
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                    <div className="text-slate-500 uppercase text-[10px]">Alert ID</div>
                    <div className="text-cyan-300 mt-0.5 font-semibold">
                      {selectedAlert.alert_id}
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                    <div className="text-slate-500 uppercase text-[10px]">Reason Code</div>
                    <div className="text-slate-200 mt-0.5 truncate">
                      {selectedAlert.reason_code}
                    </div>
                  </div>
                </div>

                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px]">Operator Explanation</div>
                  <div className="text-slate-200 mt-1 font-sans leading-relaxed">
                    {selectedAlert.description}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                    <div className="text-slate-500 uppercase text-[10px]">Observed</div>
                    <div className="text-slate-200 mt-0.5">
                      {selectedAlert.observed_value ?? "MISSING"}
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                    <div className="text-slate-500 uppercase text-[10px]">Z-Score</div>
                    <div className="text-slate-200 mt-0.5">
                      {selectedAlert.z_score !== null && selectedAlert.z_score !== undefined
                        ? `${selectedAlert.z_score}σ`
                        : "—"}
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                    <div className="text-slate-500 uppercase text-[10px]">Occurrences</div>
                    <div className="text-slate-200 mt-0.5">×{selectedAlert.occurrence_count}</div>
                  </div>
                </div>

                <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                  <div className="text-slate-500 uppercase text-[10px]">Expected Baseline / Range</div>
                  <div className="text-slate-300 mt-0.5">
                    {selectedAlert.expected_range || "N/A"}
                  </div>
                </div>

                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px] mb-1.5">
                    Measured Evidence (JSON)
                  </div>
                  <pre className="text-[11px] text-slate-300 overflow-x-auto max-h-44">
                    {JSON.stringify(selectedAlert.evidence, null, 2)}
                  </pre>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    disabled={
                      selectedAlert.status !== "ACTIVE" ||
                      pendingAlertAction === `ack:${selectedAlert.alert_id}`
                    }
                    onClick={() => acknowledgeAlert(selectedAlert.alert_id)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-amber-500/35 bg-amber-500/15 hover:bg-amber-500/25 text-amber-200 disabled:opacity-35 disabled:cursor-not-allowed"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Acknowledge</span>
                  </button>
                  <button
                    type="button"
                    disabled={
                      selectedAlert.status === "RESOLVED" ||
                      pendingAlertAction === `resolve:${selectedAlert.alert_id}`
                    }
                    onClick={() => resolveAlert(selectedAlert.alert_id)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-emerald-500/35 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-200 disabled:opacity-35 disabled:cursor-not-allowed"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    <span>Resolve</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="mt-5 pt-3 border-t border-slate-800 text-[11px] font-mono text-slate-500">
            Human operators remain responsible for triage decisions.
          </div>
        </div>
      </div>
    </div>
  );
}
