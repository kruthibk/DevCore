import { Radio } from "lucide-react";

export default function EmptyState({
  icon: Icon = Radio,
  title,
  description,
  phaseBadge,
  compact = false,
}) {
  return (
    <div
      className={`rounded-lg border border-dashed border-slate-700/80 bg-[#060b16]/80 flex flex-col items-center justify-center text-center ${
        compact ? "p-5" : "p-8"
      }`}
    >
      <div className="w-9 h-9 rounded-lg border border-slate-700 bg-slate-900/80 flex items-center justify-center text-cyan-400/80 mb-3">
        <Icon className="w-4 h-4" />
      </div>
      <div className="text-sm font-medium text-slate-200">{title}</div>
      {description && (
        <p className="text-xs text-slate-400 max-w-md mt-1 leading-relaxed">{description}</p>
      )}
      {phaseBadge && (
        <span className="mt-3 px-2 py-0.5 rounded border border-cyan-500/25 bg-cyan-500/10 text-[10px] font-mono uppercase tracking-wider text-cyan-300">
          {phaseBadge}
        </span>
      )}
    </div>
  );
}
