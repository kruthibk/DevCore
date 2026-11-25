import { Clock, Radio, Satellite } from "lucide-react";
import StatusBadge from "../common/StatusBadge";

export default function SatelliteStatus({ lastProbeAt }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-[#090f1e] p-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="w-11 h-11 rounded-lg border border-cyan-500/30 bg-cyan-500/10 flex items-center justify-center text-cyan-400 shrink-0">
            <Satellite className="w-6 h-6" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="text-lg font-bold tracking-wide text-slate-100 font-mono">
                SAT-01
              </h2>
              <StatusBadge variant="standby" label="SIMULATION / STANDBY" />
              <span className="text-[11px] font-mono text-slate-500">
                Simulated Prototype Identifier
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Ground-station telemetry link is on standby. No live spacecraft RF link is connected; simulated frames start in Phase 3.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 lg:min-w-[380px]">
          <div className="rounded border border-slate-800 bg-[#060b16] px-3.5 py-2.5">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-500">
              <Radio className="w-3 h-3 text-cyan-400" />
              <span>Telemetry Connection</span>
            </div>
            <div className="mt-1">
              <StatusBadge
                variant="muted"
                label="Waiting for Phase 3 Link"
                className="text-[10px]"
              />
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-[#060b16] px-3.5 py-2.5">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-500">
              <Clock className="w-3 h-3 text-emerald-400" />
              <span>Last Data Update</span>
            </div>
            <div className="mt-1 text-xs font-mono text-slate-300">
              No telemetry frames yet
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-0.5">
              API probe:{" "}
              {lastProbeAt
                ? new Date(lastProbeAt).toISOString().slice(11, 19) + " UTC"
                : "Pending"}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
