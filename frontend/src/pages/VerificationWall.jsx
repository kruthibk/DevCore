import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Clock,
  FileText,
  HelpCircle,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import {
  approveRecommendation,
  evaluateVerification,
  fetchDecisionHistory,
  fetchRecommendationDetail,
  fetchRecommendations,
  rejectRecommendation,
  requestInvestigation,
} from "../api/client";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import StatusBadge from "../components/common/StatusBadge";

function verificationVariant(status) {
  if (status === "VERIFIED") return "nominal";
  if (status === "NEEDS_REVIEW") return "warning";
  return "critical";
}

function decisionVariant(decision) {
  if (decision === "APPROVED") return "nominal";
  if (decision === "INVESTIGATION_REQUESTED") return "warning";
  if (decision === "REJECTED") return "critical";
  return "muted";
}

function checkVariant(status) {
  if (status === "PASS") return "nominal";
  if (status === "WARN") return "warning";
  return "critical";
}

export default function VerificationWall() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedId = searchParams.get("id");

  const [recommendations, setRecommendations] = useState([]);
  const [summary, setSummary] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedId, setSelectedId] = useState(requestedId || null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [historyItems, setHistoryItems] = useState([]);
  const [activeTab, setActiveTab] = useState("queue"); // "queue" | "history"

  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState(null);
  const [decisionNotice, setDecisionNotice] = useState(null);
  const [reasonInput, setReasonInput] = useState("");
  const [notesInput, setNotesInput] = useState("");

  const loadList = useCallback(async () => {
    setLoading(true);
    const [recRes, histRes] = await Promise.all([
      fetchRecommendations({ status: statusFilter || null }),
      fetchDecisionHistory({ limit: 40 }),
    ]);

    if (recRes.ok && recRes.data) {
      const items = recRes.data.items || [];
      setRecommendations(items);
      setSummary(recRes.data.summary || null);
      setError(null);
      setSelectedId((prev) => {
        if (requestedId && items.some((i) => i.recommendation_id === requestedId)) {
          return requestedId;
        }
        if (prev && items.some((i) => i.recommendation_id === prev)) {
          return prev;
        }
        return items[0]?.recommendation_id || null;
      });
    } else {
      setError(recRes.error || "Unable to load Verification Wall recommendations.");
    }

    if (histRes.ok && histRes.data) {
      setHistoryItems(histRes.data.items || []);
    }
    setLoading(false);
  }, [statusFilter, requestedId]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (requestedId) {
      setSelectedId(requestedId);
    }
  }, [requestedId]);

  const loadDetail = useCallback(async (recId) => {
    if (!recId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    const res = await fetchRecommendationDetail(recId);
    if (res.ok && res.data) {
      setDetail(res.data);
      setDecisionError(null);
    } else {
      setDecisionError(res.error || "Failed to load recommendation details.");
    }
    setDetailLoading(false);
  }, []);

  useEffect(() => {
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  const handleSelect = (recId) => {
    setSelectedId(recId);
    setSearchParams({ id: recId });
    setActiveTab("queue");
  };

  const handleReevaluate = async () => {
    if (!detail) return;
    setDecisionBusy(true);
    setDecisionError(null);
    const res = await evaluateVerification({
      recommendation_id: detail.recommendation_id,
      source_type: detail.source_type,
      satellite_id: detail.satellite_id,
      subsystem: detail.subsystem,
      question: detail.question,
      anomaly_summary: detail.anomaly_summary,
      verified_observations: detail.verified_observations,
      possible_explanations: detail.possible_explanations,
      supporting_evidence: detail.supporting_evidence,
      contradicting_or_missing_evidence: detail.contradicting_or_missing_evidence,
      recommended_checks: detail.recommended_checks,
      uncertainty_and_limitations: detail.uncertainty_and_limitations,
      citations: detail.citations,
      retrieved_evidence: detail.retrieved_evidence,
      verified_context: detail.verified_context,
      generation_status: detail.generation_status,
      linked_alert_id: detail.linked_alert_id,
      linked_correlation_id: detail.linked_correlation_id,
      linked_incident_id: detail.linked_incident_id,
    });
    setDecisionBusy(false);
    if (res.ok && res.data) {
      setDetail(res.data);
      loadList();
    } else {
      setDecisionError(res.error || "Re-evaluation failed.");
    }
  };

  const handleDecision = async (kind) => {
    if (!detail) return;
    if ((kind === "reject" || kind === "investigate") && reasonInput.trim().length < 5) {
      setDecisionError("Provide a reason (at least 5 characters) before rejecting or requesting investigation.");
      return;
    }
    setDecisionBusy(true);
    setDecisionError(null);
    setDecisionNotice(null);

    let res;
    if (kind === "approve") {
      res = await approveRecommendation(detail.recommendation_id, notesInput.trim() || null);
    } else if (kind === "reject") {
      res = await rejectRecommendation(
        detail.recommendation_id,
        reasonInput.trim(),
        notesInput.trim() || null
      );
    } else {
      res = await requestInvestigation(
        detail.recommendation_id,
        reasonInput.trim(),
        notesInput.trim() || null
      );
    }

    setDecisionBusy(false);
    if (res.ok && res.data) {
      setDetail(res.data);
      setReasonInput("");
      setNotesInput("");
      setDecisionNotice({
        decision: res.data.latest_decision_status,
        incidentId: res.data.linked_incident_id,
      });
      loadList();
    } else {
      setDecisionError(res.error || "Unable to record operator decision.");
    }
  };

  const latestVer = detail?.latest_verification;
  const isRejected = latestVer?.status === "REJECTED";

  return (
    <div className="space-y-6">
      {/* Safety Wall Banner */}
      <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-cyan-100">
              Deterministic Verification Wall &amp; Human Operator Approval Gate
            </div>
            <p className="text-xs text-cyan-100/80 mt-0.5">
              Deterministic 10-rule safety gate independent of LLM output. A{" "}
              <span className="font-mono font-semibold">VERIFIED</span> result confirms configured checks
              passed—it is not a guarantee of real-world spacecraft correctness. Approval never triggers spacecraft commands.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap shrink-0">
          <StatusBadge variant="muted" label={`Total: ${summary?.TOTAL ?? 0}`} />
          <StatusBadge variant="nominal" label={`Verified: ${summary?.VERIFIED ?? 0}`} />
          <StatusBadge variant="warning" label={`Review: ${summary?.NEEDS_REVIEW ?? 0}`} />
          <StatusBadge variant="critical" label={`Rejected: ${summary?.REJECTED ?? 0}`} />
        </div>
      </div>

      {/* Controls & Tabs */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setActiveTab("queue")}
            className={`px-3 py-1.5 rounded border transition-colors ${
              activeTab === "queue"
                ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-200"
                : "border-slate-800 bg-[#050913] text-slate-400 hover:text-slate-200"
            }`}
          >
            Verification Queue ({recommendations.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("history")}
            className={`px-3 py-1.5 rounded border transition-colors ${
              activeTab === "history"
                ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-200"
                : "border-slate-800 bg-[#050913] text-slate-400 hover:text-slate-200"
            }`}
          >
            Decision Audit History ({historyItems.length})
          </button>

          {activeTab === "queue" && (
            <label className="flex items-center gap-1.5 text-slate-400 ml-2">
              <span>Status:</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
              >
                <option value="">All</option>
                <option value="VERIFIED">VERIFIED</option>
                <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
                <option value="REJECTED">REJECTED</option>
              </select>
            </label>
          )}
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

      {error && <ErrorState title="Verification Wall Unavailable" message={error} onRetry={loadList} />}

      {activeTab === "history" ? (
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 text-xs font-mono uppercase tracking-wider text-slate-300">
            Chronological Human Operator Decisions (Command Execution: Always Disabled)
          </div>
          {historyItems.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={Clock}
                title="No operator decisions recorded yet."
                description="Submit an AI Copilot recommendation to the Verification Wall and record an approval, rejection, or investigation request."
                phaseBadge="Decision Audit Log"
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-[#060b16] text-[10px] font-mono uppercase text-slate-400">
                    <th className="py-2.5 px-3">Decision ID</th>
                    <th className="py-2.5 px-3">Recommendation</th>
                    <th className="py-2.5 px-3">Linked Incident</th>
                    <th className="py-2.5 px-3">Verification</th>
                    <th className="py-2.5 px-3">Human Decision</th>
                    <th className="py-2.5 px-3">Operator</th>
                    <th className="py-2.5 px-3">Reason / Notes</th>
                    <th className="py-2.5 px-3">Commands</th>
                    <th className="py-2.5 px-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {historyItems.map((item) => (
                    <tr
                      key={item.decision_id}
                      onClick={() => handleSelect(item.recommendation_id)}
                      className="cursor-pointer hover:bg-slate-900/50"
                    >
                      <td className="py-2.5 px-3 font-mono text-cyan-300 whitespace-nowrap">
                        {item.decision_id}
                      </td>
                      <td className="py-2.5 px-3 max-w-xs">
                        <div className="font-mono text-[11px] text-slate-300">
                          {item.recommendation_id} · {item.subsystem}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">
                          {item.recommendation_summary}
                        </div>
                      </td>
                      <td
                        className="py-2.5 px-3 font-mono text-[11px] whitespace-nowrap"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {item.linked_incident_id ? (
                          <Link
                            to={`/incidents?id=${encodeURIComponent(item.linked_incident_id)}`}
                            className="text-emerald-300 underline hover:text-emerald-200"
                          >
                            {item.linked_incident_id}
                          </Link>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <StatusBadge
                          variant={verificationVariant(item.verification_status_at_decision)}
                          label={item.verification_status_at_decision}
                          showDot={false}
                        />
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <StatusBadge
                          variant={decisionVariant(item.decision)}
                          label={item.decision}
                          showDot={false}
                        />
                      </td>
                      <td className="py-2.5 px-3 font-mono whitespace-nowrap text-slate-200">
                        {item.operator_username} ({item.operator_role})
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 max-w-xs">
                        {item.reason || item.notes || "—"}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-emerald-300 whitespace-nowrap">
                        {item.command_executed ? "EXECUTED" : "NONE (SAFE)"}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                        {new Date(item.decided_at).toISOString().replace("T", " ").slice(0, 19)} UTC
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Left: Recommendation List (4 cols) */}
          <div className="xl:col-span-4 rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 text-xs font-mono uppercase tracking-wider text-slate-300">
              Submitted Recommendations ({recommendations.length})
            </div>
            {loading ? (
              <div className="p-5">
                <LoadingState label="Loading Verification Wall..." />
              </div>
            ) : recommendations.length === 0 ? (
              <div className="p-5">
                <EmptyState
                  icon={ClipboardList}
                  title="No recommendations submitted yet."
                  description="Generate an evidence-linked response on the AI Copilot page and click 'Submit to Verification Wall'."
                  phaseBadge="Verification Wall Ready"
                  compact
                />
              </div>
            ) : (
              <div className="divide-y divide-slate-800/70 max-h-[75vh] overflow-y-auto">
                {recommendations.map((rec) => {
                  const active = rec.recommendation_id === selectedId;
                  return (
                    <button
                      key={rec.recommendation_id}
                      type="button"
                      onClick={() => handleSelect(rec.recommendation_id)}
                      className={`w-full text-left p-3.5 transition-colors space-y-1.5 ${
                        active ? "bg-cyan-500/10" : "hover:bg-slate-900/60"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-mono font-semibold text-cyan-300">
                          {rec.recommendation_id}
                        </span>
                        <StatusBadge
                          variant={verificationVariant(rec.latest_verification_status)}
                          label={rec.latest_verification_status}
                          showDot={false}
                        />
                      </div>
                      <div className="text-xs text-slate-200 line-clamp-2">{rec.anomaly_summary}</div>
                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span>
                          {rec.source_type} · {rec.subsystem}
                        </span>
                        <span>
                          {rec.latest_decision_status || "AWAITING_OPERATOR"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right: 3-Layer Inspection & Human Decision Panel (8 cols) */}
          <div className="xl:col-span-8 space-y-5">
            {detailLoading ? (
              <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-6">
                <LoadingState label="Inspecting deterministic verification checks..." />
              </div>
            ) : !detail ? (
              <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-8 text-center text-xs text-slate-400">
                Select a submitted recommendation to inspect its verification checks, citations, and operator decisions.
              </div>
            ) : (
              <>
                {/* Layer 1: AI Recommendation Output */}
                <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-cyan-400" />
                      <h2 className="text-sm font-semibold text-slate-100">
                        1. AI Recommendation ({detail.recommendation_id})
                      </h2>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {detail.linked_incident_id && (
                        <Link
                          to={`/incidents?id=${encodeURIComponent(detail.linked_incident_id)}`}
                          className="px-2 py-0.5 rounded border border-emerald-500/35 bg-emerald-500/15 text-[11px] font-mono text-emerald-200 hover:bg-emerald-500/25"
                        >
                          Incident {detail.linked_incident_id} →
                        </Link>
                      )}
                      {detail.linked_alert_id && (
                        <StatusBadge variant="warning" label={`Alert: ${detail.linked_alert_id}`} showDot={false} />
                      )}
                      {detail.linked_correlation_id && (
                        <StatusBadge variant="info" label={`Corr: ${detail.linked_correlation_id}`} showDot={false} />
                      )}
                      <StatusBadge variant="info" label={detail.source_type} showDot={false} />
                      <StatusBadge variant="muted" label={detail.subsystem} showDot={false} />
                    </div>
                  </div>

                  {detail.question && (
                    <div className="text-xs text-slate-400 font-mono">
                      Query: {detail.question}
                    </div>
                  )}

                  <p className="text-sm text-slate-100 leading-relaxed">{detail.anomaly_summary}</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="rounded border border-slate-800 bg-[#050913] p-3">
                      <div className="text-[10px] font-mono uppercase text-emerald-300 mb-1.5">
                        Verified Observations
                      </div>
                      <ul className="space-y-1 text-slate-300 list-disc pl-4">
                        {(detail.verified_observations || []).length > 0 ? (
                          detail.verified_observations.map((obs, idx) => <li key={idx}>{obs}</li>)
                        ) : (
                          <li className="list-none -ml-4 text-slate-500">None attached.</li>
                        )}
                      </ul>
                    </div>

                    <div className="rounded border border-slate-800 bg-[#050913] p-3">
                      <div className="text-[10px] font-mono uppercase text-amber-300 mb-1.5">
                        Recommended Investigative Checks
                      </div>
                      <ul className="space-y-1 text-slate-300 list-disc pl-4">
                        {(detail.recommended_checks || []).length > 0 ? (
                          detail.recommended_checks.map((chk, idx) => <li key={idx}>{chk}</li>)
                        ) : (
                          <li className="list-none -ml-4 text-slate-500">None specified.</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  {/* Citations */}
                  <div>
                    <div className="text-[10px] font-mono uppercase text-cyan-300 mb-1.5">
                      Submitted Source Citations ({(detail.citations || []).length})
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(detail.citations || []).length === 0 ? (
                        <span className="text-xs text-slate-500">No citations attached.</span>
                      ) : (
                        detail.citations.map((c, idx) => (
                          <span
                            key={`${c.chunk_id || idx}`}
                            className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[11px] font-mono text-cyan-100"
                          >
                            {c.runbook_id} · {c.section_heading}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                {/* Layer 2: Automated Deterministic Verification Result */}
                {latestVer && (
                  <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="w-4 h-4 text-emerald-400" />
                        <h2 className="text-sm font-semibold text-slate-100">
                          2. Deterministic Verification Wall ({latestVer.verification_id})
                        </h2>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge
                          variant={verificationVariant(latestVer.status)}
                          label={latestVer.status}
                        />
                        <button
                          type="button"
                          disabled={decisionBusy}
                          onClick={handleReevaluate}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-200 disabled:opacity-50"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Re-evaluate</span>
                        </button>
                      </div>
                    </div>

                    <p className="text-[11px] font-mono text-slate-400">{latestVer.disclaimer}</p>

                    {latestVer.warnings?.length > 0 && (
                      <div className="space-y-1.5">
                        {latestVer.warnings.map((w, idx) => (
                          <div
                            key={idx}
                            className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 flex items-start gap-2"
                          >
                            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs">
                      {latestVer.checks.map((chk) => (
                        <div
                          key={chk.rule_id}
                          className="rounded border border-slate-800 bg-[#050913] p-2.5 space-y-1"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-slate-200">{chk.name}</span>
                            <StatusBadge
                              variant={checkVariant(chk.status)}
                              label={chk.status}
                              showDot={false}
                            />
                          </div>
                          <div className="text-[11px] text-slate-400">{chk.detail}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Layer 3: Human Operator Decision & Preserved History */}
                <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                      <h2 className="text-sm font-semibold text-slate-100">
                        3. Human Operator Decision (Separate from AI Verification)
                      </h2>
                    </div>
                    <StatusBadge
                      variant={decisionVariant(detail.latest_decision_status)}
                      label={detail.latest_decision_status || "AWAITING DECISION"}
                    />
                  </div>

                  {decisionError && (
                    <div className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                      {decisionError}
                    </div>
                  )}

                  {decisionNotice?.incidentId && (
                    <div className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100 flex flex-wrap items-center justify-between gap-2">
                      <span>
                        Decision <span className="font-mono font-semibold">{decisionNotice.decision}</span>{" "}
                        recorded and synced to Incident{" "}
                        <span className="font-mono font-semibold">{decisionNotice.incidentId}</span>.
                      </span>
                      <Link
                        to={`/incidents?id=${encodeURIComponent(decisionNotice.incidentId)}`}
                        className="underline font-semibold text-cyan-300"
                      >
                        Open Linked Incident Timeline →
                      </Link>
                    </div>
                  )}

                  {isRejected && (
                    <div className="rounded border border-rose-500/35 bg-rose-500/10 px-3 py-2 text-xs text-rose-200 flex items-start gap-2">
                      <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                      <span>
                        Approval is blocked because the Verification Wall status is{" "}
                        <span className="font-mono font-semibold">REJECTED</span>. You may reject with a
                        recorded reason or request further investigation.
                      </span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                        Decision Reason (Required for Reject / Investigation)
                      </label>
                      <input
                        type="text"
                        value={reasonInput}
                        onChange={(e) => setReasonInput(e.target.value)}
                        placeholder="e.g., Verified telemetry trend or rejected due to ungrounded claim"
                        className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-slate-400 mb-1">
                        Operator Notes (Optional)
                      </label>
                      <input
                        type="text"
                        value={notesInput}
                        onChange={(e) => setNotesInput(e.target.value)}
                        placeholder="Additional ground-station context..."
                        className="w-full rounded border border-slate-700 bg-[#050913] px-3 py-2 text-slate-100"
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5 font-mono text-xs">
                    <button
                      type="button"
                      disabled={decisionBusy || isRejected}
                      title={isRejected ? "Cannot approve a REJECTED recommendation" : "Approve investigative guidance"}
                      onClick={() => handleDecision("approve")}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded border border-emerald-500/40 bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-200 disabled:opacity-35 disabled:cursor-not-allowed"
                    >
                      <ThumbsUp className="w-3.5 h-3.5" />
                      <span>Approve Guidance</span>
                    </button>

                    <button
                      type="button"
                      disabled={decisionBusy}
                      onClick={() => handleDecision("reject")}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded border border-rose-500/40 bg-rose-500/15 hover:bg-rose-500/25 text-rose-200 disabled:opacity-40"
                    >
                      <ThumbsDown className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>

                    <button
                      type="button"
                      disabled={decisionBusy}
                      onClick={() => handleDecision("investigate")}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded border border-amber-500/40 bg-amber-500/15 hover:bg-amber-500/25 text-amber-200 disabled:opacity-40"
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                      <span>Request Investigation</span>
                    </button>
                  </div>

                  {/* Preserved Decision & Verification History */}
                  <div className="pt-2 border-t border-slate-800 space-y-2">
                    <div className="text-[10px] font-mono uppercase text-slate-400">
                      Preserved Human Decision History ({detail.decisions?.length || 0}) · Verification Evaluations ({detail.verifications?.length || 0})
                    </div>
                    {(detail.decisions || []).length === 0 ? (
                      <div className="text-xs text-slate-500">
                        No human operator decisions recorded for this recommendation yet.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-56 overflow-y-auto">
                        {detail.decisions.map((dec) => (
                          <div
                            key={dec.decision_id}
                            className="rounded border border-slate-800 bg-[#050913] p-2.5 text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                              <div className="flex items-center gap-2">
                                <StatusBadge
                                  variant={decisionVariant(dec.decision)}
                                  label={dec.decision}
                                  showDot={false}
                                />
                                <span className="font-mono text-slate-200 font-semibold">
                                  {dec.operator_username}
                                </span>
                                <span className="font-mono text-[10px] text-slate-500">
                                  ({dec.operator_role}) · Ver: {dec.verification_status_at_decision}
                                </span>
                              </div>
                              <span className="font-mono text-[10px] text-slate-500">
                                {new Date(dec.decided_at).toISOString().replace("T", " ").slice(0, 19)} UTC
                              </span>
                            </div>
                            {dec.reason && <div className="text-slate-300">Reason: {dec.reason}</div>}
                            {dec.notes && <div className="text-slate-400">Notes: {dec.notes}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
