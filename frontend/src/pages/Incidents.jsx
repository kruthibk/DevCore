import { useCallback, useEffect, useState } from "react";
import {
  Bot,
  ClipboardList,
  Clock,
  FileCheck2,
  FileText,
  GitBranch,
  MessageSquarePlus,
  Plus,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  X,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import {
  addIncidentLog,
  createIncident,
  fetchIncidentDetail,
  fetchIncidents,
  updateIncident,
} from "../api/client";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import StatusBadge from "../components/common/StatusBadge";
import { useAuth } from "../context/AuthContext";

const STATUS_OPTIONS = ["OPEN", "INVESTIGATING", "MITIGATED", "CLOSED"];
const SEVERITY_OPTIONS = ["CRITICAL", "WARNING", "INFO"];
const SUBSYSTEM_OPTIONS = [
  "battery_power",
  "temperature_thermal",
  "attitude_adcs",
  "OBC",
  "SENSORS",
  "GENERAL",
];

function severityVariant(severity) {
  if (severity === "CRITICAL") return "critical";
  if (severity === "WARNING") return "warning";
  return "info";
}

function statusVariant(status) {
  if (status === "OPEN") return "critical";
  if (status === "INVESTIGATING") return "warning";
  if (status === "MITIGATED") return "info";
  return "nominal";
}

function actionVariant(action) {
  if (action === "CREATED" || action === "RECOMMENDATION_LINKED") return "info";
  if (action === "STATUS_CHANGE") return "warning";
  if (action === "VERIFICATION_RECORDED" || action === "DECISION_RECORDED") return "nominal";
  return "muted";
}

export default function Incidents({ stream }) {
  const { incidentVersion } = stream || {};
  const { canOperate, role, username } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedId = searchParams.get("id");

  const [incidents, setIncidents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [subsystemFilter, setSubsystemFilter] = useState("");

  const [selectedId, setSelectedId] = useState(requestedId || null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [noteInput, setNoteInput] = useState("");
  const [assigneeInput, setAssigneeInput] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newSummary, setNewSummary] = useState("");
  const [newSubsystem, setNewSubsystem] = useState("battery_power");
  const [newSeverity, setNewSeverity] = useState("WARNING");
  const [newAlerts, setNewAlerts] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState(null);

  const loadList = useCallback(async () => {
    setLoading(true);
    const res = await fetchIncidents({
      status: statusFilter || null,
      severity: severityFilter || null,
      subsystem: subsystemFilter || null,
    });
    if (res.ok && res.data) {
      const items = res.data.items || [];
      setIncidents(items);
      setSummary(res.data.summary || null);
      setError(null);
      setSelectedId((prev) => {
        if (requestedId && items.some((i) => i.incident_id === requestedId)) {
          return requestedId;
        }
        if (prev && items.some((i) => i.incident_id === prev)) {
          return prev;
        }
        return items[0]?.incident_id || null;
      });
    } else {
      setError(res.error || "Unable to load incidents");
    }
    setLoading(false);
  }, [statusFilter, severityFilter, subsystemFilter, requestedId]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (requestedId) {
      setSelectedId(requestedId);
    }
  }, [requestedId]);

  const loadDetail = useCallback(async (incId) => {
    if (!incId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    const res = await fetchIncidentDetail(incId);
    if (res.ok && res.data) {
      setDetail(res.data);
      setAssigneeInput(res.data.assigned_to || "");
      setActionError(null);
    } else {
      setActionError(res.error || "Unable to load incident details");
    }
    setDetailLoading(false);
  }, []);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  useEffect(() => {
    if (incidentVersion) {
      loadList();
      if (selectedId) {
        loadDetail(selectedId);
      }
    }
  }, [incidentVersion, loadList, loadDetail, selectedId]);

  const handleSelect = (incId) => {
    setSelectedId(incId);
    setSearchParams({ id: incId });
  };

  const handleStatusTransition = async (nextStatus) => {
    if (!detail || !canOperate || detail.status === nextStatus) return;
    setActionBusy(true);
    setActionError(null);
    const res = await updateIncident(detail.incident_id, { status: nextStatus });
    setActionBusy(false);
    if (res.ok && res.data) {
      setDetail(res.data);
      loadList();
    } else {
      setActionError(res.error || "Status transition failed");
    }
  };

  const handleAssigneeSave = async () => {
    if (!detail || !canOperate) return;
    setActionBusy(true);
    setActionError(null);
    const res = await updateIncident(detail.incident_id, {
      assigned_to: assigneeInput.trim() || username,
    });
    setActionBusy(false);
    if (res.ok && res.data) {
      setDetail(res.data);
      loadList();
    } else {
      setActionError(res.error || "Failed to update assignee");
    }
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!detail || !canOperate || !noteInput.trim()) return;
    setActionBusy(true);
    setActionError(null);
    const res = await addIncidentLog(detail.incident_id, noteInput.trim());
    setActionBusy(false);
    if (res.ok && res.data) {
      setDetail(res.data);
      setNoteInput("");
      loadList();
    } else {
      setActionError(res.error || "Failed to add investigation note");
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!canOperate) return;
    setCreateBusy(true);
    setCreateError(null);
    const linked = newAlerts
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const res = await createIncident({
      title: newTitle.trim(),
      summary: newSummary.trim(),
      subsystem: newSubsystem,
      severity: newSeverity,
      linked_alert_ids: linked,
    });
    setCreateBusy(false);
    if (res.ok && res.data) {
      setCreateOpen(false);
      setNewTitle("");
      setNewSummary("");
      setNewAlerts("");
      setSelectedId(res.data.incident_id);
      setSearchParams({ id: res.data.incident_id });
      setDetail(res.data);
      loadList();
    } else {
      setCreateError(res.error || "Failed to create incident");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Summary Bar */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <FileCheck2 className="w-5 h-5 text-cyan-400 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-slate-100">
              Incident Management & Audit Trail Console
            </div>
            <div className="text-xs text-slate-400">
              PostgreSQL-persisted incident lifecycle (`OPEN` → `INVESTIGATING` → `MITIGATED` → `CLOSED`) with immutable actor audit logs.
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge variant="muted" label={`Total: ${summary?.total ?? 0}`} />
          <StatusBadge variant="critical" label={`Open: ${summary?.open ?? 0}`} />
          <StatusBadge variant="info" label={`Mitigated: ${summary?.mitigated ?? 0}`} />
          <StatusBadge variant="nominal" label={`Closed: ${summary?.closed ?? 0}`} />
          {!canOperate && <StatusBadge variant="warning" label={`${role} (READ-ONLY)`} />}
          <button
            type="button"
            disabled={!canOperate}
            title={!canOperate ? "OPERATOR or ADMIN role required" : "Create a new tracked incident"}
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-cyan-500/40 bg-cyan-500/15 hover:bg-cyan-500/25 text-xs font-mono font-semibold text-cyan-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Incident</span>
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All</option>
              {STATUS_OPTIONS.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All</option>
              {SEVERITY_OPTIONS.map((sv) => (
                <option key={sv} value={sv}>
                  {sv}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Subsystem:</span>
            <select
              value={subsystemFilter}
              onChange={(e) => setSubsystemFilter(e.target.value)}
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All</option>
              {SUBSYSTEM_OPTIONS.map((sub) => (
                <option key={sub} value={sub}>
                  {sub}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={loadList}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Refresh</span>
        </button>
      </div>

      {error && <ErrorState title="Unable to Load Incidents" message={error} onRetry={loadList} />}
      {actionError && (
        <ErrorState
          title="Incident Action Failed"
          message={actionError}
          onRetry={() => setActionError(null)}
        />
      )}

      {/* Incident Table + Details + Audit Timeline */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left: Registry Table (7 cols) */}
        <div className="xl:col-span-7 rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Incident Registry ({incidents.length})
            </span>
            <span className="text-[11px] font-mono text-slate-500">
              Active: {summary?.open ?? 0} // Resolved: {summary?.resolved ?? 0}
            </span>
          </div>

          {loading ? (
            <div className="p-6">
              <LoadingState label="Loading incidents from PostgreSQL..." />
            </div>
          ) : incidents.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={ClipboardList}
                title="No incidents logged yet."
                description="Click 'New Incident' above or promote an active finding from Alerts or AI Copilot."
                phaseBadge="PostgreSQL Registry Active"
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#060b16] text-[10px] font-mono uppercase text-slate-400">
                    <th className="py-2.5 px-3">Incident ID</th>
                    <th className="py-2.5 px-3">Title & Subsystem</th>
                    <th className="py-2.5 px-3">Severity</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {incidents.map((inc) => {
                    const active = inc.incident_id === selectedId;
                    return (
                      <tr
                        key={inc.incident_id}
                        onClick={() => handleSelect(inc.incident_id)}
                        className={`cursor-pointer transition-colors ${
                          active ? "bg-cyan-500/10" : "hover:bg-slate-900/50"
                        }`}
                      >
                        <td className="py-2.5 px-3 font-mono font-semibold text-cyan-300 whitespace-nowrap">
                          {inc.incident_id}
                        </td>
                        <td className="py-2.5 px-3 max-w-xs">
                          <div className="font-medium text-slate-100 truncate">{inc.title}</div>
                          <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                            {inc.subsystem} · by {inc.created_by}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <StatusBadge variant={severityVariant(inc.severity)} label={inc.severity} />
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <StatusBadge variant={statusVariant(inc.status)} label={inc.status} />
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                          {new Date(inc.updated_at).toISOString().slice(11, 19)} UTC
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: Incident Detail & Chronological Audit Timeline (5 cols) */}
        <div className="xl:col-span-5 rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-100">Incident Details & Audit Log</h2>
            </div>
            {detail && <StatusBadge variant={statusVariant(detail.status)} label={detail.status} />}
          </div>

          {detailLoading ? (
            <LoadingState label="Loading incident detail & audit timeline..." />
          ) : !detail ? (
            <div className="text-xs text-slate-400 py-8 text-center">
              Select an incident from the registry to inspect its lifecycle and audit trail.
            </div>
          ) : (
            <div className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-2.5 font-mono">
                <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                  <div className="text-[10px] text-slate-500 uppercase">Incident ID</div>
                  <div className="text-cyan-300 font-semibold mt-0.5">{detail.incident_id}</div>
                </div>
                <div className="rounded border border-slate-800 bg-[#060b16] p-2.5">
                  <div className="text-[10px] text-slate-500 uppercase">Subsystem</div>
                  <div className="text-slate-200 mt-0.5">{detail.subsystem}</div>
                </div>
              </div>

              <div className="rounded border border-slate-800 bg-[#060b16] p-3 space-y-1.5">
                <div className="text-sm font-semibold text-slate-100">{detail.title}</div>
                <p className="text-xs text-slate-300 leading-relaxed">{detail.summary}</p>
                {detail.linked_alert_ids?.length > 0 && (
                  <div className="pt-1 flex flex-wrap gap-1.5 items-center">
                    {detail.linked_alert_ids.map((aid) => (
                      <Link
                        key={aid}
                        to={`/copilot?alert_id=${encodeURIComponent(aid)}&incident_id=${encodeURIComponent(
                          detail.incident_id
                        )}`}
                        className="px-2 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-[10px] font-mono text-amber-200"
                        title="Investigate linked alert with AI Copilot"
                      >
                        Alert: {aid} →
                      </Link>
                    ))}
                  </div>
                )}
                {detail.linked_correlation_ids?.length > 0 && (
                  <div className="pt-1 flex flex-wrap gap-1.5 items-center">
                    {detail.linked_correlation_ids.map((cid) => (
                      <Link
                        key={cid}
                        to={`/copilot?correlation_id=${encodeURIComponent(
                          cid
                        )}&incident_id=${encodeURIComponent(detail.incident_id)}`}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-indigo-500/35 bg-indigo-500/15 hover:bg-indigo-500/25 text-[10px] font-mono text-indigo-200"
                      >
                        <GitBranch className="w-3 h-3" />
                        <span>Corr: {cid} →</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {detail.linked_recommendation && (
                <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-emerald-300">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>Linked Verification &amp; Decision ({detail.linked_recommendation.recommendation_id})</span>
                    </div>
                    <Link
                      to={`/verification?id=${encodeURIComponent(detail.linked_recommendation.recommendation_id)}`}
                      className="text-[11px] font-mono underline text-cyan-300 hover:text-cyan-200"
                    >
                      Inspect Verification Wall →
                    </Link>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge
                      variant={
                        detail.linked_recommendation.latest_verification_status === "VERIFIED"
                          ? "nominal"
                          : detail.linked_recommendation.latest_verification_status === "NEEDS_REVIEW"
                          ? "warning"
                          : "critical"
                      }
                      label={`Verification: ${detail.linked_recommendation.latest_verification_status}`}
                      showDot={false}
                    />
                    <StatusBadge
                      variant={
                        detail.linked_recommendation.latest_decision_status === "APPROVED"
                          ? "nominal"
                          : detail.linked_recommendation.latest_decision_status === "REJECTED"
                          ? "critical"
                          : "warning"
                      }
                      label={`Decision: ${
                        detail.linked_recommendation.latest_decision_status || "AWAITING_OPERATOR"
                      }`}
                      showDot={false}
                    />
                  </div>
                  {detail.linked_recommendation.decisions?.length > 0 && (
                    <div className="text-[11px] text-slate-300 font-mono">
                      Latest Sign-off: {detail.linked_recommendation.decisions.at(-1).operator_username} (
                      {detail.linked_recommendation.decisions.at(-1).operator_role}) · Commands:{" "}
                      {detail.linked_recommendation.decisions.at(-1).command_executed ? "EXECUTED" : "NONE (SAFE)"}
                    </div>
                  )}
                </div>
              )}

              {!detail.linked_recommendation && (
                <div className="flex items-center justify-end">
                  <Link
                    to={`/copilot?incident_id=${encodeURIComponent(detail.incident_id)}${
                      detail.linked_alert_ids?.[0]
                        ? `&alert_id=${encodeURIComponent(detail.linked_alert_ids[0])}`
                        : ""
                    }${
                      detail.linked_correlation_ids?.[0]
                        ? `&correlation_id=${encodeURIComponent(detail.linked_correlation_ids[0])}`
                        : ""
                    }`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-indigo-500/40 bg-indigo-500/15 hover:bg-indigo-500/25 text-[11px] font-mono text-indigo-100"
                  >
                    <Bot className="w-3.5 h-3.5" />
                    <span>Launch Copilot Triage for Incident →</span>
                  </Link>
                </div>
              )}

              {detail.copilot_summary && (
                <div className="rounded border border-cyan-500/25 bg-cyan-500/5 p-3">
                  <div className="text-[10px] font-mono uppercase text-cyan-300 mb-1">
                    Attached Copilot Triage Summary
                  </div>
                  <pre className="text-[11px] text-slate-300 whitespace-pre-wrap font-sans leading-relaxed">
                    {detail.copilot_summary}
                  </pre>
                </div>
              )}

              {/* Assignee & Status Transitions */}
              <div className="rounded border border-slate-800 bg-[#060b16] p-3 space-y-3">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                  <input
                    type="text"
                    value={assigneeInput}
                    disabled={!canOperate || actionBusy}
                    onChange={(e) => setAssigneeInput(e.target.value)}
                    placeholder="Assignee"
                    className="flex-1 rounded border border-slate-700 bg-[#050913] px-2 py-1 text-xs font-mono text-slate-200 disabled:opacity-50"
                  />
                  <button
                    type="button"
                    disabled={!canOperate || actionBusy}
                    onClick={handleAssigneeSave}
                    className="px-2.5 py-1 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Assign
                  </button>
                </div>

                <div>
                  <div className="text-[10px] font-mono uppercase text-slate-500 mb-1.5">
                    Transition Workflow Status
                  </div>
                  <div className="grid grid-cols-4 gap-1.5 font-mono">
                    {STATUS_OPTIONS.map((st) => (
                      <button
                        key={st}
                        type="button"
                        disabled={!canOperate || actionBusy || detail.status === st}
                        title={!canOperate ? "OPERATOR or ADMIN role required" : `Set status to ${st}`}
                        onClick={() => handleStatusTransition(st)}
                        className={`px-2 py-1.5 rounded border text-[10px] transition-colors disabled:cursor-not-allowed ${
                          detail.status === st
                            ? "border-cyan-500/50 bg-cyan-500/20 text-cyan-100 font-semibold"
                            : "border-slate-700 bg-slate-900 text-slate-300 hover:border-cyan-500/40 disabled:opacity-35"
                        }`}
                      >
                        {st}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Add Investigation Note */}
              <form onSubmit={handleAddNote} className="space-y-2">
                <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
                  <MessageSquarePlus className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Append Investigation Note</span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={noteInput}
                    disabled={!canOperate || actionBusy}
                    onChange={(e) => setNoteInput(e.target.value)}
                    placeholder={
                      canOperate
                        ? "Record ground-station observation or triage note..."
                        : "OPERATOR or ADMIN role required to add notes"
                    }
                    className="flex-1 rounded border border-slate-700 bg-[#050913] px-2.5 py-1.5 text-xs text-slate-100 disabled:opacity-50"
                  />
                  <button
                    type="submit"
                    disabled={!canOperate || actionBusy || !noteInput.trim()}
                    className="px-3 py-1.5 rounded border border-cyan-500/40 bg-cyan-500/15 hover:bg-cyan-500/25 text-xs font-mono text-cyan-100 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Log Note
                  </button>
                </div>
              </form>

              {/* Chronological Audit Log Timeline */}
              <div>
                <div className="text-[10px] font-mono uppercase text-slate-400 flex items-center gap-1.5 mb-2">
                  <Clock className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Audit Log Timeline ({detail.logs?.length || 0})</span>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {(detail.logs || []).map((log) => (
                    <div
                      key={log.id}
                      className="rounded border border-slate-800 bg-[#060b16] p-2.5 space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-1.5">
                          <StatusBadge variant={actionVariant(log.action)} label={log.action} showDot={false} />
                          <span className="font-mono text-[11px] text-slate-200 font-semibold">
                            {log.actor}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">({log.role})</span>
                        </div>
                        <span className="text-[10px] font-mono text-slate-500">
                          {new Date(log.created_at).toISOString().replace("T", " ").slice(0, 19)} UTC
                        </span>
                      </div>
                      {log.from_status && log.to_status && log.from_status !== log.to_status && (
                        <div className="text-[10px] font-mono text-amber-300">
                          {log.from_status} → {log.to_status}
                        </div>
                      )}
                      <div className="text-xs text-slate-300">{log.note}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* New Incident Modal */}
      {createOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-lg border border-slate-700 bg-[#090f1e] p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <Plus className="w-4 h-4 text-cyan-400" />
                <span>Log New Operational Incident</span>
              </div>
              <button
                type="button"
                onClick={() => setCreateOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {createError && (
              <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                  Title
                </label>
                <input
                  type="text"
                  required
                  minLength={3}
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g., EPS battery voltage drop during eclipse entry"
                  className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-slate-100"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                    Subsystem
                  </label>
                  <select
                    value={newSubsystem}
                    onChange={(e) => setNewSubsystem(e.target.value)}
                    className="w-full rounded border border-slate-700 bg-[#050913] px-2.5 py-2 text-slate-100"
                  >
                    {SUBSYSTEM_OPTIONS.map((sub) => (
                      <option key={sub} value={sub}>
                        {sub}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                    Severity
                  </label>
                  <select
                    value={newSeverity}
                    onChange={(e) => setNewSeverity(e.target.value)}
                    className="w-full rounded border border-slate-700 bg-[#050913] px-2.5 py-2 text-slate-100"
                  >
                    {SEVERITY_OPTIONS.map((sv) => (
                      <option key={sv} value={sv}>
                        {sv}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                  Summary
                </label>
                <textarea
                  required
                  minLength={3}
                  rows={3}
                  value={newSummary}
                  onChange={(e) => setNewSummary(e.target.value)}
                  placeholder="Observed anomaly telemetry, affected channels, and initial triage notes..."
                  className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-slate-100"
                />
              </div>

              <div>
                <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                  Linked Alert IDs (optional, comma-separated)
                </label>
                <input
                  type="text"
                  value={newAlerts}
                  onChange={(e) => setNewAlerts(e.target.value)}
                  placeholder="e.g., ALT-6AA3DDCC7C"
                  className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-slate-100 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  className="px-3 py-1.5 rounded border border-slate-700 font-mono text-slate-300 hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createBusy}
                  className="px-4 py-1.5 rounded border border-cyan-500/50 bg-cyan-500/20 hover:bg-cyan-500/30 font-mono font-semibold text-cyan-100 disabled:opacity-50"
                >
                  {createBusy ? "Creating..." : "Create Incident"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
