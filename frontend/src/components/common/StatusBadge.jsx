const VARIANT_CLASSES = {
  online: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  healthy: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  nominal: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  standby: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
  info: "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",
  checking: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  degraded: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  offline: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  critical: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  muted: "border-slate-700 bg-slate-800/70 text-slate-400",
};

const DOT_CLASSES = {
  online: "bg-emerald-400",
  healthy: "bg-emerald-400",
  nominal: "bg-emerald-400",
  standby: "bg-cyan-400",
  info: "bg-cyan-400",
  checking: "bg-amber-400 animate-pulse",
  degraded: "bg-amber-400",
  warning: "bg-amber-400",
  offline: "bg-rose-400",
  critical: "bg-rose-400",
  muted: "bg-slate-500",
};

export default function StatusBadge({
  variant = "muted",
  label,
  showDot = true,
  className = "",
}) {
  const style = VARIANT_CLASSES[variant] || VARIANT_CLASSES.muted;
  const dotStyle = DOT_CLASSES[variant] || DOT_CLASSES.muted;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded border text-[11px] font-mono uppercase tracking-wide ${style} ${className}`}
    >
      {showDot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotStyle}`} />}
      <span>{label}</span>
    </span>
  );
}
