import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import MainLayout from "./components/layout/MainLayout";
import { useSystemHealth } from "./hooks/useSystemHealth";
import { useTelemetryStream } from "./hooks/useTelemetryStream";
import Alerts from "./pages/Alerts";
import Diagnostics from "./pages/Diagnostics";
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
    subtitle: "Anomaly Detection & Threshold Violations (Phase 4)",
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
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/diagnostics" element={<Diagnostics health={health} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </MainLayout>
  );
}
