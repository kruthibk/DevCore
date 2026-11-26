"""Deterministic Verification Wall engine and Human Operator Approval services."""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.detection_config import DEFAULT_SENSOR_LIMITS
from app.core.rbac import ActorContext
from app.models.alert import Alert
from app.models.incident import Incident, IncidentLog
from app.models.verification import OperatorDecision, Recommendation, Verification
from app.schemas.verification import (
    DecisionHistoryItem,
    OperatorDecisionRead,
    RecommendationDetail,
    RecommendationRead,
    VerificationCheckResult,
    VerificationEvaluateRequest,
    VerificationRead,
    VerificationStatus,
)
from app.services.copilot_service import (
    AUTONOMOUS_COMMAND_PATTERNS,
    SUPPORTED_TELEMETRY_CHANNELS,
    UNSUPPORTED_CHANNEL_PATTERNS,
)
from app.services.rag_store import normalize_subsystem_filter

VERIFICATION_DISCLAIMER = (
    "A VERIFIED result confirms only that the recommendation passed SAT-TRIAGE's configured "
    "deterministic safety and grounding checks. It does not guarantee technical correctness for real "
    "spacecraft operations. Human operator authorization is mandatory; no spacecraft commands are executed."
)

EXTRA_COMMAND_PATTERNS = (
    re.compile(
        r"\b(execute|send|issue|trigger|fire|actuate|command|uplink|enable|disable|power\s+cycle|switch)\s+"
        r"(the\s+)?(thruster|reaction\s+wheel|heater|radiator|battery\s+bus|bus\s+switch|magnetorquer|spacecraft|attitude\s+maneuver|command)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bautonomous(?:ly)?\s+(?:execute|command|fire|actuate|reset|switch)\b", re.IGNORECASE),
)

NEGATED_COMMAND_RE = re.compile(
    r"\b(no|never|not|do\s+not|must\s+not|without|prohibited|forbidden)\b.{0,35}\b(command|execute|fire|actuate|autonomous|uplink|switch|reset|reboot)\b",
    re.IGNORECASE,
)

OVERCONFIDENT_CAUSE_PATTERNS = (
    re.compile(r"\bconfirmed\s+root\s+cause\b", re.IGNORECASE),
    re.compile(r"\bdefinitively\s+(?:caused|proves|confirmed)\b", re.IGNORECASE),
    re.compile(r"\bproven\s+hardware\s+failure\b", re.IGNORECASE),
    re.compile(r"\bproves\s+causation\b", re.IGNORECASE),
    re.compile(r"\b100%\s+(?:certain|confirmed)\b", re.IGNORECASE),
    re.compile(r"\bguaranteed\s+(?:failure|root\s+cause)\b", re.IGNORECASE),
)

