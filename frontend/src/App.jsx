import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import ErrorState from "./components/common/ErrorState";
import LoadingState from "./components/common/LoadingState";
import MainLayout from "./components/layout/MainLayout";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { useSystemHealth } from "./hooks/useSystemHealth";
import { useTelemetryStream } from "./hooks/useTelemetryStream";
import AdminUsers from "./pages/AdminUsers";
import Alerts from "./pages/Alerts";
import AICopilot from "./pages/AICopilot";
import Diagnostics from "./pages/Diagnostics";
import FaultGraph from "./pages/FaultGraph";
import Incidents from "./pages/Incidents";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Profile from "./pages/Profile";
import Register from "./pages/Register";
import Telemetry from "./pages/Telemetry";
import VerificationWall from "./pages/VerificationWall";

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
  "/verification": {
    title: "Verification Wall & Human Approval",
    subtitle: "Deterministic 10-Rule Safety Gate & Operator Sign-Off Audit Trail",
  },
  "/incidents": {
    title: "Incident Management & Audit Trail",
    subtitle: "PostgreSQL Incident Lifecycle, Triage Promotion & Immutable Operator Audit Logs",
  },
  "/admin": {
    title: "Administrator Console",
    subtitle: "RBAC Role Management, Account Activation & System Audit Counters",
  },
  "/profile": {
    title: "Operator Profile & Permissions",
    subtitle: "Authenticated Session Metadata & Role Access Matrix",
  },
  "/login": {
    title: "Operator Sign In",
    subtitle: "JWT Authentication Required for Operations & Verification Wall",
  },
  "/register": {
    title: "Operator Registration",
    subtitle: "Provision a New Authenticated OPERATOR Account",
  },
  "/diagnostics": {
    title: "System Diagnostics",
    subtitle: "Live Backend API & PostgreSQL Health Verification",
  },
};

function RequireAuth({ children }) {
  const { isAuthenticated, authLoading } = useAuth();
  const location = useLocation();

  if (authLoading) {
    return <LoadingState label="Verifying authenticated JWT session..." />;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />;
  }
  return children;
}

function RequireAdmin({ children }) {
  const { isAuthenticated, authLoading, isAdmin } = useAuth();
  const location = useLocation();

  if (authLoading) {
    return <LoadingState label="Verifying administrator privileges..." />;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />;
  }
  if (!isAdmin) {
    return (
      <ErrorState
        title="403 — Administrator Role Required"
        message="Access denied. Only ADMIN accounts may manage users, roles, and system-level audits."
      />
    );
  }
  return children;
}

function AppShell() {
  const { isAuthenticated, token } = useAuth();
  const health = useSystemHealth();
  const stream = useTelemetryStream(isAuthenticated, token);
  const location = useLocation();
  const meta = PAGE_META[location.pathname] || PAGE_META["/"];

  return (
    <MainLayout title={meta.title} subtitle={meta.subtitle} health={health} stream={stream}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/diagnostics" element={<Diagnostics health={health} stream={stream} />} />

        <Route
          path="/"
          element={
            <RequireAuth>
              <Overview health={health} stream={stream} />
            </RequireAuth>
          }
        />
        <Route
          path="/telemetry"
          element={
            <RequireAuth>
              <Telemetry health={health} stream={stream} />
            </RequireAuth>
          }
        />
        <Route
          path="/alerts"
          element={
            <RequireAuth>
              <Alerts stream={stream} />
            </RequireAuth>
          }
        />
        <Route
          path="/fault-graph"
          element={
            <RequireAuth>
              <FaultGraph stream={stream} />
            </RequireAuth>
          }
        />
        <Route
          path="/copilot"
          element={
            <RequireAuth>
              <AICopilot stream={stream} />
            </RequireAuth>
          }
        />
        <Route
          path="/verification"
          element={
            <RequireAuth>
              <VerificationWall />
            </RequireAuth>
          }
        />
        <Route
          path="/incidents"
          element={
            <RequireAuth>
              <Incidents stream={stream} />
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <Profile />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAdmin>
              <AdminUsers />
            </RequireAdmin>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </MainLayout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
