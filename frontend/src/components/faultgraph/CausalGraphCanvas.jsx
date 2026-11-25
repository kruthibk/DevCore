import { useMemo } from "react";

const SUBSYSTEM_COORDS = {
  "sub:EPS": { x: 110, y: 70 },
  "sub:THERMAL": { x: 110, y: 165 },
  "sub:ADCS": { x: 110, y: 260 },
  "sub:OBC": { x: 110, y: 355 },
  "sub:SENSORS": { x: 110, y: 450 },
};

const SENSOR_COORDS = {
  "sensor:battery_voltage": { x: 430, y: 75 },
  "sensor:temperature": { x: 430, y: 170 },
  "sensor:roll": { x: 430, y: 265 },
  "sensor:pitch": { x: 430, y: 355 },
  "sensor:yaw": { x: 430, y: 445 },
};

function nodeStroke(status, isSelected) {
  if (isSelected) return "#22d3ee";
  if (status === "CRITICAL" || status === "ACTIVE") return "#f43f5e";
  if (status === "WARNING" || status === "ACKNOWLEDGED") return "#f59e0b";
  if (status === "RESOLVED") return "#10b981";
  return "#334155";
}

function nodeFill(nodeType, status) {
  if (status === "CRITICAL" || status === "ACTIVE") return "rgba(244, 63, 94, 0.14)";
  if (status === "WARNING" || status === "ACKNOWLEDGED") return "rgba(245, 158, 11, 0.14)";
  if (nodeType === "subsystem") return "#0b1426";
  if (nodeType === "sensor") return "#091222";
  return "#08101e";
}

export default function CausalGraphCanvas({
  nodes = [],
  edges = [],
  selectedNodeId,
  onSelectNode,
}) {
  const layout = useMemo(() => {
    const positions = { ...SUBSYSTEM_COORDS, ...SENSOR_COORDS };
    const alertNodes = nodes.filter((n) => n.node_type === "alert").slice(0, 8);
    const totalAlerts = alertNodes.length;
    const stepY = totalAlerts > 1 ? Math.min(62, 420 / totalAlerts) : 0;
    const startY = totalAlerts > 0 ? Math.max(55, 255 - ((totalAlerts - 1) * stepY) / 2) : 255;

    alertNodes.forEach((node, idx) => {
      positions[node.id] = {
        x: 755,
        y: startY + idx * stepY,
      };
    });

    const visibleNodes = [
      ...nodes.filter((n) => n.node_type !== "alert"),
      ...alertNodes,
    ];
    const visibleIds = new Set(visibleNodes.map((n) => n.id));
    const visibleEdges = edges.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
    );

    return { positions, visibleNodes, visibleEdges };
  }, [nodes, edges]);

  return (
    <div className="w-full overflow-x-auto rounded border border-slate-800 bg-[#050913]">
      <svg
        viewBox="0 0 900 520"
        className="w-full min-w-[680px] h-[440px] select-none"
        role="img"
        aria-label="Satellite subsystem, sensor, and alert causal fault graph"
      >
        <defs>
          <marker
            id="arrow-muted"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#475569" />
          </marker>
          <marker
            id="arrow-active"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="#22d3ee" />
          </marker>
        </defs>

        {/* Column Headers */}
        <text x="110" y="24" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="monospace">
          SUBSYSTEMS
        </text>
        <text x="430" y="24" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="monospace">
          TELEMETRY SENSORS
        </text>
        <text x="755" y="24" textAnchor="middle" fill="#64748b" fontSize="11" fontFamily="monospace">
          DETECTED ALERTS
        </text>

        {/* Edges */}
        {layout.visibleEdges.map((edge) => {
          const src = layout.positions[edge.source];
          const dst = layout.positions[edge.target];
          if (!src || !dst) return null;

          const isSameCol = Math.abs(src.x - dst.x) < 10;
          const highlighted =
            edge.active ||
            selectedNodeId === edge.source ||
            selectedNodeId === edge.target;

          if (isSameCol) {
            const curveX = src.x - 68 - Math.abs(src.y - dst.y) * 0.12;
            const pathD = `M ${src.x - 75} ${src.y} Q ${curveX} ${(src.y + dst.y) / 2} ${dst.x - 75} ${dst.y}`;
            return (
              <path
                key={edge.id}
                d={pathD}
                fill="none"
                stroke={highlighted ? "#22d3ee" : "#1e293b"}
                strokeWidth={highlighted ? 1.8 : 1.1}
                strokeDasharray={highlighted ? undefined : "3 3"}
                markerEnd={highlighted ? "url(#arrow-active)" : "url(#arrow-muted)"}
                opacity={highlighted ? 0.95 : 0.7}
              />
            );
          }

          const x1 = src.x > dst.x ? src.x - 82 : src.x + 82;
          const x2 = src.x > dst.x ? dst.x + 82 : dst.x - 82;
          const midX = (x1 + x2) / 2;

          return (
            <g key={edge.id}>
              <line
                x1={x1}
                y1={src.y}
                x2={x2}
                y2={dst.y}
                stroke={highlighted ? "#22d3ee" : "#1e293b"}
                strokeWidth={highlighted ? 1.8 : 1.1}
                markerEnd={highlighted ? "url(#arrow-active)" : "url(#arrow-muted)"}
                opacity={highlighted ? 0.95 : 0.65}
              />
              {highlighted && (
                <text
                  x={midX}
                  y={(src.y + dst.y) / 2 - 4}
                  textAnchor="middle"
                  fill="#67e8f9"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  {edge.relationship}
                </text>
              )}
            </g>
          );
        })}

        {/* Nodes */}
        {layout.visibleNodes.map((node) => {
          const pos = layout.positions[node.id];
          if (!pos) return null;
          const isSelected = selectedNodeId === node.id;
          const width = node.node_type === "alert" ? 180 : 164;
          const height = node.node_type === "alert" ? 44 : 48;

          const shortLabel =
            node.node_type === "subsystem"
              ? `${node.metadata?.short_id || node.subsystem} — ${node.label}`
              : node.node_type === "alert"
              ? `${node.label}`
              : node.label;

          return (
            <g
              key={node.id}
              transform={`translate(${pos.x - width / 2}, ${pos.y - height / 2})`}
              onClick={() => onSelectNode(node)}
              className="cursor-pointer"
            >
              <rect
                width={width}
                height={height}
                rx="6"
                fill={nodeFill(node.node_type, node.status)}
                stroke={nodeStroke(node.status, isSelected)}
                strokeWidth={isSelected ? 2 : 1.2}
              />
              <text
                x={10}
                y={19}
                fill="#e2e8f0"
                fontSize="11"
                fontWeight="600"
                fontFamily="monospace"
              >
                {shortLabel.length > 22 ? `${shortLabel.slice(0, 21)}…` : shortLabel}
              </text>
              <text
                x={10}
                y={34}
                fill={
                  node.status === "CRITICAL" || node.status === "ACTIVE"
                    ? "#fda4af"
                    : node.status === "WARNING" || node.status === "ACKNOWLEDGED"
                    ? "#fcd34d"
                    : "#94a3b8"
                }
                fontSize="9.5"
                fontFamily="monospace"
              >
                {node.node_type === "alert"
                  ? `${node.metadata?.sensor_name} // ${node.status}`
                  : `STATUS: ${node.status}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
