import { AlertTriangle, BellOff, ShieldAlert } from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import StatusBadge from "../components/common/StatusBadge";

export default function Alerts() {
  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <div>
            <div className="text-sm font-semibold text-slate-100">
              Telemetry Anomaly Alert Queue
            </div>
            <div className="text-xs text-slate-400">
              Real-time threshold and anomaly alerts will appear here once Phase 4 detection is connected.
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge variant="critical" label="Critical: —" />
          <StatusBadge variant="warning" label="Warning: —" />
          <StatusBadge variant="info" label="Info: —" />
        </div>
      </div>

      {/* Main Split Layout: Alert List + Alert Details */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Alert List Layout */}
        <div className="xl:col-span-2 rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Alert Stream
            </span>
            <span className="text-[11px] font-mono text-slate-500">
              Backend Engine: Phase 4
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800 bg-[#060b16] text-[11px] font-mono uppercase text-slate-400">
                  <th className="py-2.5 px-4">Severity</th>
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-4">Sensor / Source</th>
                  <th className="py-2.5 px-4">Alert Summary</th>
                </tr>
              </thead>
            </table>
          </div>

          <div className="p-6">
            <EmptyState
              icon={BellOff}
              title="No alert data available yet."
              description="No artificial alerts are generated in Phase 2. Once the anomaly detection backend is implemented in Phase 4, triggered subsystem alerts will populate this queue."
              phaseBadge="Awaiting Anomaly Detection Backend"
            />
          </div>
        </div>

        {/* Alert Details Panel */}
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
              <ShieldAlert className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-100">Alert Details</h2>
            </div>

            <div className="mt-4 space-y-3 text-xs font-mono">
              <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                <div className="text-slate-500 uppercase text-[10px]">Selected Alert ID</div>
                <div className="text-slate-300 mt-1">None selected</div>
              </div>

              <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                <div className="text-slate-500 uppercase text-[10px]">Subsystem & Sensor</div>
                <div className="text-slate-400 mt-1">—</div>
              </div>

              <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                <div className="text-slate-500 uppercase text-[10px]">Observed Threshold / Evidence</div>
                <div className="text-slate-400 mt-1">
                  Select an alert from the stream when Phase 4 detection is active to inspect sensor readings and triage recommendations.
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-3 border-t border-slate-800 text-[11px] font-mono text-slate-500">
            Status: Read-only standby layout (Phase 2)
          </div>
        </div>
      </div>
    </div>
  );
}
