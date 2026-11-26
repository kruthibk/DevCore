import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  CheckCircle2,
  Database,
  FileText,
  HelpCircle,
  Loader2,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
} from "lucide-react";
import { askCopilot, fetchCopilotStatus, reindexCopilot } from "../api/client";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import StatusBadge from "../components/common/StatusBadge";

const SUGGESTED_QUESTIONS = [
  {
    label: "Battery Voltage Drop",
    question: "What should an operator investigate when battery voltage suddenly drops?",
    subsystem: "battery_power",
  },
  {
    label: "Temperature Spike",
    question: "How should a temperature spike be investigated?",
    subsystem: "temperature_thermal",
  },
  {
    label: "Attitude Roll/Pitch Change",
    question: "What should be checked when roll or pitch changes unexpectedly?",
    subsystem: "attitude_adcs",
  },
  {
    label: "Angle Wrap (+179° to -179°)",
    question: "Is a transition from +179° to -179° necessarily a large attitude change?",
    subsystem: "attitude_adcs",
  },
  {
    label: "Battery vs Thermal Context",
    question: "Battery voltage dropped and battery temperature increased abnormally — how should electrical power vs thermal ownership be separated?",
    subsystem: "",
  },
  {
    label: "Insufficient Evidence Check",
    question: "Could an uncalibrated solar sail propellant valve explain a sudden drop?",
    subsystem: "",
  },
];

function indexStatusVariant(status) {
  if (status === "READY") return "nominal";
  if (status === "MISSING") return "warning";
  return "critical";
}

function generationStatusBadge(status) {
  if (status === "GENERATED") return { variant: "nominal", label: "LLM GENERATED (GROUNDED)" };
  if (status === "LLM_UNAVAILABLE") return { variant: "warning", label: "RETRIEVAL ONLY // LLM UNAVAILABLE" };
  if (status === "INSUFFICIENT_EVIDENCE") return { variant: "warning", label: "INSUFFICIENT EVIDENCE" };
  if (status === "MALFORMED_LLM_RESPONSE") return { variant: "critical", label: "MALFORMED LLM OUTPUT" };
  if (status === "INDEX_UNAVAILABLE") return { variant: "critical", label: "INDEX UNAVAILABLE" };
  return { variant: "critical", label: status || "ERROR" };
}

