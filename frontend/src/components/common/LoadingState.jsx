import { Loader2 } from "lucide-react";

export default function LoadingState({
  title = "Probing mission-control systems...",
  subtitle = "Contacting FastAPI backend and PostgreSQL health endpoints.",
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex items-center gap-3.5">
      <Loader2 className="w-5 h-5 text-cyan-400 animate-spin shrink-0" />
      <div>
        <div className="text-sm font-medium text-slate-200">{title}</div>
        <div className="text-xs font-mono text-slate-400 mt-0.5">{subtitle}</div>
      </div>
    </div>
  );
}
