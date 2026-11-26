import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import MainLayout from "./components/layout/MainLayout";
import { useSystemHealth } from "./hooks/useSystemHealth";
import { useTelemetryStream } from "./hooks/useTelemetryStream";
import Alerts from "./pages/Alerts";
import AICopilot from "./pages/AICopilot";
import Diagnostics from "./pages/Diagnostics";
import FaultGraph from "./pages/FaultGraph";
import Incidents from "./pages/Incidents";
import Overview from "./pages/Overview";
import Telemetry from "./pages/Telemetry";

const PAGE_META = {
  "/": {
    title: "Mission Control Overview",
    subtitle: "SAT-01 Operations Shell // Live Synthetic Telemetry & System Health",
  },
  "/telemetry": {
    title: "Telemetry Console",
    subtitle: "Spacecraft Power, Thermal & Attitude Live Socket.IO Channels",
  },
  "/alerts": {
    title: "Alerts Queue",
    subtitle: "Persisted Statistical Anomaly & Sensor Integrity Findings",
  },
  "/fault-graph": {
    title: "Hybrid Causal Fault Graph",
    subtitle: "Subsystem Dependencies, Alert Correlation & Root-Cause Hypotheses",
  },
  "/copilot": {
    title: "Evidence-Linked AI Copilot",
    subtitle: "Runbook RAG Retrieval & Grounded Investigative Triage Guidance",
  },
  "/incidents": {
    title: "Incident Management",
    subtitle: "Triage Registry & Operator Review (Scheduled Later Phase)",
  },
  "/diagnostics": {
    title: "System Diagnostics",
    subtitle: "Live Backend API & PostgreSQL Health Verification",
  },
};

export default function App() {
  const health = useSystemHealth();
  const stream = useTelemetryStream();
  const location = useLocation();
  const meta = PAGE_META[location.pathname] || PAGE_META["/"];

  return (
    <MainLayout title={meta.title} subtitle={meta.subtitle} health={health} stream={stream}>
      <Routes>
        <Route path="/" element={<Overview health={health} stream={stream} />} />
        <Route path="/telemetry" element={<Telemetry health={health} stream={stream} />} />
        <Route path="/alerts" element={<Alerts stream={stream} />} />
        <Route path="/fault-graph" element={<FaultGraph stream={stream} />} />
        <Route path="/copilot" element={<AICopilot stream={stream} />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/diagnostics" element={<Diagnostics health={health} stream={stream} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </MainLayout>
  );
}
