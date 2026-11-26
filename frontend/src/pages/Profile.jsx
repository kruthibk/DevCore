import { LogOut, RefreshCw, Shield, UserCircle2 } from "lucide-react";
import StatusBadge from "../components/common/StatusBadge";
import { useAuth } from "../context/AuthContext";

const ROLE_CAPABILITIES = {
  OPERATOR: [
    "View synthetic telemetry, alerts, correlations, and incident history",
    "Query AI Copilot and submit recommendations to the Verification Wall",
    "Approve, reject, or request investigation on Verification Wall items",
    "Acknowledge/resolve alerts and create or update incidents",
  ],
  ADMIN: [
    "All OPERATOR permissions",
    "Manage user accounts (activate/deactivate) and assign roles",
    "Control telemetry simulator fault injection and rebuild FAISS index",
    "Inspect system-level audit metrics and revoked sessions",
  ],
};

export default function Profile() {
  const { user, role, isAdmin, logout, refreshProfile } = useAuth();

  if (!user) return null;

  const caps = ROLE_CAPABILITIES[role] || ROLE_CAPABILITIES.OPERATOR;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-lg border border-cyan-500/30 bg-cyan-500/10 flex items-center justify-center text-cyan-400">
            <UserCircle2 className="w-6 h-6" />
          </div>
          <div>
            <div className="text-base font-semibold text-slate-100">{user.username}</div>
            <div className="text-xs font-mono text-slate-400">{user.email}</div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge variant={isAdmin ? "critical" : "standby"} label={`ROLE: ${role}`} />
          <StatusBadge
            variant={user.is_active ? "nominal" : "critical"}
            label={user.is_active ? "ACTIVE" : "INACTIVE"}
          />
          <button
            type="button"
            onClick={refreshProfile}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Sync</span>
          </button>
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded border border-rose-500/40 bg-rose-500/15 hover:bg-rose-500/25 text-xs font-mono text-rose-200"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-4">
        <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-slate-300 border-b border-slate-800 pb-3">
          <Shield className="w-4 h-4 text-cyan-400" />
          <span>Account Details &amp; Enforced Backend Permissions</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
          <div className="rounded border border-slate-800 bg-[#050913] p-3">
            <div className="text-[10px] text-slate-500 uppercase">User ID</div>
            <div className="text-slate-100 mt-1">#{user.id}</div>
          </div>
          <div className="rounded border border-slate-800 bg-[#050913] p-3">
            <div className="text-[10px] text-slate-500 uppercase">Authentication</div>
            <div className="text-emerald-300 mt-1">Bearer JWT (HS256)</div>
          </div>
          <div className="rounded border border-slate-800 bg-[#050913] p-3">
            <div className="text-[10px] text-slate-500 uppercase">Created At</div>
            <div className="text-slate-200 mt-1">
              {new Date(user.created_at).toISOString().replace("T", " ").slice(0, 19)} UTC
            </div>
          </div>
        </div>

        <div>
          <div className="text-[11px] font-mono uppercase text-cyan-300 mb-2">
            Granted Permissions ({role})
          </div>
          <ul className="space-y-1.5 text-xs text-slate-300 list-disc pl-5">
            {caps.map((cap) => (
              <li key={cap}>{cap}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
