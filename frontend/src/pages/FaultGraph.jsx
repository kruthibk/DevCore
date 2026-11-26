import { useEffect, useState } from "react";
import {
  Bot,
  CheckCheck,
  FilePlus2,
  GitBranch,
  Info,
  Network,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { createIncident } from "../api/client";
import EmptyState from "../components/common/EmptyState";
import ErrorState from "../components/common/ErrorState";
import LoadingState from "../components/common/LoadingState";
import StatusBadge from "../components/common/StatusBadge";
import CausalGraphCanvas from "../components/faultgraph/CausalGraphCanvas";
import { useAuth } from "../context/AuthContext";

function statusVariant(status) {
  if (status === "ACTIVE") return "critical";
  if (status === "ACKNOWLEDGED") return "warning";
  return "muted";
}

function subsystemToRunbook(subsystem) {
  if (subsystem === "EPS") return "battery_power";
  if (subsystem === "THERMAL") return "temperature_thermal";
  if (subsystem === "ADCS") return "attitude_adcs";
  return "";
}

export default function FaultGraph({ stream }) {
  const { canOperate, role } = useAuth();
  const {
    faultGraph,
    correlations,
    correlationSummary,
    faultGraphLoading,
    faultGraphError,
    graphWindowSeconds,
    updateGraphWindow,
    correlationStatusFilter,
    updateCorrelationStatusFilter,
    refreshFaultGraph,
    pendingCorrelationAction,
    correlationActionError,
    clearCorrelationActionError,
    acknowledgeCorrelation,
    dismissCorrelation,
  } = stream;

  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedCorrelationId, setSelectedCorrelationId] = useState(null);
  const [loggingIncident, setLoggingIncident] = useState(false);
  const [createdIncident, setCreatedIncident] = useState(null);
  const [incidentLogError, setIncidentLogError] = useState(null);

  const handleLogCorrelationIncident = async (corrObj) => {
    if (!corrObj || !canOperate) return;
    setLoggingIncident(true);
    setIncidentLogError(null);
    setCreatedIncident(null);
    const res = await createIncident({
      title: `${corrObj.suspected_subsystem} Correlation: ${corrObj.rule_code}`.slice(0, 200),
      summary: `${corrObj.hypothesis} (${corrObj.grouping_reason})`,
      subsystem: subsystemToRunbook(corrObj.suspected_subsystem) || corrObj.suspected_subsystem || "GENERAL",
      severity: "WARNING",
      linked_alert_ids: corrObj.related_alert_ids || [],
      linked_correlation_ids: [corrObj.correlation_id],
      note: `Promoted from Fault Graph correlation ${corrObj.correlation_id}.`,
    });
    setLoggingIncident(false);
    if (res.ok && res.data) {
      setCreatedIncident(res.data);
    } else {
      setIncidentLogError(res.error || "Failed to log incident");
    }
  };

  useEffect(() => {
    if (correlations.length === 0) {
      setSelectedCorrelationId(null);
      return;
    }
    if (
      !selectedCorrelationId ||
      !correlations.some((c) => c.correlation_id === selectedCorrelationId)
    ) {
      setSelectedCorrelationId(correlations[0].correlation_id);
    }
  }, [correlations, selectedCorrelationId]);

  const selectedCorrelation =
    correlations.find((c) => c.correlation_id === selectedCorrelationId) || null;

  const connectedEdges = selectedNode
    ? (faultGraph?.edges || []).filter(
        (e) => e.source === selectedNode.id || e.target === selectedNode.id
      )
    : [];

  return (
    <div className="space-y-6">
      {/* Header & Caution Banner */}
      <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <GitBranch className="w-5 h-5 text-cyan-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-cyan-100">
              Hybrid Causal Fault Graph & Alert Correlation Engine
            </div>
            <p className="text-xs text-cyan-100/80 mt-0.5">
              {faultGraph?.disclaimer ||
                "Hypotheses identify possible common causes from explicit subsystem dependency rules and temporal proximity. Correlation does not prove causation; human operators retain final authority."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap shrink-0">
          <StatusBadge
            variant="critical"
            label={`Active: ${correlationSummary?.active ?? 0}`}
          />
          <StatusBadge
            variant="warning"
            label={`Ack: ${correlationSummary?.acknowledged ?? 0}`}
          />
          <StatusBadge
            variant="muted"
            label={`Dismissed: ${correlationSummary?.dismissed ?? 0}`}
          />
          {!canOperate && (
            <StatusBadge variant="warning" label={`${role} (READ-ONLY)`} />
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Correlation Window:</span>
            <select
              aria-label="Correlation time window"
              value={graphWindowSeconds}
              onChange={(e) => updateGraphWindow(Number(e.target.value))}
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value={60}>Last 60s</option>
              <option value={120}>Last 120s</option>
              <option value={300}>Last 5 min</option>
              <option value={900}>Last 15 min</option>
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-slate-400">
            <span>Hypothesis Status:</span>
            <select
              aria-label="Filter correlation status"
              value={correlationStatusFilter}
              onChange={(e) => updateCorrelationStatusFilter(e.target.value)}
              className="rounded border border-slate-700 bg-[#050913] px-2 py-1 text-slate-200"
            >
              <option value="">All Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="DISMISSED">DISMISSED</option>
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={() => refreshFaultGraph()}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Refresh Graph</span>
        </button>
      </div>

      {faultGraphError && (
        <ErrorState
          title="Unable to Load Fault Graph"
          message={faultGraphError}
          onRetry={() => refreshFaultGraph()}
        />
      )}

      {correlationActionError && (
        <ErrorState
          title="Correlation Action Failed"
          message={correlationActionError}
          onRetry={clearCorrelationActionError}
        />
      )}

      {/* Interactive Graph + Node Inspector */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 rounded-lg border border-slate-800 bg-[#090f1e] p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Network className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-100">
                Subsystem, Sensor & Alert Dependency Topology
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-500">
              Nodes: {faultGraph?.nodes?.length ?? 0} // Edges: {faultGraph?.edges?.length ?? 0}
            </span>
          </div>

          {faultGraphLoading && !faultGraph ? (
            <LoadingState title="Loading subsystem dependency graph..." subtitle="Querying real Phase 4 alerts and correlation rules." />
          ) : (
            <CausalGraphCanvas
              nodes={faultGraph?.nodes || []}
              edges={faultGraph?.edges || []}
              selectedNodeId={selectedNode?.id}
              onSelectNode={setSelectedNode}
            />
          )}
        </div>

        {/* Selected Node Details */}
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-slate-800">
              <Info className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-100">Graph Node Inspector</h2>
            </div>

            {!selectedNode ? (
              <div className="mt-4 text-xs text-slate-400 leading-relaxed">
                Click any subsystem, sensor, or alert node in the fault graph to inspect its dependency edges and failure modes.
              </div>
            ) : (
              <div className="mt-4 space-y-3 text-xs font-mono">
                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px]">Node</div>
                  <div className="text-cyan-300 font-semibold mt-0.5">{selectedNode.label}</div>
                  <div className="text-slate-400 mt-1">
                    Type: {selectedNode.node_type.toUpperCase()} // Status: {selectedNode.status}
                  </div>
                </div>

                {selectedNode.metadata?.description && (
                  <div className="rounded border border-slate-800 bg-[#060b16] p-3 font-sans text-slate-300">
                    {selectedNode.metadata.description}
                  </div>
                )}

                {Array.isArray(selectedNode.metadata?.failure_modes) && (
                  <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                    <div className="text-slate-500 uppercase text-[10px] mb-1.5">
                      Configured Failure Modes
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedNode.metadata.failure_modes.map((fm) => (
                        <StatusBadge key={fm} variant="muted" label={fm} showDot={false} />
                      ))}
                    </div>
                  </div>
                )}

                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-slate-500 uppercase text-[10px] mb-1.5">
                    Connected Relationships ({connectedEdges.length})
                  </div>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {connectedEdges.map((edge) => (
                      <div key={edge.id} className="text-[11px] text-slate-300">
                        <span className="text-cyan-400">{edge.relationship}</span>:{" "}
                        {edge.source.replace(/^(sub|sensor|alert):/, "")} →{" "}
                        {edge.target.replace(/^(sub|sensor|alert):/, "")}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] font-mono text-slate-500">
            Explicit rule-based dependency graph (no LLM inference)
          </div>
        </div>
      </div>

      {/* Correlation Groups & Root-Cause Hypotheses */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 rounded-lg border border-slate-800 bg-[#090f1e] overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Correlated Alert Groups & Hypotheses ({correlations.length})
            </span>
            <span className="text-[11px] font-mono text-slate-500">
              Possible Common Causes (Not Confirmed Failures)
            </span>
          </div>

          {correlations.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={GitBranch}
                title="No alert correlations recorded yet."
                description="Correlation groups are created automatically when multiple related Phase 4 alerts occur within the configured time window."
                phaseBadge="Evidence-Based Correlation Ready"
              />
            </div>
          ) : (
            <div className="divide-y divide-slate-800/80">
              {correlations.map((corr) => {
                const isSelected = corr.correlation_id === selectedCorrelationId;
                const ackBusy = pendingCorrelationAction === `ack:${corr.correlation_id}`;
                const disBusy = pendingCorrelationAction === `dismiss:${corr.correlation_id}`;
                return (
                  <div
                    key={corr.correlation_id}
                    onClick={() => setSelectedCorrelationId(corr.correlation_id)}
                    className={`p-4 cursor-pointer transition-colors ${
                      isSelected ? "bg-cyan-500/10" : "hover:bg-slate-900/40"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge variant={statusVariant(corr.status)} label={corr.status} />
                        <StatusBadge
                          variant="standby"
                          label={`Subsystem: ${corr.suspected_subsystem}`}
                          showDot={false}
                        />
                        <span className="text-xs font-mono text-cyan-300 font-semibold">
                          {corr.correlation_id}
                        </span>
                      </div>
                      <span className="text-xs font-mono text-slate-300">
                        Illustrative Confidence: {Math.round(corr.confidence_score * 100)}%
                      </span>
                    </div>

                    <p className="text-sm font-medium text-slate-100 mt-2">
                      Possible Cause: {corr.hypothesis}
                    </p>
                    <p className="text-xs font-mono text-slate-400 mt-1">
                      {corr.grouping_reason}
                    </p>

                    <div
                      className="mt-3 flex flex-wrap items-center justify-between gap-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex flex-wrap items-center gap-1.5">
                        {corr.related_alert_ids.map((aid) => (
                          <StatusBadge key={aid} variant="muted" label={aid} showDot={false} />
                        ))}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          disabled={!canOperate || corr.status !== "ACTIVE" || ackBusy || disBusy}
                          title={!canOperate ? "OPERATOR or ADMIN role required" : "Acknowledge correlation"}
                          onClick={() => acknowledgeCorrelation(corr.correlation_id)}
                          className="px-2.5 py-1 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-[11px] font-mono disabled:opacity-35 disabled:cursor-not-allowed"
                        >
                          {ackBusy ? "..." : "Acknowledge"}
                        </button>
                        <button
                          type="button"
                          disabled={!canOperate || corr.status === "DISMISSED" || ackBusy || disBusy}
                          title={!canOperate ? "OPERATOR or ADMIN role required" : "Dismiss correlation"}
                          onClick={() => dismissCorrelation(corr.correlation_id)}
                          className="px-2.5 py-1 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-mono disabled:opacity-35 disabled:cursor-not-allowed"
                        >
                          {disBusy ? "..." : "Dismiss"}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Correlation Evidence & Confidence Panel */}
        <div className="rounded-lg border border-slate-800 bg-[#090f1e] p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-slate-100">
                  Hypothesis Evidence & Confidence
                </h2>
              </div>
              {selectedCorrelation && (
                <StatusBadge
                  variant={statusVariant(selectedCorrelation.status)}
                  label={selectedCorrelation.status}
                />
              )}
            </div>

            {!selectedCorrelation ? (
              <div className="mt-4 text-xs text-slate-400">
                Select a correlation group to inspect supporting evidence, contradicting evidence, and confidence reasoning.
              </div>
            ) : (
              <div className="mt-4 space-y-3 text-xs">
                <div className="rounded border border-slate-800 bg-[#060b16] p-3">
                  <div className="text-[10px] font-mono uppercase text-slate-500">
                    Illustrative Confidence ({Math.round(selectedCorrelation.confidence_score * 100)}%)
                  </div>
                  <div className="text-slate-300 mt-1 leading-relaxed">
                    {selectedCorrelation.confidence_explanation}
                  </div>
                </div>

                <div className="rounded border border-emerald-500/20 bg-emerald-500/5 p-3">
                  <div className="text-[10px] font-mono uppercase text-emerald-300 mb-1.5">
                    Supporting Evidence ({selectedCorrelation.supporting_evidence.length})
                  </div>
                  <ul className="space-y-1.5 text-slate-300 list-disc pl-4">
                    {selectedCorrelation.supporting_evidence.map((item, idx) => (
                      <li key={idx}>{item.summary}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded border border-amber-500/20 bg-amber-500/5 p-3">
                  <div className="text-[10px] font-mono uppercase text-amber-300 mb-1.5">
                    Contradicting / Alternative Evidence ({selectedCorrelation.contradicting_evidence.length})
                  </div>
                  {selectedCorrelation.contradicting_evidence.length === 0 ? (
                    <div className="text-slate-400">None identified in this window.</div>
                  ) : (
                    <ul className="space-y-1.5 text-slate-300 list-disc pl-4">
                      {selectedCorrelation.contradicting_evidence.map((item, idx) => (
                        <li key={idx}>{item.summary}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2 pt-1 font-mono">
                  <button
                    type="button"
                    disabled={
                      !canOperate ||
                      selectedCorrelation.status !== "ACTIVE" ||
                      pendingCorrelationAction === `ack:${selectedCorrelation.correlation_id}`
                    }
                    title={!canOperate ? "OPERATOR or ADMIN role required" : "Acknowledge correlation hypothesis"}
                    onClick={() => acknowledgeCorrelation(selectedCorrelation.correlation_id)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-amber-500/35 bg-amber-500/15 hover:bg-amber-500/25 text-amber-200 disabled:opacity-35 disabled:cursor-not-allowed"
                  >
                    <CheckCheck className="w-3.5 h-3.5" />
                    <span>Acknowledge</span>
                  </button>
                  <button
                    type="button"
                    disabled={
                      !canOperate ||
                      selectedCorrelation.status === "DISMISSED" ||
                      pendingCorrelationAction === `dismiss:${selectedCorrelation.correlation_id}`
                    }
                    title={!canOperate ? "OPERATOR or ADMIN role required" : "Dismiss correlation hypothesis"}
                    onClick={() => dismissCorrelation(selectedCorrelation.correlation_id)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-35 disabled:cursor-not-allowed"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Dismiss</span>
                  </button>
                  <Link
                    to={`/copilot?correlation_id=${encodeURIComponent(
                      selectedCorrelation.correlation_id
                    )}&subsystem=${encodeURIComponent(
                      subsystemToRunbook(selectedCorrelation.suspected_subsystem)
                    )}&question=${encodeURIComponent(
                      `Investigate ${selectedCorrelation.suspected_subsystem} correlation ${selectedCorrelation.correlation_id}: ${selectedCorrelation.hypothesis}`
                    )}`}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-indigo-500/40 bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-100"
                  >
                    <Bot className="w-3.5 h-3.5" />
                    <span>Ask AI Copilot</span>
                  </Link>
                  <button
                    type="button"
                    disabled={!canOperate || loggingIncident}
                    title={!canOperate ? "OPERATOR or ADMIN role required" : "Log Incident from correlation"}
                    onClick={() => handleLogCorrelationIncident(selectedCorrelation)}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-cyan-500/40 bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-100 disabled:opacity-35 disabled:cursor-not-allowed"
                  >
                    <FilePlus2 className="w-3.5 h-3.5" />
                    <span>{loggingIncident ? "Logging..." : "Log Incident"}</span>
                  </button>
                </div>

                {incidentLogError && (
                  <div className="rounded border border-rose-500/35 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                    {incidentLogError}
                  </div>
                )}

                {createdIncident && (
                  <div className="rounded border border-emerald-500/35 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200 flex items-center justify-between gap-2">
                    <span>Logged {createdIncident.incident_id}</span>
                    <Link
                      to={`/incidents?id=${encodeURIComponent(createdIncident.incident_id)}`}
                      className="underline font-semibold text-cyan-300"
                    >
                      Open Incident →
                    </Link>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] font-mono text-slate-500">
            Correlation hypotheses never confirm failure without operator review.
          </div>
        </div>
      </div>
    </div>
  );
}