export default function AICopilot({ stream }) {
  const { alerts = [], correlations = [] } = stream || {};

  const [statusData, setStatusData] = useState(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState(null);
  const [reindexing, setReindexing] = useState(false);

  const [question, setQuestion] = useState("");
  const [subsystem, setSubsystem] = useState("");
  const [anomalyId, setAnomalyId] = useState("");
  const [selectedAlertId, setSelectedAlertId] = useState("");
  const [selectedCorrelationId, setSelectedCorrelationId] = useState("");
  const [topK, setTopK] = useState(5);

  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState(null);
  const [responseData, setResponseData] = useState(null);
  const [expandedChunkId, setExpandedChunkId] = useState(null);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    const res = await fetchCopilotStatus();
    if (res.ok && res.data) {
      setStatusData(res.data);
      setStatusError(null);
    } else {
      setStatusError(res.error || "Unable to inspect RAG index status");
    }
    setStatusLoading(false);
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleReindex = async () => {
    setReindexing(true);
    setStatusError(null);
    const res = await reindexCopilot();
    if (res.ok && res.data) {
      setStatusData(res.data);
    } else {
      setStatusError(res.error || "Failed to rebuild FAISS index");
    }
    setReindexing(false);
  };

  const submitQuestion = async (overrideQuestion = null, overrideSubsystem = null) => {
    const qText = (overrideQuestion ?? question).trim();
    const subFilter = overrideSubsystem !== null ? overrideSubsystem : subsystem;
    if (!qText) {
      setAskError("Enter an operational question or select a suggested query.");
      return;
    }

    setAsking(true);
    setAskError(null);
    const res = await askCopilot({
      question: qText,
      satellite_id: "SAT-01",
      subsystem: subFilter || null,
      anomaly_id: anomalyId.trim() || null,
      alert_id: selectedAlertId || null,
      correlation_id: selectedCorrelationId || null,
      top_k: Number(topK) || 5,
      include_live_telemetry: true,
    });

    if (res.ok && res.data) {
      setResponseData(res.data);
      const firstChunk = res.data.retrieved_evidence?.[0]?.chunk_id || null;
      setExpandedChunkId(firstChunk);
    } else {
      setAskError(res.error || "Copilot request failed");
    }
    setAsking(false);
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    await submitQuestion();
  };

  const handleSuggestedClick = async (preset) => {
    setQuestion(preset.question);
    setSubsystem(preset.subsystem);
    setAnomalyId("");
    await submitQuestion(preset.question, preset.subsystem);
  };

  const genBadge = responseData ? generationStatusBadge(responseData.generation_status) : null;

  return (
    <div className="space-y-6">
      {/* Grounding & Epistemic Safety Notice */}
      <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <Bot className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-cyan-100">
              Evidence-Linked RAG + AI Copilot (Investigative Assistance Only)
            </div>
            <p className="text-xs text-cyan-100/80 mt-0.5">
              Grounded strictly in the three approved troubleshooting runbooks (`ATT-RB-001`, `THM-RB-001`,
              `BAT-RB-001`) and verified `SAT-01` detector telemetry. Statistical detection stays authoritative;
              correlation never proves causation; no autonomous spacecraft commands are generated.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          {statusData && (
            <>
              <StatusBadge
                variant={indexStatusVariant(statusData.index_status)}
                label={`FAISS: ${statusData.index_status} (${statusData.chunk_count} CHUNKS)`}
              />
              <StatusBadge
                variant={statusData.llm_available ? "online" : "warning"}
                label={
                  statusData.llm_available
                    ? `LLM: ${statusData.llm_provider} (${statusData.llm_model})`
                    : "LLM: KEY NOT CONFIGURED"
                }
              />
            </>
          )}
        </div>
      </div>

      {/* RAG Index & Runtime Status Card */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4">
        {statusLoading ? (
          <LoadingState label="Inspecting FAISS vector index and LLM configuration..." />
        ) : statusError ? (
          <ErrorState
            title="Copilot Status Unavailable"
            message={statusError}
            onRetry={loadStatus}
          />
        ) : (
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1">
              <div className="rounded border border-slate-800/80 bg-[#070b15] px-3 py-2">
                <div className="text-[10px] font-mono uppercase text-slate-500">Runbooks</div>
                <div className="text-sm font-mono text-slate-100 mt-0.5">
                  {statusData.document_count} Documents
                </div>
              </div>
              <div className="rounded border border-slate-800/80 bg-[#070b15] px-3 py-2">
                <div className="text-[10px] font-mono uppercase text-slate-500">Indexed Chunks</div>
                <div className="text-sm font-mono text-slate-100 mt-0.5">
                  {statusData.chunk_count} ({statusData.embedding_dim || "—"}d)
                </div>
              </div>
              <div className="rounded border border-slate-800/80 bg-[#070b15] px-3 py-2">
                <div className="text-[10px] font-mono uppercase text-slate-500">Embedding Model</div>
                <div className="text-xs font-mono text-cyan-300 mt-0.5 truncate" title={statusData.embedding_model}>
                  {statusData.embedding_model}
                </div>
              </div>
              <div className="rounded border border-slate-800/80 bg-[#070b15] px-3 py-2">
                <div className="text-[10px] font-mono uppercase text-slate-500">Supported Channels</div>
                <div className="text-[11px] font-mono text-slate-300 mt-0.5 truncate">
                  {statusData.supported_channels.join(", ")}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleReindex}
                disabled={reindexing}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded border border-cyan-500/40 bg-cyan-500/10 hover:bg-cyan-500/20 text-xs font-mono text-cyan-200 disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${reindexing ? "animate-spin" : ""}`} />
                {reindexing
                  ? "Rebuilding Index..."
                  : statusData?.index_available
                  ? "Rebuild FAISS Index"
                  : "Build FAISS Index"}
              </button>
            </div>
          </div>
        )}
        {statusData && !statusData.llm_available && (
          <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              No LLM API key is configured in backend environment variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`, or
              `LLM_API_KEY`). Vector retrieval against the approved runbooks remains active, and generation will report
              unavailable instead of returning fabricated AI answers.
            </span>
          </div>
        )}
      </div>

      {/* Question Input & Context Controls */}
      <form onSubmit={handleFormSubmit} className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-mono uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Search className="w-4 h-4 text-cyan-400" />
            Operator Triage Query
          </div>
          <div className="text-[11px] text-slate-400">
            Attach optional subsystem filters, anomaly IDs, or live alerts/correlations.
          </div>
        </div>

        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="Ask an investigative question (e.g., What should an operator investigate when battery voltage suddenly drops?)"
          className="w-full rounded-lg border border-slate-700/90 bg-[#070b15] px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/60"
        />

        {/* Context & Retrieval Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-500 mb-1">
              Subsystem Filter
            </label>
            <select
              value={subsystem}
              onChange={(e) => setSubsystem(e.target.value)}
              className="w-full rounded border border-slate-700/90 bg-[#070b15] px-2.5 py-1.5 text-xs text-slate-200"
            >
              <option value="">All Subsystems</option>
              <option value="battery_power">Battery / Power (BAT-RB-001)</option>
              <option value="temperature_thermal">Temperature / Thermal (THM-RB-001)</option>
              <option value="attitude_adcs">Attitude / ADCS (ATT-RB-001)</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-500 mb-1">
              Anomaly ID (Optional)
            </label>
            <input
              type="text"
              value={anomalyId}
              onChange={(e) => setAnomalyId(e.target.value)}
              placeholder="e.g. BAT-001, THM-001, ATT-001"
              className="w-full rounded border border-slate-700/90 bg-[#070b15] px-2.5 py-1.5 text-xs text-slate-200 placeholder:text-slate-600"
            />
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-500 mb-1">
              Persisted Alert Context
            </label>
            <select
              value={selectedAlertId}
              onChange={(e) => setSelectedAlertId(e.target.value)}
              className="w-full rounded border border-slate-700/90 bg-[#070b15] px-2.5 py-1.5 text-xs text-slate-200"
            >
              <option value="">Auto (Latest Open Alert)</option>
              {alerts.slice(0, 20).map((a) => (
                <option key={a.alert_id} value={a.alert_id}>
                  {a.alert_id} · {a.sensor_name} ({a.severity})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-500 mb-1">
              Correlation Context
            </label>
            <select
              value={selectedCorrelationId}
              onChange={(e) => setSelectedCorrelationId(e.target.value)}
              className="w-full rounded border border-slate-700/90 bg-[#070b15] px-2.5 py-1.5 text-xs text-slate-200"
            >
              <option value="">None</option>
              {correlations.slice(0, 20).map((c) => (
                <option key={c.correlation_id} value={c.correlation_id}>
                  {c.correlation_id} · {c.suspected_subsystem} ({c.status})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase text-slate-500 mb-1">
              Top-K Evidence Chunks
            </label>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="w-full rounded border border-slate-700/90 bg-[#070b15] px-2.5 py-1.5 text-xs text-slate-200"
            >
              <option value={3}>Top 3 Chunks</option>
              <option value={5}>Top 5 Chunks</option>
              <option value={8}>Top 8 Chunks</option>
            </select>
          </div>
        </div>

        {/* Suggested Queries */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-mono uppercase text-slate-500">
            Suggested Verification & Triage Questions
          </div>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                disabled={asking}
                onClick={() => handleSuggestedClick(preset)}
                className="text-left text-xs px-2.5 py-1 rounded border border-slate-700/80 bg-[#0b1224] hover:border-cyan-500/40 hover:text-cyan-200 text-slate-300 transition-colors disabled:opacity-50"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 pt-1">
          <div className="text-[11px] text-slate-500 font-mono">
            Supported telemetry context: battery_voltage, temperature, roll, pitch, yaw
          </div>
          <button
            type="submit"
            disabled={asking}
            className="inline-flex items-center gap-2 px-4 py-2 rounded bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/50 text-xs font-mono font-semibold text-cyan-100 disabled:opacity-50"
          >
            {asking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {asking ? "Retrieving & Analyzing..." : "Ask AI Copilot"}
          </button>
        </div>
      </form>

      {/* Request Error */}
      {askError && (
        <ErrorState
          title="Copilot Query Failed"
          message={askError}
          onRetry={() => submitQuestion()}
        />
      )}

      {/* Results Area */}
      {asking && !responseData && (
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-6">
          <LoadingState label="Searching FAISS vector store and validating evidence..." />
        </div>
      )}

      {!asking && !responseData && !askError && (
        <EmptyState
          icon={BookOpen}
          title="No Copilot Query Executed Yet"
          description="Submit an anomaly investigation question or choose one of the suggested queries above to retrieve cited runbook procedures."
        />
      )}

      {responseData && (
        <div className="space-y-6">
          {/* Status & Limitations Banner */}
          <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                {genBadge && <StatusBadge variant={genBadge.variant} label={genBadge.label} />}
                <StatusBadge
                  variant={responseData.evidence_sufficient ? "nominal" : "warning"}
                  label={
                    responseData.evidence_sufficient
                      ? `EVIDENCE SUFFICIENT (${responseData.retrieved_evidence.length} CHUNKS)`
                      : "INSUFFICIENT EVIDENCE"
                  }
                />
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                {new Date(responseData.timestamp).toISOString().replace("T", " ").slice(0, 19)} UTC
              </span>
            </div>

            <div className="text-xs text-slate-300">{responseData.evidence_message}</div>

            {responseData.warnings?.length > 0 && (
              <div className="space-y-1.5">
                {responseData.warnings.map((w, idx) => (
                  <div
                    key={idx}
                    className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 flex items-start gap-2"
                  >
                    <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            {/* Left / Main Structured Answer + Verified Context (7 cols) */}
            <div className="xl:col-span-7 space-y-4">
              {/* Structured Answer Sections (when LLM generated) */}
              {responseData.answer ? (
                <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-5">
                  <div>
                    <div className="text-[11px] font-mono uppercase tracking-wider text-cyan-400">
                      Anomaly Summary
                    </div>
                    <p className="text-sm text-slate-100 mt-1.5 leading-relaxed">
                      {responseData.answer.anomaly_summary}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded border border-emerald-500/25 bg-emerald-500/5 p-3">
                      <div className="text-[11px] font-mono uppercase text-emerald-300 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Verified Observations (Ground Truth)
                      </div>
                      <ul className="mt-2 space-y-1.5 text-xs text-slate-200 list-disc pl-4">
                        {(responseData.answer.verified_observations || []).length > 0 ? (
                          responseData.answer.verified_observations.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))
                        ) : (
                          <li className="text-slate-400 list-none -ml-4">
                            No active telemetry deviations attached to this query.
                          </li>
                        )}
                      </ul>
                    </div>

                    <div className="rounded border border-amber-500/25 bg-amber-500/5 p-3">
                      <div className="text-[11px] font-mono uppercase text-amber-300 flex items-center gap-1.5">
                        <HelpCircle className="w-3.5 h-3.5" />
                        Possible Explanations (Not Confirmed)
                      </div>
                      <ul className="mt-2 space-y-1.5 text-xs text-slate-200 list-disc pl-4">
                        {(responseData.answer.possible_explanations || []).length > 0 ? (
                          responseData.answer.possible_explanations.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))
                        ) : (
                          <li className="text-slate-400 list-none -ml-4">None inferred.</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded border border-slate-800 bg-[#070b15] p-3">
                      <div className="text-[11px] font-mono uppercase text-cyan-300">
                        Supporting Evidence
                      </div>
                      <ul className="mt-2 space-y-1.5 text-xs text-slate-300 list-disc pl-4">
                        {(responseData.answer.supporting_evidence || []).map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded border border-slate-800 bg-[#070b15] p-3">
                      <div className="text-[11px] font-mono uppercase text-rose-300">
                        Contradicting or Missing Evidence
                      </div>
                      <ul className="mt-2 space-y-1.5 text-xs text-slate-300 list-disc pl-4">
                        {(responseData.answer.contradicting_or_missing_evidence || []).length > 0 ? (
                          responseData.answer.contradicting_or_missing_evidence.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))
                        ) : (
                          <li className="text-slate-500 list-none -ml-4">None noted.</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  <div>
                    <div className="text-[11px] font-mono uppercase text-emerald-300">
                      Recommended Investigative Checks (Operator Only)
                    </div>
                    <ol className="mt-2 space-y-1.5 text-xs text-slate-200 list-decimal pl-4">
                      {(responseData.answer.recommended_investigative_checks || []).map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ol>
                  </div>

                  <div className="rounded border border-slate-800 bg-[#070b15] p-3">
                    <div className="text-[11px] font-mono uppercase text-slate-400">
                      Uncertainty & Limitations
                    </div>
                    <ul className="mt-1.5 space-y-1 text-xs text-slate-400 list-disc pl-4">
                      {(responseData.answer.uncertainty_and_limitations || []).map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Inspectable Traceable Citations */}
                  <div>
                    <div className="text-[11px] font-mono uppercase text-cyan-300 mb-2">
                      Source Citations (Traceable to Retrieved Chunks)
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(responseData.answer.citations || []).map((cit) => (
                        <button
                          key={cit.chunk_id}
                          type="button"
                          onClick={() => setExpandedChunkId(cit.chunk_id)}
                          className="text-left rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 px-2.5 py-1.5 text-[11px] font-mono text-cyan-100"
                        >
                          <span className="font-semibold">{cit.runbook_id}</span> · {cit.document_name} ·{" "}
                          {cit.section_heading} ({(cit.similarity_score * 100).toFixed(0)}%)
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 space-y-3">
                  <div className="text-sm font-semibold text-slate-100">
                    {responseData.generation_status === "INSUFFICIENT_EVIDENCE"
                      ? "Insufficient Approved Runbook Evidence"
                      : "LLM Synthesis Unavailable — Inspectable Runbook Retrieval Only"}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {responseData.llm_unavailable_reason ||
                      responseData.evidence_message ||
                      "No LLM synthesis was performed."}
                  </p>
                  <p className="text-[11px] text-slate-500 font-mono">
                    {responseData.disclaimer}
                  </p>
                </div>
              )}

              {/* Verified Telemetry / Detector Context */}
              <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 space-y-3">
                <div className="text-xs font-mono uppercase tracking-wider text-slate-300 flex items-center gap-2">
                  <Database className="w-4 h-4 text-emerald-400" />
                  Verified Telemetry & Alert Context ({responseData.verified_context?.satellite_id})
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  {(responseData.verified_context?.supported_channels || []).map((ch) => {
                    const reading = responseData.verified_context?.latest_readings?.[ch];
                    return (
                      <div
                        key={ch}
                        className="rounded border border-slate-800 bg-[#070b15] px-2.5 py-2"
                      >
                        <div className="text-[10px] font-mono text-slate-500 truncate">{ch}</div>
                        <div className="text-xs font-mono text-slate-100 mt-0.5">
                          {reading && reading.sensor_value !== null && reading.sensor_value !== undefined
                            ? `${Number(reading.sensor_value).toFixed(2)} ${reading.unit || ""}`
                            : "STANDBY"}
                        </div>
                      </div>
                    );
                  })}
                </div>
                {responseData.verified_context?.alert && (
                  <div className="rounded border border-slate-800 bg-[#070b15] p-3 text-xs text-slate-300">
                    <span className="font-mono text-amber-300">
                      Alert {responseData.verified_context.alert.alert_id}:
                    </span>{" "}
                    {responseData.verified_context.alert.title} ({responseData.verified_context.alert.severity} ·{" "}
                    {responseData.verified_context.alert.status})
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Retrieved Evidence Chunks (5 cols) */}
            <div className="xl:col-span-5 space-y-3">
              <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-mono uppercase tracking-wider text-slate-200 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-cyan-400" />
                    Retrieved Runbook Evidence ({responseData.retrieved_evidence.length})
                  </div>
                </div>

                {responseData.retrieved_evidence.length === 0 ? (
                  <div className="text-xs text-slate-400 py-6 text-center">
                    No chunks retrieved for this query and filter combination.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {responseData.retrieved_evidence.map((chunk) => {
                      const isExpanded = expandedChunkId === chunk.chunk_id;
                      return (
                        <div
                          key={chunk.chunk_id}
                          className={`rounded border p-3 transition-colors ${
                            isExpanded
                              ? "border-cyan-500/50 bg-[#0c162c]"
                              : "border-slate-800 bg-[#070b15]"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[11px] font-mono font-semibold text-cyan-300">
                                  {chunk.runbook_id}
                                </span>
                                <span className="text-[10px] font-mono text-slate-500">
                                  {chunk.document_name} (v{chunk.version})
                                </span>
                              </div>
                              <div className="text-xs font-semibold text-slate-100 mt-1">
                                {chunk.section_heading}
                              </div>
                              <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                                subsystem: {chunk.subsystem}
                                {chunk.anomaly_ids?.length > 0
                                  ? ` · anomalies: ${chunk.anomaly_ids.join(", ")}`
                                  : ""}
                              </div>
                            </div>
                            <div className="text-right shrink-0">
                              <div className="text-[11px] font-mono text-emerald-300">
                                sim {(chunk.similarity_score * 100).toFixed(1)}%
                              </div>
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedChunkId(isExpanded ? null : chunk.chunk_id)
                                }
                                className="mt-1 text-[10px] font-mono text-cyan-400 hover:text-cyan-300 underline"
                              >
                                {isExpanded ? "Hide Full Section" : "Inspect Section"}
                              </button>
                            </div>
                          </div>

                          <div className="mt-2 text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
                            {isExpanded ? chunk.text : chunk.snippet}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
