import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import EmptyState from "../common/EmptyState";

export default function TelemetryChart({
  title,
  subtitle,
  unit,
  data = [],
  series = [],
  emptyTitle = "Waiting for telemetry",
  emptyDescription = "Start the synthetic telemetry simulator to stream live readings into this chart.",
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        {unit && (
          <span className="px-2 py-0.5 rounded border border-slate-800 bg-[#050913] text-[10px] font-mono text-slate-400">
            {unit}
          </span>
        )}
      </div>

      <div className="h-56 w-full">
        {data.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <EmptyState
              title={emptyTitle}
              description={emptyDescription}
              phaseBadge="SYNTHETIC SIMULATION STREAM"
              compact
            />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1b2942" />
              <XAxis
                dataKey="timestamp"
                stroke="#64748b"
                tick={{ fontSize: 11, fontFamily: "monospace" }}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 11, fontFamily: "monospace" }}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#060b16",
                  borderColor: "#1b2942",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontFamily: "monospace",
                }}
              />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: "11px" }} />}
              {series.map((s) => (
                <Line
                  key={s.dataKey}
                  type="monotone"
                  dataKey={s.dataKey}
                  name={s.name}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