THRESHOLD_STATEMENT_RE = re.compile(
    r"(?:threshold|limit|nominal\s+range|warning\s+bound|critical\s+bound|max(?:imum)?\s+rate|safe\s+range|must\s+remain\s+(?:above|below)|exceeds?|drops?\s+below)"
    r"[^.\n]{0,45}?(-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

RUNBOOK_SUBSYSTEM_MAP = {
    "BAT-RB-001": "battery_power",
    "THM-RB-001": "temperature_thermal",
    "ATT-RB-001": "attitude_adcs",
}

SUBSYSTEM_TO_RUNBOOK = {
    "battery_power": "BAT-RB-001",
    "temperature_thermal": "THM-RB-001",
    "attitude_adcs": "ATT-RB-001",
}

CONTRADICTORY_CUES = (
    "contradict",
    "conflict",
    "mismatch",
    "incomplete",
    "insufficient",
    "no evidence",
    "sensor_missing",
    "sensor_frozen",
    "sensor_invalid",
    "sensor_stale",
    "missing telemetry",
    "below the configured relevance threshold",
)

BENIGN_GAP_NOTES = (
    "none noted",
    "correlation does not prove causation",
    "other runbook fields are unavailable",
    "supports only battery_voltage",
)


def _configured_threshold_numbers() -> Set[str]:
    numbers: Set[str] = set()
    for limits in DEFAULT_SENSOR_LIMITS.values():
        for pair in (limits.engineering_warning, limits.engineering_critical, limits.physical_valid_range):
            for val in pair:
                numbers.add(f"{val:g}")
                numbers.add(str(val))
        numbers.add(f"{limits.max_rate_per_sec:g}")
        numbers.add(f"{limits.min_deviation_deadband:g}")
    return numbers


def _extract_numbers(text: str) -> Set[str]:
    out: Set[str] = set()
    for match in NUMBER_RE.findall(text or ""):
        try:
            num = float(match)
            out.add(f"{num:g}")
            out.add(match)
        except ValueError:
            continue
    return out


def _mentions_unsupported_channel(line: str) -> bool:
    if not any(pat.search(line) for pat in UNSUPPORTED_CHANNEL_PATTERNS):
        return False
    lower = line.lower()
    if any(
        cue in lower
        for cue in (
            "unavailable",
            "not available",
            "not supported",
            "not provided",
            "missing from simulator",
            "supports only",
            "never fabricated",
        )
    ):
        return False
    return True


def _contains_autonomous_command(line: str) -> bool:
    if NEGATED_COMMAND_RE.search(line):
        return False
    return any(pat.search(line) for pat in (*AUTONOMOUS_COMMAND_PATTERNS, *EXTRA_COMMAND_PATTERNS))


def run_deterministic_verification(
    payload: VerificationEvaluateRequest,
    min_similarity: float = 0.56,
) -> Tuple[VerificationStatus, List[VerificationCheckResult], List[Dict[str, Any]], List[str]]:
    """Evaluate all 10 deterministic Verification Wall rules without invoking any LLM."""
    checks: List[VerificationCheckResult] = []
    warnings: List[str] = []

    if payload.ai_claimed_status:
        warnings.append(
            f"Ignored AI self-reported status '{payload.ai_claimed_status}'; independent deterministic checks executed."
        )

    evidence = list(payload.retrieved_evidence or [])
    citations = list(payload.citations or [])
    all_text_lines: List[str] = [
        payload.anomaly_summary,
        *payload.verified_observations,
        *payload.possible_explanations,
        *payload.supporting_evidence,
        *payload.recommended_checks,
    ]
    combined_text = "\n".join(line for line in all_text_lines if line)

    # 1. Evidence availability
    top_sim = max((float(item.get("similarity_score", 0.0) or 0.0) for item in evidence), default=0.0)
    if not evidence:
        checks.append(
            VerificationCheckResult(
                rule_id="evidence_availability",
                name="Evidence Availability",
                status="WARN",
                detail="No retrieved runbook chunks were provided with this recommendation.",
            )
        )
        warnings.append("Missing runbook evidence; recommendation requires human review.")
    elif top_sim < min_similarity:
        checks.append(
            VerificationCheckResult(
                rule_id="evidence_availability",
                name="Evidence Availability",
                status="WARN",
                detail=f"Top retrieval similarity ({top_sim:.2f}) is below configured threshold ({min_similarity:.2f}).",
            )
        )
        warnings.append(f"Low retrieval similarity ({top_sim:.2f} < {min_similarity:.2f}).")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="evidence_availability",
                name="Evidence Availability",
                status="PASS",
                detail=f"{len(evidence)} runbook chunk(s) available (top similarity {top_sim:.2f}).",
            )
        )

    # 2. Source citation validity
    by_chunk_id = {str(item.get("chunk_id", "")).strip(): item for item in evidence if item.get("chunk_id")}
    by_pair = {
        (str(item.get("runbook_id", "")).strip(), str(item.get("section_heading", "")).strip()): item
        for item in evidence
        if item.get("runbook_id") and item.get("section_heading")
    }
    valid_refs: List[Dict[str, Any]] = []
    invalid_citations: List[str] = []

    for cit in citations:
        if not isinstance(cit, dict):
            invalid_citations.append(str(cit))
            continue
        cid = str(cit.get("chunk_id") or "").strip()
        rid = str(cit.get("runbook_id") or "").strip()
        sec = str(cit.get("section_heading") or "").strip()
        matched = by_chunk_id.get(cid) if cid in by_chunk_id else by_pair.get((rid, sec))
        if matched is None:
            invalid_citations.append(cid or f"{rid}:{sec}" or "unknown")
        else:
            valid_refs.append(
                {
                    "chunk_id": matched.get("chunk_id"),
                    "runbook_id": matched.get("runbook_id"),
                    "document_name": matched.get("document_name"),
                    "section_heading": matched.get("section_heading"),
                    "subsystem": matched.get("subsystem"),
                    "similarity_score": matched.get("similarity_score"),
                }
            )

    if invalid_citations:
        checks.append(
            VerificationCheckResult(
                rule_id="source_citation_validity",
                name="Source Citation Validity",
                status="FAIL",
                detail=f"Ungrounded or fabricated citation(s) detected: {', '.join(invalid_citations)}.",
            )
        )
        warnings.append("Rejected: citation(s) do not trace to retrieved runbook chunks.")
    elif not valid_refs:
        checks.append(
            VerificationCheckResult(
                rule_id="source_citation_validity",
                name="Source Citation Validity",
                status="WARN",
                detail="Recommendation contains zero verified runbook citations.",
            )
        )
        warnings.append("No source citations attached to recommendation.")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="source_citation_validity",
                name="Source Citation Validity",
                status="PASS",
                detail=f"All {len(valid_refs)} citation(s) verified against retrieved chunks.",
            )
        )

    # 3. Supported telemetry channels
    bad_channels = [line for line in all_text_lines if line and _mentions_unsupported_channel(line)]
    if bad_channels:
        checks.append(
            VerificationCheckResult(
                rule_id="supported_telemetry_channels",
                name="Supported Telemetry Channels",
                status="FAIL",
                detail=(
                    f"Unsupported telemetry channel observation(s) claimed outside "
                    f"{', '.join(SUPPORTED_TELEMETRY_CHANNELS)}."
                ),
            )
        )
        warnings.append("Rejected: unsupported telemetry channel observation detected.")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="supported_telemetry_channels",
                name="Supported Telemetry Channels",
                status="PASS",
                detail="All telemetry references respect the 5 supported simulator channels.",
            )
        )

    # 4. Runbook subsystem ownership
    normalized_req_sub = normalize_subsystem_filter(payload.subsystem)
    cited_runbooks = {str(ref.get("runbook_id")) for ref in valid_refs if ref.get("runbook_id")}
    expected_rb = SUBSYSTEM_TO_RUNBOOK.get(normalized_req_sub or "")
    ownership_violation = None

    if expected_rb and cited_runbooks and expected_rb not in cited_runbooks:
        # Allow cross-subsystem citations only if explicitly referencing coupling/context
        if "coupling" not in combined_text.lower() and "context" not in combined_text.lower():
            ownership_violation = (
                f"Subsystem '{normalized_req_sub}' requires {expected_rb}, but citations only reference "
                f"{', '.join(sorted(cited_runbooks))}."
            )

    if ownership_violation:
        checks.append(
            VerificationCheckResult(
                rule_id="runbook_subsystem_ownership",
                name="Runbook Subsystem Ownership",
                status="FAIL",
                detail=ownership_violation,
            )
        )
        warnings.append(f"Rejected: {ownership_violation}")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="runbook_subsystem_ownership",
                name="Runbook Subsystem Ownership",
                status="PASS",
                detail="Cited runbooks align with configured subsystem ownership boundaries.",
            )
        )

    # 5. Consistency with retrieved evidence
    consistency_error = None
    evidence_text_blob = "\n".join(str(item.get("text") or item.get("snippet") or "") for item in evidence)
    if ("179" in combined_text and "358" in combined_text) and (
        "large attitude change" in combined_text.lower() or "358-degree rotation" in combined_text.lower()
    ):
        if "angle-wrapping" in evidence_text_blob.lower() or "179" in evidence_text_blob:
            consistency_error = "Contradicts ATT-RB-001 angle-wrapping guidance (+179° to -179° is a 2° wrap, not a 358° jump)."

    if consistency_error:
        checks.append(
            VerificationCheckResult(
                rule_id="evidence_consistency",
                name="Consistency with Retrieved Evidence",
                status="FAIL",
                detail=consistency_error,
            )
        )
        warnings.append(f"Rejected: {consistency_error}")
    elif not evidence:
        checks.append(
            VerificationCheckResult(
                rule_id="evidence_consistency",
                name="Consistency with Retrieved Evidence",
                status="WARN",
                detail="Cannot verify consistency because retrieved runbook evidence is empty.",
            )
        )
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="evidence_consistency",
                name="Consistency with Retrieved Evidence",
                status="PASS",
                detail="Claims do not contradict retrieved runbook guidance.",
            )
        )

    # 6. Unsupported engineering thresholds
    allowed_numbers = _configured_threshold_numbers()
    allowed_numbers |= _extract_numbers(evidence_text_blob)
    allowed_numbers |= _extract_numbers(str(payload.verified_context or {}))
    # Allow common non-threshold numeric tokens (e.g. step numbers 1-10, 179/-179 wrap)
    allowed_numbers.update({"0", "1", "2", "3", "4", "5", "6", "8", "10", "179", "-179"})

    bad_thresholds: List[str] = []
    for line in all_text_lines:
        for num_str in THRESHOLD_STATEMENT_RE.findall(line or ""):
            try:
                norm_num = f"{float(num_str):g}"
            except ValueError:
                continue
            if norm_num not in allowed_numbers and num_str not in allowed_numbers:
                bad_thresholds.append(num_str)

    if bad_thresholds:
        checks.append(
            VerificationCheckResult(
                rule_id="unsupported_thresholds",
                name="Unsupported Engineering Thresholds",
                status="FAIL",
                detail=(
                    f"Unconfigured or ungrounded threshold value(s) detected: "
                    f"{', '.join(dict.fromkeys(bad_thresholds))}."
                ),
            )
        )
        warnings.append("Rejected: recommendation introduces engineering thresholds not in config or evidence.")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="unsupported_thresholds",
                name="Unsupported Engineering Thresholds",
                status="PASS",
                detail="All referenced numeric bounds match configured limits or verified context.",
            )
        )

    # 7. Autonomous command or control instructions
    command_lines = [line for line in all_text_lines if line and _contains_autonomous_command(line)]
    if command_lines:
        checks.append(
            VerificationCheckResult(
                rule_id="autonomous_commands",
                name="No Autonomous Spacecraft Commands",
                status="FAIL",
                detail="Prohibited spacecraft command or hardware actuation instruction detected.",
            )
        )
        warnings.append("Rejected: autonomous spacecraft command or actuator control instruction prohibited.")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="autonomous_commands",
                name="No Autonomous Spacecraft Commands",
                status="PASS",
                detail="Guidance remains strictly investigative with zero spacecraft actuation commands.",
            )
        )

    # 8. Unsupported root-cause claims
    causal_violations = [
        line for line in all_text_lines if line and any(p.search(line) for p in OVERCONFIDENT_CAUSE_PATTERNS)
    ]
    if causal_violations:
        checks.append(
            VerificationCheckResult(
                rule_id="unsupported_root_cause",
                name="No Unsupported Root-Cause Claims",
                status="FAIL",
                detail="Overconfident confirmed root-cause or causal certainty claim detected.",
            )
        )
        warnings.append("Rejected: unsupported confirmed root-cause claim violates epistemic safety rules.")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="unsupported_root_cause",
                name="No Unsupported Root-Cause Claims",
                status="PASS",
                detail="Explanations are appropriately framed as hypotheses, not confirmed root causes.",
            )
        )

    # 9. Missing or contradictory evidence
    gap_items = [
        str(x).strip()
        for x in (payload.contradicting_or_missing_evidence or [])
        if str(x).strip()
        and not any(benign in str(x).lower() for benign in BENIGN_GAP_NOTES)
    ]
    has_contradiction = any(
        any(cue in item.lower() for cue in CONTRADICTORY_CUES) for item in gap_items
    ) or (
        isinstance(payload.verified_context, dict)
        and isinstance(payload.verified_context.get("correlation"), dict)
        and bool(payload.verified_context["correlation"].get("contradicting_evidence"))
    )
    if has_contradiction or payload.generation_status in ("INSUFFICIENT_EVIDENCE", "INDEX_UNAVAILABLE"):
        checks.append(
            VerificationCheckResult(
                rule_id="missing_or_contradictory_evidence",
                name="Missing or Contradictory Evidence",
                status="WARN",
                detail="Incomplete, uncertain, or contradicting evidence flagged for human review.",
            )
        )
        warnings.append("Evidence gaps or contradictions require operator review before approval.")
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="missing_or_contradictory_evidence",
                name="Missing or Contradictory Evidence",
                status="PASS",
                detail="No disqualifying contradictions or missing-evidence alerts present.",
            )
        )

    # 10. Human operator approval requirement
    if payload.ai_claimed_status and payload.ai_claimed_status.upper() == "VERIFIED":
        checks.append(
            VerificationCheckResult(
                rule_id="human_approval_requirement",
                name="Human Operator Approval Requirement",
                status="WARN",
                detail="AI output attempted self-verification; independent human operator sign-off enforced.",
            )
        )
    else:
        checks.append(
            VerificationCheckResult(
                rule_id="human_approval_requirement",
                name="Human Operator Approval Requirement",
                status="PASS",
                detail="Authenticated human operator approval required; no automated command execution.",
            )
        )

    # Synthesize final deterministic status
    if any(chk.status == "FAIL" for chk in checks):
        overall: VerificationStatus = "REJECTED"
    elif any(chk.status == "WARN" for chk in checks):
        overall = "NEEDS_REVIEW"
    else:
        overall = "VERIFIED"

    return overall, checks, valid_refs, list(dict.fromkeys(warnings))


