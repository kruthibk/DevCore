import {
  Activity,
  AlertTriangle,
  Bot,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileCheck2,
  GitBranch,
  History,
  Lock,
  Radio,
  Satellite,
  Sliders,
  Terminal,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const PRIMARY_NAV = [
  { to: "/", label: "Overview", icon: Activity, end: true },
  { to: "/telemetry", label: "Telemetry", icon: Radio },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/fault-graph", label: "Fault Graph", icon: GitBranch },
  { to: "/copilot", label: "AI Copilot", icon: Bot },
  { to: "/incidents", label: "Incidents", icon: FileCheck2 },
];

const UPCOMING_NAV = [
  { label: "Predictive Simulator", icon: Sliders },
  { label: "Audit History", icon: History },
];

export default function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  team,
}) {
  const sidebarContent = (isMobile = false) => (
    <div className="flex flex-col justify-between h-full bg-[#070c18] border-r border-slate-800/90">
      <div>
        {/* Brand Header */}
        <div className="h-16 px-4 border-b border-slate-800/90 flex items-center justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
              <Satellite className="w-5 h-5" />
            </div>
            {(!collapsed || isMobile) && (
              <div className="min-w-0">
                <div className="text-sm font-bold tracking-wider text-slate-100 truncate">
                  SAT-TRIAGE
                </div>
                <div className="text-[10px] font-mono text-cyan-400/80 truncate">
                  Anomaly Triage Copilot
                </div>
              </div>
            )}
          </div>

          {isMobile ? (
            <button
              type="button"
              onClick={onCloseMobile}
              aria-label="Close navigation menu"
              className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800/70"
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onToggleCollapse}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden lg:inline-flex p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800/70 transition-colors"
            >
              {collapsed ? (
                <ChevronRight className="w-4 h-4" />
              ) : (
                <ChevronLeft className="w-4 h-4" />
              )}
            </button>
          )}
        </div>

        {/* Operations Navigation */}
        <div className="px-2.5 pt-4 space-y-5 overflow-y-auto">
          <div>
            {(!collapsed || isMobile) && (
              <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                Mission Operations
              </div>
            )}
            <nav className="space-y-1">
              {PRIMARY_NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={isMobile ? onCloseMobile : undefined}
                    title={collapsed && !isMobile ? item.label : undefined}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                        isActive
                          ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
                          : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border-transparent"
                      } ${collapsed && !isMobile ? "justify-center px-2" : ""}`
                    }
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    {(!collapsed || isMobile) && <span>{item.label}</span>}
                  </NavLink>
                );
              })}
            </nav>
          </div>

          {/* Coming Soon Modules */}
          <div>
            {(!collapsed || isMobile) && (
              <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-600">
                Upcoming Modules
              </div>
            )}
            <div className="space-y-1">
              {UPCOMING_NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.label}
                    title={`${item.label} (coming soon)`}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs text-slate-500 border border-slate-800/50 bg-slate-900/30 cursor-not-allowed ${
                      collapsed && !isMobile ? "justify-center px-2" : ""
                    }`}
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      <Icon className="w-3.5 h-3.5 shrink-0 text-slate-600" />
                      {(!collapsed || isMobile) && (
                        <span className="truncate">{item.label}</span>
                      )}
                    </span>
                    {(!collapsed || isMobile) && (
                      <span className="inline-flex items-center gap-1 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 shrink-0">
                        <Lock className="w-2.5 h-2.5" />
                        Soon
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Phase 1 Infrastructure Diagnostics */}
          <div>
            {(!collapsed || isMobile) && (
              <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                Infrastructure
              </div>
            )}
            <NavLink
              to="/diagnostics"
              onClick={isMobile ? onCloseMobile : undefined}
              title={collapsed && !isMobile ? "System Diagnostics" : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                  isActive
                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border-transparent"
                } ${collapsed && !isMobile ? "justify-center px-2" : ""}`
              }
            >
              <Terminal className="w-4 h-4 shrink-0" />
              {(!collapsed || isMobile) && <span>System Diagnostics</span>}
            </NavLink>
          </div>
        </div>
      </div>

      {/* Team Footer */}
      <div className="p-3.5 border-t border-slate-800/90 bg-[#050913]">
        <div
          className={`flex items-center gap-2 text-xs font-mono text-slate-300 ${
            collapsed && !isMobile ? "justify-center" : ""
          }`}
        >
          <Cpu className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          {(!collapsed || isMobile) && (
            <span className="truncate">
              {team?.name || "DevCore"} 
            </span>
          )}
        </div>
        {(!collapsed || isMobile) && (
          <div className="mt-1 text-[10px] font-mono text-slate-500 truncate">
            ID: {team?.team_id || "AV26-BF34B6F9D2"}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Fixed Sidebar */}
      <aside
        className={`hidden lg:block shrink-0 transition-all duration-200 ${
          collapsed ? "w-[72px]" : "w-64"
        }`}
      >
        {sidebarContent(false)}
      </aside>

      {/* Mobile Drawer Sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs"
            onClick={onCloseMobile}
          />
          <aside className="relative w-72 max-w-[85vw] h-full z-10">
            {sidebarContent(true)}
          </aside>
        </div>
      )}
    </>
  );
}
