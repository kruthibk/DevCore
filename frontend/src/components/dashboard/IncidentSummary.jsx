import { ClipboardList, FileCheck2 } from "lucide-react";
import { Link } from "react-router-dom";
import EmptyState from "../common/EmptyState";
import StatusBadge from "../common/StatusBadge";

function incidentStatusVariant(status) {
  if (status === "OPEN") return "critical";
  if (status === "INVESTIGATING") return "warning";
  if (status === "MITIGATED") return "info";
  return "nominal";
}

function severityVariant(severity) {
  if (severity === "CRITICAL") return "critical";
  if (severity === "WARNING") return "warning";
  return "info";
}

export default function IncidentSummary({ counts = null, incidents = [], error = null }) {
  const total = counts?.total ?? "—";
  const open = counts?.open ?? "—";
  const resolved = counts?.resolved ?? "—";

  return (
    <section className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between gap-2 mb-4">
          <div className="flex items-center gap-2">
            <FileCheck2 className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-slate-100">Incident Overview</h2>
          </div>
          <Link
            to="/incidents"
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
          >
            View Incidents →
          </Link>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="rounded border border-slate-800 bg-[#060b16] p-3">
            <div className="text-[10px] font-mono uppercase text-slate-400">Total</div>
            <div className="text-xl font-mono font-bold text-slate-200 mt-1">{total}</div>
          </div>
          <div className="rounded border border-amber-500/20 bg-amber-500/5 p-3">
            <div className="text-[10px] font-mono uppercase text-amber-300/80">Open</div>
            <div className="text-xl font-mono font-bold text-amber-300 mt-1">{open}</div>
          </div>
          <div className="rounded border border-emerald-500/20 bg-emerald-500/5 p-3">
            <div className="text-[10px] font-mono uppercase text-emerald-300/80">Resolved</div>
            <div className="text-xl font-mono font-bold text-emerald-300 mt-1">{resolved}</div>
          </div>
        </div>

        <div className="text-xs font-mono uppercase tracking-wider text-slate-500 mb-2">
          Recent Incidents
        </div>

        {error ? (
          <div className="rounded border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200 font-mono">
            {error}
          </div>
        ) : incidents.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="No tracked incidents yet."
            description="Log an incident from Alerts, AI Copilot, or the Incidents page to begin tracked operator triage."
            phaseBadge="Incident Registry Ready"
            compact
          />
        ) : (
          <div className="space-y-2">
            {incidents.slice(0, 4).map((inc) => (
              <Link
                key={inc.incident_id}
                to={`/incidents?id=${encodeURIComponent(inc.incident_id)}`}
                className="block rounded border border-slate-800 bg-[#060b16] hover:border-cyan-500/40 p-2.5 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[11px] font-mono font-semibold text-cyan-300 shrink-0">
                      {inc.incident_id}
                    </span>
                    <span className="text-xs text-slate-200 truncate">{inc.title}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <StatusBadge variant={severityVariant(inc.severity)} label={inc.severity} showDot={false} />
                    <StatusBadge variant={incidentStatusVariant(inc.status)} label={inc.status} showDot={false} />
                  </div>
                </div>
                <div className="mt-1 text-[10px] font-mono text-slate-500 flex items-center justify-between">
                  <span>subsystem: {inc.subsystem}</span>
                  <span>by {inc.created_by}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