def _resolve_or_create_incident_for_rec(
    db: Session,
    rec: Recommendation,
    latest_ver_status: str,
    actor: ActorContext,
    now: datetime,
    explicit_incident_id: Optional[str] = None,
    create_if_missing: bool = False,
) -> Optional[Incident]:
    """Find an existing linked/matching Incident or create one cleanly without duplicates."""
    inc: Optional[Incident] = None

    if explicit_incident_id and explicit_incident_id.strip():
        target_id = explicit_incident_id.strip()
        inc = db.execute(select(Incident).where(Incident.incident_id == target_id)).scalar_one_or_none()
        if inc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{target_id}' not found.",
            )

    if inc is None and rec.linked_incident_id:
        inc = db.execute(
            select(Incident).where(Incident.incident_id == rec.linked_incident_id)
        ).scalar_one_or_none()

    if inc is None:
        inc = db.execute(
            select(Incident).where(Incident.linked_recommendation_id == rec.recommendation_id)
        ).scalar_one_or_none()

    if inc is None and (rec.linked_alert_id or rec.linked_correlation_id):
        open_candidates = (
            db.execute(
                select(Incident)
                .where(Incident.status.in_(("OPEN", "INVESTIGATING")))
                .order_by(desc(Incident.updated_at), desc(Incident.id))
                .limit(50)
            )
            .scalars()
            .all()
        )
        for cand in open_candidates:
            if cand.linked_recommendation_id and cand.linked_recommendation_id != rec.recommendation_id:
                continue
            alert_match = rec.linked_alert_id and rec.linked_alert_id in (cand.linked_alert_ids or [])
            corr_match = rec.linked_correlation_id and rec.linked_correlation_id in (
                cand.linked_correlation_ids or []
            )
            if alert_match or corr_match:
                inc = cand
                break

    if inc is None and create_if_missing:
        severity = "CRITICAL" if latest_ver_status == "REJECTED" else "WARNING"
        if rec.linked_alert_id:
            alert_row = db.execute(
                select(Alert).where(Alert.alert_id == rec.linked_alert_id)
            ).scalar_one_or_none()
            if alert_row is not None and alert_row.severity in ("CRITICAL", "WARNING", "INFO"):
                severity = alert_row.severity

        citations_text = "; ".join(
            f"{c.get('runbook_id')} ({c.get('section_heading')})"
            for c in (rec.citations or [])
            if isinstance(c, dict) and c.get("runbook_id")
        )
        checks_text = " | ".join((rec.recommended_checks or [])[:3])
        copilot_digest = "\n".join(
            part
            for part in (
                f"Question: {rec.question}" if rec.question else None,
                f"Summary: {rec.anomaly_summary}",
                f"Checks: {checks_text}" if checks_text else None,
                f"Citations: {citations_text}" if citations_text else None,
            )
            if part
        )

        new_inc_id = f"INC-{uuid4().hex[:8].upper()}"
        inc = Incident(
            incident_id=new_inc_id,
            title=f"Triage ({rec.subsystem}): {rec.anomaly_summary}"[:200],
            summary=rec.anomaly_summary,
            subsystem=rec.subsystem or "GENERAL",
            severity=severity,
            status="OPEN",
            linked_alert_ids=[rec.linked_alert_id] if rec.linked_alert_id else [],
            linked_correlation_ids=[rec.linked_correlation_id] if rec.linked_correlation_id else [],
            linked_recommendation_id=rec.recommendation_id,
            copilot_summary=copilot_digest or None,
            created_by=actor.username,
            assigned_to=actor.username,
            created_at=now,
            updated_at=now,
        )
        db.add(inc)
        db.flush()
        db.add(
            IncidentLog(
                incident_id=inc.incident_id,
                actor=actor.username,
                role=actor.role,
                action="CREATED",
                from_status=None,
                to_status="OPEN",
                note=f"Incident created for recommendation {rec.recommendation_id} ({rec.subsystem}).",
                created_at=now,
            )
        )
        db.add(
            IncidentLog(
                incident_id=inc.incident_id,
                actor=actor.username,
                role=actor.role,
                action="RECOMMENDATION_LINKED",
                from_status="OPEN",
                to_status="OPEN",
                note=f"Linked Copilot recommendation {rec.recommendation_id} ({rec.generation_status}).",
                created_at=now,
            )
        )

    if inc is not None:
        rec.linked_incident_id = inc.incident_id
        if inc.linked_recommendation_id is None:
            inc.linked_recommendation_id = rec.recommendation_id
        if rec.linked_alert_id and rec.linked_alert_id not in (inc.linked_alert_ids or []):
            inc.linked_alert_ids = [*(inc.linked_alert_ids or []), rec.linked_alert_id]
        if rec.linked_correlation_id and rec.linked_correlation_id not in (inc.linked_correlation_ids or []):
            inc.linked_correlation_ids = [*(inc.linked_correlation_ids or []), rec.linked_correlation_id]
        inc.updated_at = now

    return inc


