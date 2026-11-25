import { AlertTriangle, BellOff } from "lucide-react";
import { Link } from "react-router-dom";
import EmptyState from "../common/EmptyState";

export default function AlertSummary({ counts = null, alerts = [] }) {
  const critical = counts?.critical ?? "—";
  const warning = counts?.warning ?? "—";
  const info = counts?.info ?? "—";

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
          Recent Alerts
        </div>
        {alerts.length === 0 ? (
          <EmptyState
            icon={BellOff}
            title="No alert data available yet."
            description="Anomaly detection endpoints are not enabled in Phase 2. Live alerts will appear once Phase 4 detection is active."
            phaseBadge="Pending Phase 4"
            compact
          />
        ) : null}
      </div>
    </section>
  );
}
