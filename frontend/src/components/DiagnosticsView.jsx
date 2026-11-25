function PayloadPanel({ title, endpoint, result }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#0b1222]/90 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-800/80 flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-slate-200">{title}</div>
          <div className="text-[11px] font-mono text-cyan-400">GET {endpoint}</div>
        </div>
        <div className="text-xs font-mono text-slate-400">
          Status:{" "}
          <span className={result?.ok ? "text-emerald-400" : "text-rose-400"}>
            {result?.statusCode ?? "ERR"}
          </span>{" "}
          // {result ? `${result.latencyMs}ms` : "—"}
        </div>
      </div>
      <pre className="p-4 text-xs font-mono text-slate-300 overflow-x-auto max-h-60 bg-[#060a14]">
        {result
          ? JSON.stringify(result.data || { error: result.error }, null, 2)
          : "Pending..."}
      </pre>
    </div>
  );
}

export default function DiagnosticsView({ serviceHealth, dbHealth, systemInfo }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-slate-100">
          Live Endpoint Diagnostics
        </h2>
        <p className="text-xs text-slate-400">
          Raw JSON responses directly observed from FastAPI and PostgreSQL health probes.
        </p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <PayloadPanel title="Service Health" endpoint="/health" result={serviceHealth} />
        <PayloadPanel title="Database Health" endpoint="/health/db" result={dbHealth} />
        <PayloadPanel title="System Info" endpoint="/api/v1/info" result={systemInfo} />
      </div>
    </div>
  );
}
