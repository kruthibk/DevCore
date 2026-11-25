import StatusBadge from "../common/StatusBadge";

export default function MetricCard({
  title,
  icon: Icon,
  value = "—",
  unit,
  statusLabel = "Waiting for telemetry",
  statusVariant = "muted",
  details,
  children,
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 flex flex-col justify-between">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center gap-2 min-w-0">
            {Icon && <Icon className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
            <span className="truncate">{title}</span>
          </span>
          <StatusBadge variant={statusVariant} label={statusLabel} className="shrink-0" />
        </div>

        {children ? (
          <div className="mt-3.5">{children}</div>
        ) : (
          <div className="mt-3.5 flex items-baseline gap-2">
            <span className="text-2xl font-mono font-bold text-slate-200">{value}</span>
            {unit && <span className="text-xs font-mono text-slate-400">{unit}</span>}
          </div>
        )}
      </div>

      {details && (
        <div className="mt-4 pt-2.5 border-t border-slate-800/80 text-[11px] font-mono text-slate-500">
          {details}
        </div>
      )}
    </div>
  );
}
