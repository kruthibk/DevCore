import { AlertOctagon, RefreshCw } from "lucide-react";

export default function ErrorState({
  title = "System Connectivity Issue",
  message,
  details,
  onRetry,
  severity = "error",
}) {
  const isWarning = severity === "warning";
  const containerClass = isWarning
    ? "border-amber-500/30 bg-amber-500/10 text-amber-200"
    : "border-rose-500/30 bg-rose-500/10 text-rose-200";
  const iconClass = isWarning ? "text-amber-400" : "text-rose-400";

  return (
    <div className={`rounded-lg border p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${containerClass}`}>
      <div className="flex items-start gap-3">
        <AlertOctagon className={`w-5 h-5 mt-0.5 shrink-0 ${iconClass}`} />
        <div>
          <div className="text-sm font-semibold">{title}</div>
          {message && <div className="text-xs font-mono mt-0.5 opacity-90">{message}</div>}
          {details && <div className="text-[11px] font-mono mt-1 opacity-75">{details}</div>}
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-current/25 bg-black/20 hover:bg-black/35 text-xs font-mono shrink-0 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Probe</span>
        </button>
      )}
    </div>
  );
}
