import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function LatencyChart({ history }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#0b1222]/90 p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">
            Live Health Probe Latency
          </h2>
          <p className="text-xs text-slate-400">
            Measured round-trip latency from actual GET /health and GET /health/db responses
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span className="flex items-center gap-1.5 text-cyan-300">
            <span className="w-2.5 h-2.5 rounded-sm bg-cyan-400" />
            API (/health)
          </span>
          <span className="flex items-center gap-1.5 text-emerald-300">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400" />
            DB (/health/db)
          </span>
        </div>
      </div>

      <div className="h-64 w-full">
        {history.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs font-mono text-slate-500 border border-dashed border-slate-800 rounded-lg">
            Awaiting initial health probe...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={history} margin={{ top: 10, right: 12, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="apiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="dbGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="time"
                stroke="#64748b"
                tick={{ fontSize: 11, fontFamily: "monospace" }}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 11, fontFamily: "monospace" }}
                unit="ms"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0a101f",
                  borderColor: "#1e2d4d",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontFamily: "monospace",
                }}
              />
              <Area
                type="monotone"
                dataKey="apiLatencyMs"
                name="API Latency (ms)"
                stroke="#22d3ee"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#apiGrad)"
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="dbLatencyMs"
                name="DB Query (ms)"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#dbGrad)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
