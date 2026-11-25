import { AlertTriangle, BellOff } from "lucide-react";
import { Link } from "react-router-dom";
import EmptyState from "../common/EmptyState";
import StatusBadge from "../common/StatusBadge";

function severityVariant(severity) {
  if (severity === "CRITICAL") return "critical";
  if (severity === "WARNING") return "warning";
  return "info";
}

export default function AlertSummary({ summary = null, alerts = [], error = null }) {
  const critical = summary ? summary.critical_active : "—";
  const warning = summary ? summary.warning_active : "—";
  const info = summary ? summary.info_active : "—";

  return (
    <section className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between gap-2 mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-slate-100">Alert Summary</h2>
          </div>
          <Link
            to="/alerts"
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            View Alerts →
          </Link>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="rounded border border-rose-500/20 bg-rose-500/5 p-3">
            <div className="text-[10px] font-mono uppercase text-rose-300/80">Critical</div>
            <div className="text-xl font-mono font-bold text-rose-300 mt-1">{critical}</div>
          </div>
          <div className="rounded border border-amber-500/20 bg-amber-500/5 p-3">
            <div className="text-[10px] font-mono uppercase text-amber-300/80">Warning</div>
            <div className="text-xl font-mono font-bold text-amber-300 mt-1">{warning}</div>
          </div>
          <div className="rounded border border-cyan-500/20 bg-cyan-500/5 p-3">
            <div className="text-[10px] font-mono uppercase text-cyan-300/80">Info</div>
            <div className="text-xl font-mono font-bold text-cyan-300 mt-1">{info}</div>
          </div>
        </div>

        <div className="text-xs font-mono uppercase tracking-wider text-slate-500 mb-2">
          Recent Persisted Alerts
        </div>

        {error ? (
          <div className="rounded border border-rose-500/30 bg-rose-500/10 p-3 text-xs font-mono text-rose-200">
            Unable to load alerts: {error}
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState
            icon={BellOff}
            title="No alert data available yet."
            description="Persisted statistical anomaly and sensor integrity alerts will appear here when detected."
            phaseBadge="Detection Active"
            compact
          />
        ) : (
          <div className="space-y-2">
            {alerts.slice(0, 4).map((alert) => (
              <Link
                key={alert.alert_id}
                to="/alerts"
                className="block rounded border border-slate-800 bg-[#060b16] hover:border-slate-700 p-3 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <StatusBadge
                      variant={severityVariant(alert.severity)}
                      label={alert.severity}
                    />
                    <span className="text-xs font-semibold text-slate-200 truncate">
                      {alert.title}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    {alert.status} // ×{alert.occurrence_count}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1 line-clamp-1">{alert.description}</p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
