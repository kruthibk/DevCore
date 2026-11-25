import { useEffect, useState } from "react";
import { Menu, RefreshCw, UserCircle2 } from "lucide-react";
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
  isPolling,
  onManualRefresh,
  onOpenMobileMenu,
}) {
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

      <div className="flex items-center gap-2 sm:gap-2.5 flex-wrap">
        <StatusBadge variant={systemState} label={systemLabel} />
        <StatusBadge variant={backendState} label={apiLabel} />
        <StatusBadge variant={dbState} label={dbLabel} />

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

        {/* Operator Profile Placeholder */}
        <div
          className="hidden md:flex items-center gap-2 pl-2.5 border-l border-slate-800"
          title="Operator authentication will be enabled in a future phase"
        >
          <UserCircle2 className="w-5 h-5 text-slate-400" />
          <div className="leading-tight">
            <div className="text-[11px] font-medium text-slate-200">Flight Ops</div>
            <div className="text-[10px] font-mono text-slate-500">Operator // Standby</div>
          </div>
        </div>
      </div>
    </header>
  );
}
