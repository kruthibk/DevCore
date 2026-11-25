import {
  Activity,
  AlertTriangle,
  Bot,
  Cpu,
  Lock,
  Radio,
  Satellite,
  Terminal,
} from "lucide-react";

const PHASE_1_NAV = [
  { id: "overview", label: "Mission Control", icon: Activity },
  { id: "diagnostics", label: "System Diagnostics", icon: Terminal },
];

const UPCOMING_MODULES = [
  { label: "Telemetry Stream", icon: Radio, phase: "Phase 2" },
  { label: "Anomaly Triage", icon: AlertTriangle, phase: "Phase 3" },
  { label: "AI Copilot", icon: Bot, phase: "Phase 4" },
];

export default function Sidebar({ activeView, onSelectView, team }) {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-800/80 bg-[#070b16] flex flex-col justify-between">
      <div>
        <div className="h-16 px-5 border-b border-slate-800/80 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <Satellite className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-wider text-slate-100">
              SAT-TRIAGE
            </div>
            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-400/80">
              Orbital Ops Shell
            </div>
          </div>
        </div>

        <div className="px-3 pt-5">
          <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
            Phase 1 // Foundation
          </div>
          <nav className="space-y-1">
            {PHASE_1_NAV.map((item) => {
              const Icon = item.icon;
              const isActive = activeView === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectView(item.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          <div className="px-2.5 pt-6 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-600">
            Roadmap Modules
          </div>
          <div className="space-y-1">
            {UPCOMING_MODULES.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.label}
                  className="flex items-center justify-between px-3 py-2 rounded-lg text-xs text-slate-600 border border-slate-800/40 bg-slate-900/20 cursor-not-allowed"
                  title={`${item.label} is scheduled for ${item.phase}`}
                >
                  <span className="flex items-center gap-2.5">
                    <Icon className="w-3.5 h-3.5" />
                    <span>{item.label}</span>
                  </span>
                  <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-500">
                    <Lock className="w-2.5 h-2.5" />
                    {item.phase}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="p-4 border-t border-slate-800/80 bg-[#050811]/70">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>{team?.name || "DevCore"}</span>
          <span className="text-slate-600">//</span>
          <span className="text-cyan-400/90">{team?.event || "AVISHKAR'26"}</span>
        </div>
        <div className="mt-1 text-[11px] font-mono text-slate-500">
          ID: {team?.team_id || "AV26-BF34B6F9D2"}
        </div>
      </div>
    </aside>
  );
}
