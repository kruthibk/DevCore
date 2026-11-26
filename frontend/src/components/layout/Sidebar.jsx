import {
  Activity,
  AlertTriangle,
  Bot,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileCheck2,
  GitBranch,
  KeyRound,
  Radio,
  Satellite,
  Shield,
  ShieldCheck,
  Terminal,
  UserCircle2,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const AUTHENTICATED_NAV = [
  { to: "/", label: "Overview", icon: Activity, end: true },
  { to: "/telemetry", label: "Telemetry", icon: Radio },
  { to: "/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/fault-graph", label: "Fault Graph", icon: GitBranch },
  { to: "/copilot", label: "AI Copilot", icon: Bot },
  { to: "/verification", label: "Verification", icon: ShieldCheck },
  { to: "/incidents", label: "Incidents", icon: FileCheck2 },
];

const PUBLIC_NAV = [
  { to: "/login", label: "Sign In", icon: KeyRound },
  { to: "/register", label: "Register", icon: UserPlus },
];

export default function Sidebar({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  team,
}) {
  const { isAuthenticated, isAdmin } = useAuth();
  const navItems = isAuthenticated ? AUTHENTICATED_NAV : PUBLIC_NAV;

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

        {/* Navigation */}
        <div className="px-2.5 pt-4 space-y-5 overflow-y-auto">
          <div>
            {(!collapsed || isMobile) && (
              <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                {isAuthenticated ? "Mission Operations" : "Authentication"}
              </div>
            )}
            <nav className="space-y-1">
              {navItems.map((item) => {
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

          {/* Role-Based Admin Section */}
          {isAuthenticated && isAdmin && (
            <div>
              {(!collapsed || isMobile) && (
                <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-rose-400/80">
                  Administration
                </div>
              )}
              <NavLink
                to="/admin"
                onClick={isMobile ? onCloseMobile : undefined}
                title={collapsed && !isMobile ? "Admin & Users" : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                    isActive
                      ? "bg-rose-500/15 text-rose-200 border-rose-500/30"
                      : "text-slate-300 hover:text-slate-100 hover:bg-slate-800/60 border-transparent"
                  } ${collapsed && !isMobile ? "justify-center px-2" : ""}`
                }
              >
                <Users className="w-4 h-4 shrink-0 text-rose-400" />
                {(!collapsed || isMobile) && <span>Admin &amp; Users</span>}
              </NavLink>
            </div>
          )}

          {/* Account & Infrastructure */}
          <div>
            {(!collapsed || isMobile) && (
              <div className="px-2.5 pb-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
                Account &amp; System
              </div>
            )}
            <div className="space-y-1">
              {isAuthenticated && (
                <NavLink
                  to="/profile"
                  onClick={isMobile ? onCloseMobile : undefined}
                  title={collapsed && !isMobile ? "Operator Profile" : undefined}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium border transition-colors ${
                      isActive
                        ? "bg-cyan-500/10 text-cyan-300 border-cyan-500/30"
                        : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border-transparent"
                    } ${collapsed && !isMobile ? "justify-center px-2" : ""}`
                  }
                >
                  {isAdmin ? (
                    <Shield className="w-4 h-4 shrink-0 text-rose-400" />
                  ) : (
                    <UserCircle2 className="w-4 h-4 shrink-0" />
                  )}
                  {(!collapsed || isMobile) && <span>Profile &amp; Role</span>}
                </NavLink>
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
            <span className="truncate">{team?.name || "DevCore"}</span>
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
      <aside
        className={`hidden lg:block shrink-0 transition-all duration-200 ${
          collapsed ? "w-[72px]" : "w-64"
        }`}
      >
        {sidebarContent(false)}
      </aside>

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
