import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

function StatusPill({ label, state }) {
  const styles = {
    healthy: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    unhealthy: "border-rose-500/30 bg-rose-500/10 text-rose-300",
    checking: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  };
  const dotStyles = {
    healthy: "bg-emerald-400",
    unhealthy: "bg-rose-400",
    checking: "bg-amber-400 animate-pulse",
  };
  const text = {
    healthy: "ONLINE",
    unhealthy: "OFFLINE",
    checking: "PROBING",
  };

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full border text-xs font-mono ${
        styles[state] || styles.checking
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${dotStyles[state] || dotStyles.checking}`} />
      <span className="text-slate-400">{label}:</span>
      <span className="font-semibold">{text[state] || "UNKNOWN"}</span>
    </div>
  );
}

export default function Header({
  backendState,
  dbState,
  environment,
  isPolling,
  autoPoll,
  onToggleAutoPoll,
  onManualRefresh,
}) {
  const [utcClock, setUtcClock] = useState(() => new Date().toISOString().slice(11, 19));

  useEffect(() => {
    const timer = setInterval(() => {
      setUtcClock(new Date().toISOString().slice(11, 19));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-16 px-6 border-b border-slate-800/80 bg-[#070b16]/90 backdrop-blur flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
          {environment || "UNVERIFIED"}
        </span>
        <div className="text-xs font-mono text-slate-400">
          MISSION UTC <span className="text-slate-200 font-semibold">{utcClock}Z</span>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <StatusPill label="API" state={backendState} />
        <StatusPill label="PGSQL" state={dbState} />

        <button
          type="button"
          onClick={onToggleAutoPoll}
          className={`px-2.5 py-1 rounded-lg border text-xs font-mono transition-colors ${
            autoPoll
              ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300"
              : "border-slate-700 bg-slate-800/60 text-slate-400"
          }`}
        >
          AUTO-POLL: {autoPoll ? "ON (10s)" : "PAUSED"}
        </button>

        <button
          type="button"
          onClick={onManualRefresh}
          disabled={isPolling}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/30 text-cyan-300 text-xs font-mono disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isPolling ? "animate-spin" : ""}`} />
          <span>Probe Now</span>
        </button>
      </div>
    </header>
  );
}