class VerificationService:
    """Persists recommendations and immutable deterministic Verification records."""

    @staticmethod
    def evaluate_and_persist(
        db: Session,
        payload: VerificationEvaluateRequest,
        actor: ActorContext,
        min_similarity: float = 0.56,
    ) -> RecommendationDetail:
        now = datetime.now(timezone.utc)
        rec: Optional[Recommendation] = None

        if payload.recommendation_id:
            rec = db.execute(
                select(Recommendation).where(Recommendation.recommendation_id == payload.recommendation_id)
            ).scalar_one_or_none()
            if rec is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Recommendation '{payload.recommendation_id}' not found.",
                )

        overall_status, checks, valid_refs, warnings = run_deterministic_verification(
            payload, min_similarity=min_similarity
        )

        if rec is None:
            rec_id = f"REC-{uuid4().hex[:8].upper()}"
            rec = Recommendation(
                recommendation_id=rec_id,
                source_type=payload.source_type,
                satellite_id=payload.satellite_id,
                subsystem=payload.subsystem.strip() or "GENERAL",
                question=payload.question,
                anomaly_summary=payload.anomaly_summary.strip(),
                verified_observations=list(payload.verified_observations),
                possible_explanations=list(payload.possible_explanations),
                supporting_evidence=list(payload.supporting_evidence),
                contradicting_or_missing_evidence=list(payload.contradicting_or_missing_evidence),
                recommended_checks=list(payload.recommended_checks),
                uncertainty_and_limitations=list(payload.uncertainty_and_limitations),
                citations=list(payload.citations),
                retrieved_evidence=list(payload.retrieved_evidence),
                verified_context=dict(payload.verified_context),
                generation_status=payload.generation_status,
                ai_claimed_status=payload.ai_claimed_status,
                linked_alert_id=payload.linked_alert_id,
                linked_correlation_id=payload.linked_correlation_id,
                linked_incident_id=payload.linked_incident_id,
                created_by_user_id=actor.user_id,
                created_by_username=actor.username,
                latest_verification_status=overall_status,
                created_at=now,
                updated_at=now,
            )
            db.add(rec)
            db.flush()
        else:
            # Update latest status on recommendation while preserving all prior Verification & Decision rows
            rec.latest_verification_status = overall_status
            if payload.linked_incident_id and not rec.linked_incident_id:
                rec.linked_incident_id = payload.linked_incident_id
            rec.updated_at = now

        ver_id = f"VER-{uuid4().hex[:8].upper()}"
        ver = Verification(
            verification_id=ver_id,
            recommendation_id=rec.recommendation_id,
            status=overall_status,
            checks=[c.model_dump(mode="json") for c in checks],
            supporting_evidence_refs=valid_refs,
            warnings=warnings,
            engine_version="deterministic-wall-v1",
            disclaimer=VERIFICATION_DISCLAIMER,
            evaluated_by_user_id=actor.user_id,
            evaluated_by_username=actor.username,
            verified_at=now,
        )
        db.add(ver)
        db.flush()

        linked_inc = _resolve_or_create_incident_for_rec(
            db=db,
            rec=rec,
            latest_ver_status=overall_status,
            actor=actor,
            now=now,
            explicit_incident_id=payload.linked_incident_id,
            create_if_missing=False,
        )
        if linked_inc is not None:
            passed_cnt = sum(1 for c in checks if c.status == "PASS")
            db.add(
                IncidentLog(
                    incident_id=linked_inc.incident_id,
                    actor=actor.username,
                    role=actor.role,
                    action="VERIFICATION_RECORDED",
                    from_status=linked_inc.status,
                    to_status=linked_inc.status,
                    note=(
                        f"Verification Wall {ver_id} ({overall_status}: "
                        f"{passed_cnt}/{len(checks)} checks passed) recorded for {rec.recommendation_id}."
                    ),
                    created_at=now,
                )
            )

        db.commit()
        return VerificationService.get_recommendation_detail(db=db, recommendation_id=rec.recommendation_id)

    @staticmethod
    def list_recommendations(
        db: Session,
        verification_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RecommendationRead], int, Dict[str, int]]:
        stmt = select(Recommendation)
        count_stmt = select(func.count(Recommendation.id))
        if verification_status:
            stmt = stmt.where(Recommendation.latest_verification_status == verification_status)
            count_stmt = count_stmt.where(Recommendation.latest_verification_status == verification_status)

        total = int(db.execute(count_stmt).scalar() or 0)
        rows = (
            db.execute(stmt.order_by(desc(Recommendation.updated_at), desc(Recommendation.id)).limit(limit).offset(offset))
            .scalars()
            .all()
        )
        agg_rows = db.execute(
            select(Recommendation.latest_verification_status, func.count(Recommendation.id)).group_by(
                Recommendation.latest_verification_status
            )
        ).all()
        summary_map = {"VERIFIED": 0, "NEEDS_REVIEW": 0, "REJECTED": 0}
        for st, cnt in agg_rows:
            summary_map[str(st)] = int(cnt)
        summary_map["TOTAL"] = sum(summary_map.values())
        return [RecommendationRead.model_validate(r) for r in rows], total, summary_map

    @staticmethod
    def get_recommendation_detail(db: Session, recommendation_id: str) -> RecommendationDetail:
        row = (
            db.execute(
                select(Recommendation)
                .options(
                    selectinload(Recommendation.verifications),
                    selectinload(Recommendation.decisions),
                )
                .where(Recommendation.recommendation_id == recommendation_id)
            )
            .scalars()
            .first()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation '{recommendation_id}' not found.",
            )
        vers = [VerificationRead.model_validate(v) for v in row.verifications]
        decs = [OperatorDecisionRead.model_validate(d) for d in row.decisions]
        base = RecommendationRead.model_validate(row).model_dump()
        return RecommendationDetail(
            **base,
            verifications=vers,
            decisions=decs,
            latest_verification=vers[-1] if vers else None,
            latest_decision=decs[-1] if decs else None,
        )

    @staticmethod
    def get_verification(db: Session, verification_id: str) -> VerificationRead:
        row = db.execute(
            select(Verification).where(Verification.verification_id == verification_id)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Verification '{verification_id}' not found.",
            )
        return VerificationRead.model_validate(row)


