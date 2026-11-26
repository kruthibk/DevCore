"""Grounded Evidence-Linked AI Copilot service (strictly investigative, no fabricated data)."""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.alert import Alert
from app.models.correlation import Correlation
from app.schemas.copilot import (
    CitationItem,
    CopilotAnswer,
    CopilotAskRequest,
    CopilotAskResponse,
    RetrievedEvidenceChunk,
    VerifiedTelemetryContext,
)
from app.services.rag_store import RAGVectorStore, rag_vector_store
from app.services.simulator_service import simulator_service

logger = get_logger(__name__)

SUPPORTED_TELEMETRY_CHANNELS = (
    "battery_voltage",
    "temperature",
    "roll",
    "pitch",
    "yaw",
)

UNSUPPORTED_CHANNEL_PATTERNS = (
    re.compile(r"\bbattery[_\s]+current\b", re.IGNORECASE),
    re.compile(r"\bbattery[_\s]+soc\b|\bstate\s+of\s+charge\b", re.IGNORECASE),
    re.compile(r"\bpower[_\s]+bus[_\s]+voltage\b", re.IGNORECASE),
    re.compile(r"\bangular[_\s]+velocity\b", re.IGNORECASE),
    re.compile(r"\battitude[_\s]+error\b", re.IGNORECASE),
    re.compile(r"\breaction[_\s]+wheel[_\s]+speed\b", re.IGNORECASE),
    re.compile(r"\belectronics[_\s]+temperature\b", re.IGNORECASE),
    re.compile(r"\binstrument[_\s]+temperature\b", re.IGNORECASE),
    re.compile(r"\binternal[_\s]+temperature\b", re.IGNORECASE),
    re.compile(r"\bthermal[_\s]+control[_\s]+status\b", re.IGNORECASE),
)

AUTONOMOUS_COMMAND_PATTERNS = (
    re.compile(
        r"\b(execute|send|issue|trigger|fire|command)\s+(the\s+)?"
        r"(thruster|reaction wheel|heater|battery switch|reset|reboot|spacecraft command)\b",
        re.IGNORECASE,
    ),
)

COPILOT_DISCLAIMER = (
    "SAT-TRIAGE AI Copilot provides strictly investigative guidance grounded in approved prototype "
    "runbooks and verified detector telemetry. Statistical detection remains authoritative; correlation "
    "does not prove causation; no autonomous spacecraft commands are permitted."
)

SYSTEM_PROMPT = """You are the SAT-TRIAGE Satellite Telemetry Anomaly Triage Copilot.
You assist human ground operators by synthesizing ONLY the retrieved troubleshooting runbook chunks and the verified telemetry/alert observations provided in the prompt.

STRICT SAFETY AND GROUNDING RULES:
1. Statistical/integrity detectors are authoritative for anomaly detection. Never claim or invent detections outside the provided verified context.
2. NEVER invent telemetry channels, numeric sensor values, timestamps, thresholds, or runbook citations.
3. The simulator supports ONLY these 5 channels: battery_voltage, temperature, roll, pitch, yaw. Never report observed values or measurements for unsupported fields such as battery_current, battery_soc, angular_velocity, attitude_error, reaction_wheel_speed, electronics_temperature, instrument_temperature, internal_temperature, or thermal_control_status.
4. Keep "verified_observations" strictly separated from "possible_explanations". Possible causes are hypotheses, NEVER confirmed hardware failures.
5. Correlation does NOT prove causation. State missing evidence or uncertainty explicitly whenever evidence is incomplete or absent.
6. Recommendations MUST remain investigative only. NEVER generate or recommend autonomous spacecraft commands or hardware actuation.
7. Every item in "citations" MUST use the exact "chunk_id", "runbook_id", "document_name", and "section_heading" from the retrieved runbook evidence provided below.
8. Return ONLY a valid JSON object matching this schema:
{
  "anomaly_summary": "string",
  "verified_observations": ["string"],
  "possible_explanations": ["string"],
  "supporting_evidence": ["string"],
  "contradicting_or_missing_evidence": ["string"],
  "recommended_investigative_checks": ["string"],
  "uncertainty_and_limitations": ["string"],
  "citations": [
    {
      "chunk_id": "string",
      "runbook_id": "string",
      "document_name": "string",
      "section_heading": "string"
    }
  ]
}"""


