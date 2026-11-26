import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Shield, UserCheck, UserX } from "lucide-react";
import {
  fetchAdminUsers,
  updateAdminUserRole,
  updateAdminUserStatus,
} from "../api/client";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import StatusBadge from "../components/common/StatusBadge";
import { useAuth } from "../context/AuthContext";

export default function AdminUsers() {
  const { user: currentUser, isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    const res = await fetchAdminUsers();
    if (res.ok && res.data) {
      setData(res.data);
      setError(null);
    } else {
      setError(res.error || "Unable to load admin user directory.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (isAdmin) {
      loadUsers();
    } else {
      setLoading(false);
    }
  }, [isAdmin, loadUsers]);

  if (!isAdmin) {
    return (
      <ErrorState
        title="403 — Administrator Access Required"
        message="Your account holds OPERATOR permissions. User management and system audit controls are restricted to ADMIN users."
      />
    );
  }

  const handleToggleRole = async (targetUser) => {
    const currentNormalized = String(targetUser.role || "").toUpperCase();
    const nextRole = currentNormalized === "ADMIN" ? "OPERATOR" : "ADMIN";
    setBusyId(`role:${targetUser.id}`);
    setActionError(null);
    const res = await updateAdminUserRole(targetUser.id, nextRole);
    setBusyId(null);
    if (res.ok) {
      loadUsers();
    } else {
      setActionError(res.error || "Failed to update role.");
    }
  };

  const handleToggleStatus = async (targetUser) => {
    setBusyId(`status:${targetUser.id}`);
    setActionError(null);
    const res = await updateAdminUserStatus(targetUser.id, !targetUser.is_active);
    setBusyId(null);
    if (res.ok) {
      loadUsers();
    } else {
      setActionError(res.error || "Failed to update account status.");
    }
  };

  const audit = data?.audit_summary;

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5 text-rose-400 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-rose-100">
              Administrator User Management &amp; System Audit Console
            </div>
            <div className="text-xs text-rose-100/80">
              Manage RBAC role assignments, activate/deactivate accounts, and inspect verification &amp; revocation counts.
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={loadUsers}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-xs font-mono text-cyan-200"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {error && <ErrorState title="Admin Endpoint Error" message={error} onRetry={loadUsers} />}
      {actionError && (
        <ErrorState
          title="User Update Failed"
          message={actionError}
          onRetry={() => setActionError(null)}
        />
      )}

      {loading ? (
        <LoadingState label="Loading system users and audit counters..." />
      ) : (
        data && (
          <>
            {/* System Audit Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 font-mono">
              <div className="rounded border border-slate-800 bg-[#090f1e] p-3">
                <div className="text-[10px] text-slate-500 uppercase">Total Users</div>
                <div className="text-lg font-bold text-slate-100 mt-0.5">{audit.total_users}</div>
              </div>
              <div className="rounded border border-slate-800 bg-[#090f1e] p-3">
                <div className="text-[10px] text-slate-500 uppercase">Active Users</div>
                <div className="text-lg font-bold text-emerald-300 mt-0.5">{audit.active_users}</div>
              </div>
              <div className="rounded border border-slate-800 bg-[#090f1e] p-3">
                <div className="text-[10px] text-slate-500 uppercase">Verified Recs</div>
                <div className="text-lg font-bold text-cyan-300 mt-0.5">
                  {audit.verified_recommendations} / {audit.total_recommendations}
                </div>
              </div>
              <div className="rounded border border-slate-800 bg-[#090f1e] p-3">
                <div className="text-[10px] text-slate-500 uppercase">Human Decisions</div>
                <div className="text-lg font-bold text-slate-100 mt-0.5">{audit.total_decisions}</div>
              </div>
              <div className="rounded border border-slate-800 bg-[#090f1e] p-3">
                <div className="text-[10px] text-slate-500 uppercase">Incidents</div>
                <div className="text-lg font-bold text-amber-300 mt-0.5">{audit.total_incidents}</div>
              </div>
              <div className="rounded border border-slate-800 bg-[#090f1e] p-3">
                <div className="text-[10px] text-slate-500 uppercase">Revoked Tokens</div>
                <div className="text-lg font-bold text-rose-300 mt-0.5">{audit.revoked_tokens}</div>
              </div>
            </div>

            {/* User Table */}
            <div className="rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 text-xs font-mono uppercase tracking-wider text-slate-300">
                Registered Platform Users ({data.users.length})
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 bg-[#060b16] text-[10px] font-mono uppercase text-slate-400">
                      <th className="py-2.5 px-3">ID</th>
                      <th className="py-2.5 px-3">Username</th>
                      <th className="py-2.5 px-3">Email</th>
                      <th className="py-2.5 px-3">Role</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Created</th>
                      <th className="py-2.5 px-3">Admin Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {data.users.map((u) => {
                      const isSelf = currentUser && u.id === currentUser.id;
                      const roleUp = String(u.role || "").toUpperCase();
                      return (
                        <tr key={u.id} className="hover:bg-slate-900/40">
                          <td className="py-2.5 px-3 font-mono text-slate-400">#{u.id}</td>
                          <td className="py-2.5 px-3 font-mono font-semibold text-slate-100">
                            {u.username}
                            {isSelf && (
                              <span className="ml-2 text-[10px] text-cyan-400">(YOU)</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{u.email}</td>
                          <td className="py-2.5 px-3">
                            <StatusBadge
                              variant={roleUp === "ADMIN" ? "critical" : "standby"}
                              label={roleUp}
                              showDot={false}
                            />
                          </td>
                          <td className="py-2.5 px-3">
                            <StatusBadge
                              variant={u.is_active ? "nominal" : "critical"}
                              label={u.is_active ? "ACTIVE" : "INACTIVE"}
                              showDot={false}
                            />
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400">
                            {new Date(u.created_at).toISOString().slice(0, 10)}
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-2 font-mono text-[11px]">
                              <button
                                type="button"
                                disabled={isSelf || busyId === `role:${u.id}`}
                                title={
                                  isSelf
                                    ? "Cannot modify your own role"
                                    : `Switch role to ${roleUp === "ADMIN" ? "OPERATOR" : "ADMIN"}`
                                }
                                onClick={() => handleToggleRole(u)}
                                className="px-2.5 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-200 disabled:opacity-35 disabled:cursor-not-allowed"
                              >
                                {roleUp === "ADMIN" ? "Set OPERATOR" : "Set ADMIN"}
                              </button>
                              <button
                                type="button"
                                disabled={isSelf || busyId === `status:${u.id}`}
                                title={
                                  isSelf
                                    ? "Cannot deactivate your own account"
                                    : u.is_active
                                    ? "Deactivate user"
                                    : "Activate user"
                                }
                                onClick={() => handleToggleStatus(u)}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded border disabled:opacity-35 disabled:cursor-not-allowed ${
                                  u.is_active
                                    ? "border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-200"
                                    : "border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-200"
                                }`}
                              >
                                {u.is_active ? (
                                  <>
                                    <UserX className="w-3 h-3" />
                                    <span>Deactivate</span>
                                  </>
                                ) : (
                                  <>
                                    <UserCheck className="w-3 h-3" />
                                    <span>Activate</span>
                                  </>
                                )}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )
      )}
    </div>
  );
}
