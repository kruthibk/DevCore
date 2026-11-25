import { ClipboardList, FileCheck2, FileText } from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import StatusBadge from "../components/common/StatusBadge";

export default function Incidents() {
  return (
    <div className="space-y-6">
      {/* Header Summary Bar */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <FileCheck2 className="w-5 h-5 text-cyan-400" />
          <div>
            <div className="text-sm font-semibold text-slate-100">
              Incident Management Console
            </div>
            <div className="text-xs text-slate-400">
              Structured anomaly incident tracking and operator review layout. Creation and approval workflows will be implemented in a later phase.
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge variant="muted" label="Read-Only Layout" />
          <StatusBadge variant="standby" label="Backend Pending" />
        </div>
      </div>

      {/* Incident Table + Details Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Incident Table Layout */}
        <div className="xl:col-span-2 rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Incident Registry
            </span>
            <span className="text-[11px] font-mono text-slate-500">
              Total: — // Open: — // Resolved: —
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-[#060b16] text-[11px] font-mono uppercase text-slate-400">
                  <th className="py-2.5 px-4">Incident ID</th>
                  <th className="py-2.5 px-4">Title</th>
                  <th className="py-2.5 px-4">Severity</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Created</th>
                </tr>
              </thead>
            </table>
          </div>

          <div className="p-6">
            <EmptyState
              icon={ClipboardList}
              title="Incident management will be enabled in a later phase."
              description="No mock incidents are generated in Phase 2. Incident creation, root-cause linking, and operator sign-off endpoints will be integrated in upcoming phases."
              phaseBadge="Scheduled Later Phase"
            />
          </div>
        </div>

        {/* Incident Details Placeholder Layout */}
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
              <FileText className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-100">Incident Details</h2>
            </div>

            <div className="mt-4 space-y-3 text-xs font-mono">
              <div className="grid grid-cols-2 gap-2.5">
                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px]">Incident ID</div>
                  <div className="text-slate-300 mt-1">—</div>
                </div>
                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px]">Severity / Status</div>
                  <div className="text-slate-300 mt-1">— / —</div>
                </div>
              </div>

              <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                <div className="text-slate-500 uppercase text-[10px]">Title</div>
                <div className="text-slate-400 mt-1">No incident selected</div>
              </div>

              <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                <div className="text-slate-500 uppercase text-[10px]">Created Timestamp</div>
                <div className="text-slate-400 mt-1">—</div>
              </div>

              <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                <div className="text-slate-500 uppercase text-[10px]">Triage & Copilot Summary</div>
                <div className="text-slate-400 mt-1 leading-relaxed">
                  Incident timelines, correlated telemetry anomalies, and copilot triage playbooks will populate here once incident management is active.
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-slate-800 text-[11px] font-mono text-slate-500">
            Creation and approval actions disabled in Phase 2
          </div>
        </div>
      </div>
    </div>
  );
}
