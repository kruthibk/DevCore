import { useEffect, useState } from "react";
import { KeyRound, LogOut, Menu, RefreshCw, Shield, UserCircle2, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import StatusBadge from "../common/StatusBadge";

const ROLES = ["ADMIN", "OPERATOR", "VIEWER"];

function formatUtcTimestamp(date) {
  return date.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

function roleButtonStyle(itemRole, activeRole) {
  if (itemRole !== activeRole) {
    return "text-slate-400 hover:text-slate-100 hover:bg-slate-800/70";
  }
  if (itemRole === "ADMIN") {
    return "bg-rose-500/20 text-rose-200 border border-rose-500/40";
  }
  if (itemRole === "OPERATOR") {
    return "bg-cyan-500/20 text-cyan-200 border border-cyan-500/40";
  }
  return "bg-amber-500/20 text-amber-200 border border-amber-500/40";
}

export default function Header({
  title,
  subtitle,
  systemState,
  backendState,
  dbState,
  socketStatus,
  simulatorRunning,
  isPolling,
  onManualRefresh,
  onOpenMobileMenu,
}) {
  const { role, username, authMode, switchDemoRole, login, logout } = useAuth();
  const [now, setNow] = useState(() => new Date());
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginUsername, setLoginUsername] = useState("admin");
  const [loginPassword, setLoginPassword] = useState("AdminPass!2026");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState(null);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoginBusy(true);
    setLoginError(null);
    const res = await login(loginUsername.trim(), loginPassword);
    setLoginBusy(false);
    if (res.ok) {
      setLoginOpen(false);
    } else {
      setLoginError(res.error || "Authentication failed");
    }
  };

  const systemLabel =
    systemState === "online"
      ? "SYS: NOMINAL"
      : systemState === "degraded"
      ? "SYS: DEGRADED"
      : systemState === "offline"
      ? "SYS: OFFLINE"
      : "SYS: PROBING";

  const apiLabel =
    backendState === "online"
      ? "API: ONLINE"
      : backendState === "offline"
      ? "API: OFFLINE"
      : "API: PROBING";

  const dbLabel =
    dbState === "online"
      ? "PGSQL: ONLINE"
      : dbState === "offline"
      ? "PGSQL: OFFLINE"
      : "PGSQL: PROBING";

  const socketVariant =
    socketStatus === "connected"
      ? "online"
      : socketStatus === "connecting"
      ? "checking"
      : "offline";

  const socketLabel =
    socketStatus === "connected"
      ? "SIO: LIVE"
      : socketStatus === "connecting"
      ? "SIO: CONNECTING"
      : "SIO: OFFLINE";

  return (
    <>
      <header className="min-h-16 px-4 sm:px-6 py-2.5 border-b border-slate-800/90 bg-[#070c18]/95 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onOpenMobileMenu}
            aria-label="Open navigation menu"
            className="lg:hidden p-2 rounded-lg border border-slate-800 bg-slate-900/70 text-slate-300 hover:text-white"
          >
            <Menu className="w-4 h-4" />
          </button>
          <div className="min-w-0">
            <h1 className="text-base sm:text-lg font-semibold text-slate-100 truncate">
              {title}
            </h1>
            {subtitle && (
              <p className="text-[11px] font-mono text-slate-400 truncate">{subtitle}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge variant={systemState} label={systemLabel} />
          <StatusBadge variant={backendState} label={apiLabel} />
          <StatusBadge variant={dbState} label={dbLabel} />
          <StatusBadge variant={socketVariant} label={socketLabel} />
          <StatusBadge
            variant={simulatorRunning ? "standby" : "muted"}
            label={simulatorRunning ? "SIM: RUNNING" : "SIM: STANDBY"}
          />

          <div className="hidden xl:block px-2.5 py-1 rounded border border-slate-800 bg-[#050913] text-[11px] font-mono text-slate-300">
            {formatUtcTimestamp(now)}
          </div>

          <button
            type="button"
            onClick={onManualRefresh}
            disabled={isPolling}
            title="Probe backend and PostgreSQL health"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 text-[11px] font-mono disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${isPolling ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Probe</span>
          </button>

          {/* RBAC Role Switcher & Session Control */}
          <div className="flex items-center gap-2 pl-2.5 border-l border-slate-800">
            <div
              className="inline-flex items-center rounded border border-slate-800 bg-[#050913] p-0.5 text-[10px] font-mono"
              role="group"
              aria-label="Demo RBAC Role Switcher"
            >
              {ROLES.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => switchDemoRole(r)}
                  className={`px-2 py-0.5 rounded transition-colors ${roleButtonStyle(r, role)}`}
                  title={`Switch active RBAC role to ${r}`}
                >
                  {r}
                </button>
              ))}
            </div>

            <div className="hidden md:flex items-center gap-1.5 text-[11px] font-mono text-slate-300">
              <UserCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />
              <span className="max-w-[110px] truncate" title={`${username} (${authMode})`}>
                {username}
              </span>
            </div>

            {authMode === "bearer" ? (
              <button
                type="button"
                onClick={logout}
                title="Sign out of JWT session"
                className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-[10px] font-mono text-slate-200"
              >
                <LogOut className="w-3 h-3" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setLoginOpen(true)}
                title="Sign in with PostgreSQL user credentials"
                className="inline-flex items-center gap-1 px-2 py-1 rounded border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-[10px] font-mono text-slate-200"
              >
                <KeyRound className="w-3 h-3" />
                <span className="hidden sm:inline">Login</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Optional PostgreSQL User Login Modal */}
      {loginOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-lg border border-slate-700 bg-[#090f1e] p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <Shield className="w-4 h-4 text-cyan-400" />
                <span>SAT-TRIAGE RBAC Sign In</span>
              </div>
              <button
                type="button"
                onClick={() => setLoginOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="rounded border border-slate-800 bg-[#050913] p-3 text-[11px] font-mono text-slate-400 space-y-1">
              <div className="text-slate-300 font-semibold">Seeded Demo Accounts:</div>
              <div>admin / AdminPass!2026 (ADMIN)</div>
              <div>operator / OperatorPass!2026 (OPERATOR)</div>
              <div>viewer / ViewerPass!2026 (VIEWER)</div>
            </div>

            {loginError && (
              <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                {loginError}
              </div>
            )}

            <form onSubmit={handleLoginSubmit} className="space-y-3">
              <div>
                <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                  Username
                </label>
                <input
                  type="text"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  required
                  className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-xs text-slate-100"
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                  className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-xs text-slate-100"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setLoginOpen(false)}
                  className="px-3 py-1.5 rounded border border-slate-700 text-xs font-mono text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loginBusy}
                  className="px-4 py-1.5 rounded border border-cyan-500/50 bg-cyan-500/20 hover:bg-cyan-500/30 text-xs font-mono font-semibold text-cyan-100 disabled:opacity-50"
                >
                  {loginBusy ? "Signing In..." : "Sign In"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
