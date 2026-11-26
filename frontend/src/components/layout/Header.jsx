import { useEffect, useState } from "react";
import { KeyRound, LogOut, Menu, RefreshCw, Shield, UserCircle2, UserPlus } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import StatusBadge from "../common/StatusBadge";

function formatUtcTimestamp(date) {
  return date.toISOString().replace("T", " ").slice(0, 19) + " UTC";
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
  const { isAuthenticated, username, role, isAdmin, logout } = useAuth();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

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
        {isAuthenticated && (
          <>
            <StatusBadge variant={socketVariant} label={socketLabel} />
            <StatusBadge
              variant={simulatorRunning ? "standby" : "muted"}
              label={simulatorRunning ? "SIM: RUNNING" : "SIM: STANDBY"}
            />
          </>
        )}

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

        {/* Authenticated User Session / Login Links */}
        <div className="flex items-center gap-2 pl-2.5 border-l border-slate-800">
          {isAuthenticated ? (
            <>
              <Link
                to="/profile"
                className="flex items-center gap-1.5 px-2 py-1 rounded border border-slate-800 bg-[#050913] hover:border-cyan-500/40 text-[11px] font-mono text-slate-200"
                title="View account profile & permissions"
              >
                {isAdmin ? (
                  <Shield className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                ) : (
                  <UserCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                )}
                <span className="max-w-[100px] truncate">{username}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                    isAdmin
                      ? "bg-rose-500/20 text-rose-200"
                      : "bg-cyan-500/20 text-cyan-200"
                  }`}
                >
                  {role}
                </span>
              </Link>
              <button
                type="button"
                onClick={logout}
                title="Sign out and revoke JWT session"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-rose-500/35 bg-rose-500/10 hover:bg-rose-500/20 text-[11px] font-mono text-rose-200"
              >
                <LogOut className="w-3 h-3" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-cyan-500/40 bg-cyan-500/15 hover:bg-cyan-500/25 text-[11px] font-mono text-cyan-100"
              >
                <KeyRound className="w-3 h-3" />
                <span>Sign In</span>
              </Link>
              <Link
                to="/register"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-[11px] font-mono text-slate-200"
              >
                <UserPlus className="w-3 h-3" />
                <span className="hidden sm:inline">Register</span>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