class LLMClientError(RuntimeError):
    """Raised on upstream LLM HTTP failure or unparseable payload."""


class LLMClient:
    """Async HTTP client supporting Gemini and OpenAI-compatible chat completions."""

    def __init__(self, settings: Settings, http_client: Optional[httpx.AsyncClient] = None) -> None:
        self.settings = settings
        self._http_client = http_client

    def resolve_provider(self) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Resolve (provider_name, api_key, model_name, base_url) without exposing secrets."""
        configured = (self.settings.llm_provider or "auto").strip().lower()
        gemini_key = (self.settings.gemini_api_key or "").strip() or None
        openai_key = (self.settings.openai_api_key or "").strip() or None
        generic_key = (self.settings.llm_api_key or "").strip() or None

        if configured == "gemini" or (configured == "auto" and gemini_key):
            raw_model = (self.settings.llm_model or "").strip() or "gemini-3.1-flash-lite"
            return (
                "gemini",
                gemini_key or generic_key,
                raw_model.removeprefix("models/"),
                (self.settings.llm_base_url or "").strip()
                or "https://generativelanguage.googleapis.com/v1beta",
            )

        if configured in ("openai", "openai_compatible") or (configured == "auto" and (openai_key or generic_key)):
            return (
                "openai_compatible",
                openai_key or generic_key,
                (self.settings.llm_model or "").strip() or "gpt-4o-mini",
                (self.settings.llm_base_url or "").strip() or "https://api.openai.com/v1",
            )

        return ("unconfigured", None, None, None)

    def is_configured(self) -> bool:
        provider, api_key, _, _ = self.resolve_provider()
        return provider != "unconfigured" and bool(api_key)

    async def generate_structured_json(self, user_prompt: str) -> Dict[str, Any]:
        """Invoke the configured LLM provider and return parsed JSON content."""
        provider, api_key, model, base_url = self.resolve_provider()
        if not api_key or not model or not base_url:
            raise LLMClientError("No LLM API key configured.")

        if provider == "gemini":
            return await self._call_gemini(api_key=api_key, model=model, base_url=base_url, user_prompt=user_prompt)
        return await self._call_openai_compatible(
            api_key=api_key,
            model=model,
            base_url=base_url,
            user_prompt=user_prompt,
        )

    async def _post_json(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.llm_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMClientError(f"LLM API request error ({exc.__class__.__name__}): {exc}") from exc

        if response.status_code >= 400:
            detail = ""
            try:
                err_body = response.json()
                err_msg = err_body.get("error", {}).get("message") if isinstance(err_body, dict) else None
                if err_msg:
                    detail = f" ({err_msg[:200]})"
            except Exception:  # noqa: BLE001
                detail = ""
            raise LLMClientError(f"LLM API returned HTTP {response.status_code}{detail}")

        try:
            return response.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMClientError(f"LLM API returned invalid JSON envelope: {exc}") from exc

    async def _call_gemini(
        self,
        api_key: str,
        model: str,
        base_url: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        model_id = model.strip().removeprefix("models/")
        url = f"{base_url.rstrip('/')}/models/{model_id}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }
        data = await self._post_json(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            payload=payload,
        )
        try:
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Malformed Gemini response envelope.") from exc
        return _parse_json_object(raw_text)

    async def _call_openai_compatible(
        self,
        api_key: str,
        model: str,
        base_url: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        data = await self._post_json(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload=payload,
        )
        try:
            raw_text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Malformed OpenAI-compatible response envelope.") from exc
        return _parse_json_object(raw_text)


def _parse_json_object(raw_text: Any) -> Dict[str, Any]:
    if isinstance(raw_text, dict):
        return raw_text
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise LLMClientError("Empty LLM completion text.")
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        parsed = json.loads(cleaned)
    except Exception as exc:  # noqa: BLE001
        raise LLMClientError(f"LLM completion was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMClientError("LLM JSON completion must be an object.")
    return parsed


def _mentions_unsupported_measurement(line: str) -> bool:
    """Detect claims attributing observed/measured values to unsupported simulator fields."""
    if not any(pat.search(line) for pat in UNSUPPORTED_CHANNEL_PATTERNS):
        return False
    lower = line.lower()
    # Allow explicit statements noting unavailability, otherwise flag as fabricated observation.
    if any(cue in lower for cue in ("unavailable", "not available", "not supported", "not provided", "missing from simulator")):
        return False
    return True


def validate_and_sanitize_llm_payload(
    raw_payload: Dict[str, Any],
    retrieved_chunks: List[RetrievedEvidenceChunk],
    verified_context: VerifiedTelemetryContext,
) -> Tuple[CopilotAnswer, List[str]]:
    """Verify citation traceability, prevent channel fabrication, and enforce safety rules."""
    warnings: List[str] = []
    required_summary = raw_payload.get("anomaly_summary")
    if not isinstance(required_summary, str) or not required_summary.strip():
        raise LLMClientError("LLM response missing non-empty 'anomaly_summary'.")

    retrieved_by_id: Dict[str, RetrievedEvidenceChunk] = {c.chunk_id: c for c in retrieved_chunks}
    retrieved_by_pair: Dict[Tuple[str, str], RetrievedEvidenceChunk] = {
        (c.runbook_id, c.section_heading): c for c in retrieved_chunks
    }

    def as_str_list(key: str) -> List[str]:
        val = raw_payload.get(key, [])
        if not isinstance(val, list):
            return []
        return [str(item).strip() for item in val if str(item).strip()]

    raw_verified = as_str_list("verified_observations")
    verified_observations: List[str] = []
    missing_or_contradicting = as_str_list("contradicting_or_missing_evidence")

    for obs in raw_verified:
        if _mentions_unsupported_measurement(obs):
            warnings.append(
                f"Removed unverified claim referencing unsupported telemetry channel: {obs}"
            )
            missing_or_contradicting.append(
                "Simulator supports only battery_voltage, temperature, roll, pitch, and yaw; other runbook fields are unavailable."
            )
            continue
        verified_observations.append(obs)

    # Filter autonomous control commands if any were generated in recommendations
    raw_checks = as_str_list("recommended_investigative_checks")
    safe_checks: List[str] = []
    for chk in raw_checks:
        if any(pat.search(chk) for pat in AUTONOMOUS_COMMAND_PATTERNS):
            warnings.append("Filtered recommendation containing prohibited spacecraft control language.")
            continue
        safe_checks.append(chk)

    # Traceable citation verification strictly against retrieved chunks
    raw_citations = raw_payload.get("citations", [])
    verified_citations: List[CitationItem] = []
    seen_citation_ids = set()

    if isinstance(raw_citations, list):
        for item in raw_citations:
            if not isinstance(item, dict):
                continue
            chunk = None
            cid = str(item.get("chunk_id") or "").strip()
            rid = str(item.get("runbook_id") or "").strip()
            sec = str(item.get("section_heading") or "").strip()
            if cid and cid in retrieved_by_id:
                chunk = retrieved_by_id[cid]
            elif rid and sec and (rid, sec) in retrieved_by_pair:
                chunk = retrieved_by_pair[(rid, sec)]

            if chunk is None:
                warnings.append(
                    f"Dropped ungrounded citation not present in retrieved evidence ({cid or rid or 'unknown'})."
                )
                continue

            if chunk.chunk_id in seen_citation_ids:
                continue
            seen_citation_ids.add(chunk.chunk_id)
            verified_citations.append(
                CitationItem(
                    chunk_id=chunk.chunk_id,
                    runbook_id=chunk.runbook_id,
                    document_name=chunk.document_name,
                    section_heading=chunk.section_heading,
                    subsystem=chunk.subsystem,
                    anomaly_ids=list(chunk.anomaly_ids),
                    similarity_score=chunk.similarity_score,
                )
            )

    uncertainty = as_str_list("uncertainty_and_limitations")
    baseline_note = "Correlation does not prove causation; human operators retain final authority."
    if not any("causation" in u.lower() for u in uncertainty):
        uncertainty.append(baseline_note)

    if not verified_observations and verified_context.latest_readings:
        verified_observations = [
            f"Verified {ch}: {val.get('sensor_value')} {val.get('unit', '')} ({val.get('quality_status')})"
            for ch, val in verified_context.latest_readings.items()
        ]

    # Deduplicate missing_or_contradicting preserving order
    missing_or_contradicting = list(dict.fromkeys(missing_or_contradicting))

    answer = CopilotAnswer(
        anomaly_summary=required_summary.strip(),
        verified_observations=verified_observations,
        possible_explanations=as_str_list("possible_explanations"),
        supporting_evidence=as_str_list("supporting_evidence"),
        contradicting_or_missing_evidence=missing_or_contradicting,
        recommended_investigative_checks=safe_checks,
        uncertainty_and_limitations=uncertainty,
        citations=verified_citations,
    )
    return answer, warnings


def gather_verified_context(
    db: Optional[Session],
    request: CopilotAskRequest,
) -> VerifiedTelemetryContext:
    """Collect verified telemetry (5 supported channels only), alert, and correlation context."""
    notes: List[str] = [
        "Simulator telemetry supports only: battery_voltage, temperature, roll, pitch, yaw.",
        "Unsupported parameters (battery_current, battery_soc, angular_velocity, reaction_wheel_speed, electronics_temperature) are unavailable and never fabricated.",
    ]
    latest_readings: Dict[str, Any] = {}
    if request.include_live_telemetry and db is not None:
        try:
            latest_resp = simulator_service.get_latest_readings(
                db=db,
                satellite_id=request.satellite_id,
            )
            for sensor in SUPPORTED_TELEMETRY_CHANNELS:
                sample = latest_resp.readings.get(sensor)
                if sample is not None:
                    latest_readings[sensor] = {
                        "sensor_value": sample.sensor_value,
                        "unit": sample.unit,
                        "timestamp": sample.timestamp.isoformat(),
                        "quality_status": sample.quality_status,
                    }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to load live telemetry context for copilot: %s", exc)

    alert_ctx: Optional[Dict[str, Any]] = None
    correlation_ctx: Optional[Dict[str, Any]] = None

    if db is not None:
        if request.alert_id:
            alert_row = db.execute(
                select(Alert).where(Alert.alert_id == request.alert_id.strip())
            ).scalar_one_or_none()
            if alert_row is not None:
                alert_ctx = {
                    "alert_id": alert_row.alert_id,
                    "satellite_id": alert_row.satellite_id,
                    "sensor_name": alert_row.sensor_name,
                    "alert_type": alert_row.alert_type,
                    "severity": alert_row.severity,
                    "status": alert_row.status,
                    "title": alert_row.title,
                    "description": alert_row.description,
                    "observed_value": alert_row.observed_value,
                    "expected_range": alert_row.expected_range,
                    "z_score": alert_row.z_score,
                    "reason_code": alert_row.reason_code,
                    "last_detected_at": alert_row.last_detected_at.isoformat(),
                }
        else:
            recent_open = db.execute(
                select(Alert)
                .where(
                    Alert.satellite_id == request.satellite_id,
                    Alert.status.in_(("ACTIVE", "ACKNOWLEDGED")),
                )
                .order_by(desc(Alert.last_detected_at))
                .limit(1)
            ).scalar_one_or_none()
            if recent_open is not None:
                alert_ctx = {
                    "alert_id": recent_open.alert_id,
                    "satellite_id": recent_open.satellite_id,
                    "sensor_name": recent_open.sensor_name,
                    "alert_type": recent_open.alert_type,
                    "severity": recent_open.severity,
                    "status": recent_open.status,
                    "title": recent_open.title,
                    "description": recent_open.description,
                    "observed_value": recent_open.observed_value,
                    "z_score": recent_open.z_score,
                }

        if request.correlation_id:
            corr_row = db.execute(
                select(Correlation).where(Correlation.correlation_id == request.correlation_id.strip())
            ).scalar_one_or_none()
            if corr_row is not None:
                correlation_ctx = {
                    "correlation_id": corr_row.correlation_id,
                    "rule_code": corr_row.rule_code,
                    "suspected_subsystem": corr_row.suspected_subsystem,
                    "hypothesis": corr_row.hypothesis,
                    "related_alert_ids": corr_row.related_alert_ids,
                    "supporting_evidence": corr_row.supporting_evidence,
                    "contradicting_evidence": corr_row.contradicting_evidence,
                    "confidence_score": corr_row.confidence_score,
                    "status": corr_row.status,
                }
                if not request.alert_id and corr_row.related_alert_ids:
                    linked_alert = db.execute(
                        select(Alert).where(Alert.alert_id == corr_row.related_alert_ids[0])
                    ).scalar_one_or_none()
                    if linked_alert is not None:
                        alert_ctx = {
                            "alert_id": linked_alert.alert_id,
                            "satellite_id": linked_alert.satellite_id,
                            "sensor_name": linked_alert.sensor_name,
                            "alert_type": linked_alert.alert_type,
                            "severity": linked_alert.severity,
                            "status": linked_alert.status,
                            "title": linked_alert.title,
                            "description": linked_alert.description,
                            "observed_value": linked_alert.observed_value,
                            "expected_range": linked_alert.expected_range,
                            "z_score": linked_alert.z_score,
                            "reason_code": linked_alert.reason_code,
                            "last_detected_at": linked_alert.last_detected_at.isoformat(),
                        }
        elif alert_ctx is not None:
            open_corrs = (
                db.execute(
                    select(Correlation)
                    .where(
                        Correlation.satellite_id == request.satellite_id,
                        Correlation.status.in_(("ACTIVE", "ACKNOWLEDGED")),
                    )
                    .order_by(desc(Correlation.updated_at))
                    .limit(20)
                )
                .scalars()
                .all()
            )
            matching_corr = next(
                (c for c in open_corrs if alert_ctx["alert_id"] in (c.related_alert_ids or [])),
                None,
            )
            if matching_corr is not None:
                correlation_ctx = {
                    "correlation_id": matching_corr.correlation_id,
                    "rule_code": matching_corr.rule_code,
                    "suspected_subsystem": matching_corr.suspected_subsystem,
                    "hypothesis": matching_corr.hypothesis,
                    "related_alert_ids": matching_corr.related_alert_ids,
                    "supporting_evidence": matching_corr.supporting_evidence,
                    "contradicting_evidence": matching_corr.contradicting_evidence,
                    "confidence_score": matching_corr.confidence_score,
                    "status": matching_corr.status,
                }

    return VerifiedTelemetryContext(
        satellite_id=request.satellite_id,
        supported_channels=list(SUPPORTED_TELEMETRY_CHANNELS),
        latest_readings=latest_readings,
        alert=alert_ctx,
        correlation=correlation_ctx,
        notes=notes,
    )


def _build_llm_user_prompt(
    question: str,
    verified_context: VerifiedTelemetryContext,
    retrieved_chunks: List[RetrievedEvidenceChunk],
) -> str:
    context_json = json.dumps(verified_context.model_dump(mode="json"), indent=2)
    evidence_blocks = []
    for idx, chunk in enumerate(retrieved_chunks, start=1):
        evidence_blocks.append(
            f"--- EVIDENCE {idx} ---\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"runbook_id: {chunk.runbook_id}\n"
            f"document_name: {chunk.document_name}\n"
            f"subsystem: {chunk.subsystem}\n"
            f"anomaly_ids: {', '.join(chunk.anomaly_ids) if chunk.anomaly_ids else 'general'}\n"
            f"section_heading: {chunk.section_heading}\n"
            f"similarity_score: {chunk.similarity_score:.4f}\n"
            f"content:\n{chunk.text}\n"
        )
    return (
        f"OPERATOR QUESTION:\n{question.strip()}\n\n"
        f"VERIFIED TELEMETRY & DETECTOR CONTEXT (Ground Truth):\n{context_json}\n\n"
        f"RETRIEVED APPROVED RUNBOOK EVIDENCE:\n{''.join(evidence_blocks)}\n"
        f"Respond with the required JSON object only."
    )


class CopilotService:
    """Orchestrates verified context loading, FAISS retrieval, and cautious LLM generation."""

    def __init__(
        self,
        vector_store: Optional[RAGVectorStore] = None,
        llm_client: Optional[LLMClient] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.vector_store = vector_store or rag_vector_store
        self.llm_client = llm_client or LLMClient(self.settings)

    def get_status(self) -> Any:
        provider, api_key, model, _ = self.llm_client.resolve_provider()
        return self.vector_store.get_status(
            llm_available=bool(api_key),
            llm_provider=provider,
            llm_model=model,
        )

    def reindex(self) -> Any:
        self.vector_store.rebuild_index()
        return self.get_status()

    async def ask(self, request: CopilotAskRequest, db: Optional[Session] = None) -> CopilotAskResponse:
        now = datetime.now(timezone.utc)
        provider, api_key, model, _ = self.llm_client.resolve_provider()
        llm_available = bool(api_key)
        verified_context = gather_verified_context(db=db, request=request)

        if not self.vector_store.ensure_loaded(auto_build=False):
            status_snapshot = self.get_status()
            return CopilotAskResponse(
                question=request.question,
                generation_status="INDEX_UNAVAILABLE",
                llm_available=llm_available,
                llm_provider=provider,
                llm_model=model,
                llm_unavailable_reason=(
                    None
                    if llm_available
                    else "LLM API key is not configured in environment variables."
                ),
                evidence_sufficient=False,
                evidence_message=status_snapshot.diagnostic_message,
                verified_context=verified_context,
                retrieved_evidence=[],
                answer=None,
                warnings=[status_snapshot.diagnostic_message],
                disclaimer=COPILOT_DISCLAIMER,
                timestamp=now,
            )

        retrieved, evidence_sufficient, evidence_msg = self.vector_store.retrieve(
            query=request.question,
            subsystem=request.subsystem,
            anomaly_id=request.anomaly_id,
            top_k=request.top_k,
        )

        if not evidence_sufficient:
            return CopilotAskResponse(
                question=request.question,
                generation_status="INSUFFICIENT_EVIDENCE",
                llm_available=llm_available,
                llm_provider=provider,
                llm_model=model,
                llm_unavailable_reason=(
                    None
                    if llm_available
                    else "LLM API key is not configured in environment variables."
                ),
                evidence_sufficient=False,
                evidence_message=evidence_msg,
                verified_context=verified_context,
                retrieved_evidence=retrieved,
                answer=None,
                warnings=[evidence_msg],
                disclaimer=COPILOT_DISCLAIMER,
                timestamp=now,
            )

        if not llm_available:
            reason = (
                "No LLM API key is configured (set GEMINI_API_KEY, OPENAI_API_KEY, or LLM_API_KEY). "
                "Semantic retrieval succeeded and returned grounded runbook evidence without fabricated LLM generation."
            )
            return CopilotAskResponse(
                question=request.question,
                generation_status="LLM_UNAVAILABLE",
                llm_available=False,
                llm_provider=provider,
                llm_model=model,
                llm_unavailable_reason=reason,
                evidence_sufficient=True,
                evidence_message=evidence_msg,
                verified_context=verified_context,
                retrieved_evidence=retrieved,
                answer=None,
                warnings=[reason],
                disclaimer=COPILOT_DISCLAIMER,
                timestamp=now,
            )

        prompt = _build_llm_user_prompt(
            question=request.question,
            verified_context=verified_context,
            retrieved_chunks=retrieved,
        )

        try:
            raw_payload = await self.llm_client.generate_structured_json(prompt)
            sanitized_answer, warnings = validate_and_sanitize_llm_payload(
                raw_payload=raw_payload,
                retrieved_chunks=retrieved,
                verified_context=verified_context,
            )
        except LLMClientError as exc:
            msg = str(exc)
            is_malformed = any(
                token in msg.lower()
                for token in ("malformed", "valid json", "missing non-empty", "empty llm", "must be an object")
            )
            return CopilotAskResponse(
                question=request.question,
                generation_status="MALFORMED_LLM_RESPONSE" if is_malformed else "LLM_ERROR",
                llm_available=True,
                llm_provider=provider,
                llm_model=model,
                llm_unavailable_reason=None,
                evidence_sufficient=True,
                evidence_message=evidence_msg,
                verified_context=verified_context,
                retrieved_evidence=retrieved,
                answer=None,
                warnings=[f"LLM generation could not be verified: {msg}. Grounded retrieval evidence remains available below."],
                disclaimer=COPILOT_DISCLAIMER,
                timestamp=now,
            )

        return CopilotAskResponse(
            question=request.question,
            generation_status="GENERATED",
            llm_available=True,
            llm_provider=provider,
            llm_model=model,
            llm_unavailable_reason=None,
            evidence_sufficient=True,
            evidence_message=evidence_msg,
            verified_context=verified_context,
            retrieved_evidence=retrieved,
            answer=sanitized_answer,
            warnings=warnings,
            disclaimer=COPILOT_DISCLAIMER,
            timestamp=now,
        )


def create_default_copilot_service(settings: Optional[Settings] = None) -> CopilotService:
    cfg = settings or get_settings()
    return CopilotService(vector_store=rag_vector_store, llm_client=LLMClient(cfg), settings=cfg)


copilot_service = create_default_copilot_service()