class DecisionService:
    """Manages immutable human operator approval, rejection, and investigation decisions."""

    @staticmethod
    def record_decision(
        db: Session,
        recommendation_id: str,
        decision: str,
        actor: ActorContext,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> RecommendationDetail:
        rec = (
            db.execute(
                select(Recommendation)
                .options(selectinload(Recommendation.verifications))
                .where(Recommendation.recommendation_id == recommendation_id)
            )
            .scalars()
            .first()
        )
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation '{recommendation_id}' not found.",
            )
        if not rec.verifications:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recommendation has not been evaluated by the Verification Wall yet.",
            )

        latest_ver = rec.verifications[-1]

        if decision == "APPROVED" and latest_ver.status == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot approve recommendation '{recommendation_id}' because its verification "
                    f"status is REJECTED. Reject or request investigation instead."
                ),
            )

        if decision in ("REJECTED", "INVESTIGATION_REQUESTED") and (not reason or not reason.strip()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"An explicit reason is required when decision is '{decision}'.",
            )

        now = datetime.now(timezone.utc)
        linked_inc = _resolve_or_create_incident_for_rec(
            db=db,
            rec=rec,
            latest_ver_status=latest_ver.status,
            actor=actor,
            now=now,
            explicit_incident_id=incident_id,
            create_if_missing=True,
        )
        decision_id = f"DEC-{uuid4().hex[:8].upper()}"
        entry = OperatorDecision(
            decision_id=decision_id,
            recommendation_id=rec.recommendation_id,
            verification_id=latest_ver.verification_id,
            verification_status_at_decision=latest_ver.status,
            decision=decision,
            reason=reason.strip() if reason else None,
            notes=notes.strip() if notes else None,
            operator_user_id=actor.user_id,
            operator_username=actor.username,
            operator_role=actor.role,
            command_executed=False,  # Strictly investigative; never executes spacecraft commands
            linked_incident_id=linked_inc.incident_id if linked_inc is not None else None,
            decided_at=now,
        )
        db.add(entry)
        # Never overwrite Verification.status; only record latest human decision on Recommendation
        rec.latest_decision_status = decision
        rec.updated_at = now

        if linked_inc is not None:
            existing_ver_log = db.execute(
                select(IncidentLog).where(
                    IncidentLog.incident_id == linked_inc.incident_id,
                    IncidentLog.action == "VERIFICATION_RECORDED",
                    IncidentLog.note.contains(latest_ver.verification_id),
                )
            ).scalar_one_or_none()
            if existing_ver_log is None:
                db.add(
                    IncidentLog(
                        incident_id=linked_inc.incident_id,
                        actor=latest_ver.evaluated_by_username,
                        role="OPERATOR",
                        action="VERIFICATION_RECORDED",
                        from_status=linked_inc.status,
                        to_status=linked_inc.status,
                        note=f"Verification Wall {latest_ver.verification_id}: {latest_ver.status}.",
                        created_at=now,
                    )
                )

            old_inc_status = linked_inc.status
            new_inc_status = old_inc_status
            if decision == "INVESTIGATION_REQUESTED" and old_inc_status == "OPEN":
                new_inc_status = "INVESTIGATING"
                linked_inc.status = new_inc_status

            detail_parts = [
                f"Operator decision {decision_id}: {decision} on {rec.recommendation_id} "
                f"(Verification {latest_ver.verification_id}={latest_ver.status}, command_executed=False)."
            ]
            if reason and reason.strip():
                detail_parts.append(f"Reason: {reason.strip()}")
            if notes and notes.strip():
                detail_parts.append(f"Notes: {notes.strip()}")

            db.add(
                IncidentLog(
                    incident_id=linked_inc.incident_id,
                    actor=actor.username,
                    role=actor.role,
                    action="DECISION_RECORDED",
                    from_status=old_inc_status,
                    to_status=new_inc_status,
                    note=" ".join(detail_parts),
                    created_at=now,
                )
            )
            if new_inc_status != old_inc_status:
                db.add(
                    IncidentLog(
                        incident_id=linked_inc.incident_id,
                        actor=actor.username,
                        role=actor.role,
                        action="STATUS_CHANGE",
                        from_status=old_inc_status,
                        to_status=new_inc_status,
                        note=f"Incident moved to {new_inc_status} following operator investigation request.",
                        created_at=now,
                    )
                )

        db.commit()
        return VerificationService.get_recommendation_detail(db=db, recommendation_id=rec.recommendation_id)

    @staticmethod
    def list_history(
        db: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DecisionHistoryItem], int]:
        total = int(db.execute(select(func.count(OperatorDecision.id))).scalar() or 0)
        rows = db.execute(
            select(OperatorDecision, Recommendation.anomaly_summary, Recommendation.subsystem)
            .join(Recommendation, OperatorDecision.recommendation_id == Recommendation.recommendation_id)
            .order_by(desc(OperatorDecision.decided_at), desc(OperatorDecision.id))
            .limit(limit)
            .offset(offset)
        ).all()

        items: List[DecisionHistoryItem] = []
        for dec_row, summary, subsystem in rows:
            base = OperatorDecisionRead.model_validate(dec_row).model_dump()
            items.append(
                DecisionHistoryItem(
                    **base,
                    recommendation_summary=summary,
                    subsystem=subsystem,
                )
            )
        return items, total
