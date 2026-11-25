import { ClipboardList, FileCheck2 } from "lucide-react";
import { Link } from "react-router-dom";
import EmptyState from "../common/EmptyState";

export default function IncidentSummary({ counts = null, incidents = [] }) {
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
        {incidents.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="Incident management will be enabled in a later phase."
            description="Backend incident workflows, root-cause records, and operator approvals are scheduled for upcoming phases."
            phaseBadge="Scheduled Later Phase"
            compact
          />
        ) : null}
      </div>
    </section>
  );
}
