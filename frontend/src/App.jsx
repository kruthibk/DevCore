import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import MainLayout from "./components/layout/MainLayout";
import { useSystemHealth } from "./hooks/useSystemHealth";
import Alerts from "./pages/Alerts";
import Diagnostics from "./pages/Diagnostics";
import Incidents from "./pages/Incidents";
import Overview from "./pages/Overview";
import Telemetry from "./pages/Telemetry";

const PAGE_META = {
  "/": {
    title: "Mission Control Overview",
    subtitle: "SAT-01 Operations Shell // Infrastructure & Subsystem Readiness",
  },
  "/telemetry": {
    title: "Telemetry Console",
    subtitle: "Spacecraft Power, Thermal & Attitude Channels",
  },
  "/alerts": {
    title: "Alerts Queue",
    subtitle: "Anomaly Detection & Threshold Violations",
  },
  "/incidents": {
    title: "Incident Management",
    subtitle: "Triage Registry & Operator Review",
  },
  "/diagnostics": {
    title: "System Diagnostics",
    subtitle: "Live Backend API & PostgreSQL Health Verification",
  },
};

export default function App() {
  const health = useSystemHealth();
  const location = useLocation();
  const meta = PAGE_META[location.pathname] || PAGE_META["/"];

  return (
    <MainLayout title={meta.title} subtitle={meta.subtitle} health={health}>
      <Routes>
        <Route path="/" element={<Overview health={health} />} />
        <Route path="/telemetry" element={<Telemetry />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/diagnostics" element={<Diagnostics health={health} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </MainLayout>
  );
}
