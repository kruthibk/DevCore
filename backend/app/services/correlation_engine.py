"""Time-window alert correlation, hybrid causal hypothesis engine, and fault graph builder."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from uuid import uuid4

from fastapi import status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.fault_graph_config import (
    CAUSAL_RULES,
    DEFAULT_CORRELATION_WINDOW_SECONDS,
    SENSOR_TO_PRIMARY_SUBSYSTEM,
    SUBSYSTEM_DEFINITIONS,
    SUBSYSTEM_DEPENDENCY_EDGES,
    CausalRuleDefinition,
)
from app.models.alert import Alert
from app.models.correlation import Correlation
from app.schemas.alerts import AlertRead
from app.schemas.fault_graph import (
    CorrelationDetailResponse,
    CorrelationRead,
    CorrelationStatus,
    CorrelationSummaryCounts,
    FaultGraphResponse,
    GraphEdge,
    GraphNode,
)

PHYSICAL_ALERT_TYPES = {"STATISTICAL_ANOMALY", "RATE_OF_CHANGE", "ENGINEERING_LIMIT"}
INTEGRITY_ALERT_TYPES = {"SENSOR_MISSING", "SENSOR_FROZEN", "SENSOR_INVALID", "SENSOR_STALE"}
SEVERITY_RANK = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}


class CorrelationNotFoundError(AppException):
    """Raised when a correlation_id does not exist."""

    def __init__(self, correlation_id: str) -> None:
        super().__init__(
            message=f"Correlation '{correlation_id}' was not found.",
            code="CORRELATION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@dataclass
class CorrelationCandidate:
    """In-memory causal hypothesis produced before DB deduplication."""

    satellite_id: str
    rule_code: str
    suspected_subsystem: str
    hypothesis: str
    grouping_reason: str
    related_alert_ids: List[str]
    supporting_evidence: List[Dict[str, Any]]
    contradicting_evidence: List[Dict[str, Any]]
    confidence_score: float
    confidence_explanation: str
    window_start: datetime
    window_end: datetime


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_correlations_for_alerts(
    alerts: Sequence[AlertRead],
    satellite_id: str,
    window_seconds: float = DEFAULT_CORRELATION_WINDOW_SECONDS,
    reference_time: Optional[datetime] = None,
) -> List[CorrelationCandidate]:
    """Group related alerts within the configured time window and build causal hypotheses.

    Unrelated alerts (outside time window, different satellite, or uncoupled channels)
    are never merged into the same correlation group.
    """
    sat_alerts = [a for a in alerts if a.satellite_id == satellite_id]
    if len(sat_alerts) < 2:
        return []

    ref_ts = _ensure_utc(
        reference_time
        or max(_ensure_utc(a.last_detected_at) for a in sat_alerts)
    )
    cutoff = ref_ts - timedelta(seconds=window_seconds)

    window_alerts = [
        a for a in sat_alerts
        if cutoff <= _ensure_utc(a.last_detected_at) <= ref_ts
    ]
    if len(window_alerts) < 2:
        return []

    physical_alerts = [a for a in window_alerts if a.alert_type in PHYSICAL_ALERT_TYPES]
    integrity_alerts = [a for a in window_alerts if a.alert_type in INTEGRITY_ALERT_TYPES]

    all_window_sensors: Set[str] = {a.sensor_name for a in window_alerts}
    physical_by_sensor: Dict[str, List[AlertRead]] = {}
    for a in physical_alerts:
        physical_by_sensor.setdefault(a.sensor_name, []).append(a)

    integrity_sensors: Set[str] = {a.sensor_name for a in integrity_alerts}

    candidates: List[CorrelationCandidate] = []
    consumed_physical_alert_ids: Set[str] = set()

    # 1. Cross-subsystem rule: EPS + Thermal coupling
    if "battery_voltage" in physical_by_sensor and "temperature" in physical_by_sensor:
        rule = _get_rule("EPS_THERMAL_COUPLED_FAULT")
        grouped = physical_by_sensor["battery_voltage"] + physical_by_sensor["temperature"]
        candidates.append(
            _build_candidate(
                rule=rule,
                satellite_id=satellite_id,
                grouped_alerts=grouped,
                all_window_sensors=all_window_sensors,
                integrity_alerts=integrity_alerts,
            )
        )
        consumed_physical_alert_ids.update(a.alert_id for a in grouped)

    # 2. Cross-subsystem rule: ADCS + EPS solar coupling
    adcs_physical = [
        a for s in ("roll", "pitch", "yaw") for a in physical_by_sensor.get(s, [])
    ]
    if "battery_voltage" in physical_by_sensor and adcs_physical:
        rule = _get_rule("ADCS_EPS_SOLAR_COUPLING")
        grouped = physical_by_sensor["battery_voltage"] + adcs_physical
        # Only create if not already completely covered by a broader cross-rule
        if not all(a.alert_id in consumed_physical_alert_ids for a in grouped):
            candidates.append(
                _build_candidate(
                    rule=rule,
                    satellite_id=satellite_id,
                    grouped_alerts=grouped,
                    all_window_sensors=all_window_sensors,
                    integrity_alerts=integrity_alerts,
                )
            )
            consumed_physical_alert_ids.update(a.alert_id for a in grouped)

    # 3. Single-subsystem multi-detector clusters for remaining unconsumed physical alerts
    # EPS cluster
    eps_remaining = [
        a for a in physical_by_sensor.get("battery_voltage", [])
        if a.alert_id not in consumed_physical_alert_ids
    ]
    if len(eps_remaining) >= 2:
        rule = _get_rule("EPS_UNDERVOLTAGE_CLUSTER")
        candidates.append(
            _build_candidate(
                rule=rule,
                satellite_id=satellite_id,
                grouped_alerts=eps_remaining,
                all_window_sensors=all_window_sensors,
                integrity_alerts=integrity_alerts,
            )
        )

    # THERMAL cluster
    thermal_remaining = [
        a for a in physical_by_sensor.get("temperature", [])
        if a.alert_id not in consumed_physical_alert_ids
    ]
    if len(thermal_remaining) >= 2:
        rule = _get_rule("THERMAL_EXCURSION_CLUSTER")
        candidates.append(
            _build_candidate(
                rule=rule,
                satellite_id=satellite_id,
                grouped_alerts=thermal_remaining,
                all_window_sensors=all_window_sensors,
                integrity_alerts=integrity_alerts,
            )
        )

    # ADCS cluster
    adcs_remaining = [
        a for a in adcs_physical
        if a.alert_id not in consumed_physical_alert_ids
    ]
    if len(adcs_remaining) >= 2:
        rule = _get_rule("ADCS_ATTITUDE_CLUSTER")
        candidates.append(
            _build_candidate(
                rule=rule,
                satellite_id=satellite_id,
                grouped_alerts=adcs_remaining,
                all_window_sensors=all_window_sensors,
                integrity_alerts=integrity_alerts,
            )
        )

    # 4. OBC multi-channel integrity rule (only when >= 2 distinct sensors exhibit integrity issues)
    if len(integrity_sensors) >= 2 and len(integrity_alerts) >= 2:
        rule = _get_rule("OBC_MULTI_CHANNEL_INTEGRITY")
        candidates.append(
            _build_candidate(
                rule=rule,
                satellite_id=satellite_id,
                grouped_alerts=integrity_alerts,
                all_window_sensors=all_window_sensors,
                integrity_alerts=integrity_alerts,
            )
        )

    return candidates


def _get_rule(rule_code: str) -> CausalRuleDefinition:
    for rule in CAUSAL_RULES:
        if rule.rule_code == rule_code:
            return rule
    raise ValueError(f"Unknown causal rule: {rule_code}")


def _build_candidate(
    rule: CausalRuleDefinition,
    satellite_id: str,
    grouped_alerts: List[AlertRead],
    all_window_sensors: Set[str],
    integrity_alerts: List[AlertRead],
) -> CorrelationCandidate:
    ordered = sorted(grouped_alerts, key=lambda a: (_ensure_utc(a.last_detected_at), a.alert_id))
    timestamps = [_ensure_utc(a.first_detected_at) for a in ordered] + [
        _ensure_utc(a.last_detected_at) for a in ordered
    ]
    window_start = min(timestamps)
    window_end = max(timestamps)
    span_seconds = round((window_end - window_start).total_seconds(), 2)

    distinct_sensors = sorted({a.sensor_name for a in ordered})
    alert_types = sorted({a.alert_type for a in ordered})
    has_critical = any(a.severity == "CRITICAL" for a in ordered)

    supporting: List[Dict[str, Any]] = [
        {
            "kind": "TEMPORAL_PROXIMITY",
            "summary": f"{len(ordered)} alerts observed within {span_seconds:.1f}s across {len(distinct_sensors)} channel(s).",
            "details": {
                "alert_count": len(ordered),
                "span_seconds": span_seconds,
                "sensors": distinct_sensors,
                "alert_types": alert_types,
            },
        },
        {
            "kind": "SUBSYSTEM_RULE_MATCH",
            "summary": f"Matched causal rule {rule.rule_code} targeting subsystem {rule.suspected_subsystem}.",
            "details": {
                "rule_code": rule.rule_code,
                "suspected_subsystem": rule.suspected_subsystem,
            },
        },
    ]

    for a in ordered:
        supporting.append(
            {
                "kind": "ALERT_OBSERVATION",
                "summary": f"[{a.severity}] {a.sensor_name} ({a.alert_type}): {a.description}",
                "details": {
                    "alert_id": a.alert_id,
                    "sensor_name": a.sensor_name,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "observed_value": a.observed_value,
                    "z_score": a.z_score,
                },
            }
        )

    # Explicitly compute contradicting or alternative evidence
    contradicting: List[Dict[str, Any]] = []
    if len(distinct_sensors) == 1 and not rule.requires_integrity_only:
        contradicting.append(
            {
                "kind": "SINGLE_CHANNEL_SCOPE",
                "summary": (
                    f"Only {distinct_sensors[0]} showed anomalies; coupled subsystems did not exhibit "
                    "corroborating excursions during this window."
                ),
            }
        )

    if rule.suspected_subsystem == "EPS" and "temperature" not in all_window_sensors:
        contradicting.append(
            {
                "kind": "NOMINAL_COUPLED_CHANNEL",
                "summary": "Thermal channel (temperature) remained nominal during this window, weakening thermal-coupled EPS causes.",
            }
        )

    if rule.suspected_subsystem == "EPS" and not any(
        s in all_window_sensors for s in ("roll", "pitch", "yaw")
    ):
        contradicting.append(
            {
                "kind": "NOMINAL_ATTITUDE",
                "summary": "Attitude channels (roll, pitch, yaw) remained nominal, reducing likelihood of solar off-pointing.",
            }
        )

    if rule.suspected_subsystem == "THERMAL" and "battery_voltage" not in all_window_sensors:
        contradicting.append(
            {
                "kind": "NOMINAL_POWER_BUS",
                "summary": "Battery voltage remained nominal, suggesting thermal excursion may not be driven by an EPS bus fault.",
            }
        )

    if rule.suspected_subsystem == "ADCS" and "battery_voltage" not in all_window_sensors:
        contradicting.append(
            {
                "kind": "NOMINAL_POWER_BUS",
                "summary": "EPS battery voltage remained nominal, indicating no observed solar-pointing power deficit yet.",
            }
        )

    if integrity_alerts and not rule.requires_integrity_only:
        contradicting.append(
            {
                "kind": "CONCURRENT_INTEGRITY_DEFECT",
                "summary": (
                    "Concurrent sensor integrity issues exist in this window; instrumentation glitches "
                    "could partially confound physical subsystem hypotheses."
                ),
            }
        )

    if any(a.status == "RESOLVED" for a in ordered):
        contradicting.append(
            {
                "kind": "PARTIAL_RECOVERY",
                "summary": "One or more linked alerts have already resolved, indicating a transient or recovering condition.",
            }
        )

    # Illustrative heuristic confidence calculation (explicitly NOT a calibrated probability)
    score = 0.35
    score += 0.09 * min(len(ordered), 4)
    if len(distinct_sensors) >= 2:
        score += 0.14
    if has_critical:
        score += 0.10
    if span_seconds <= 15.0:
        score += 0.08
    score -= 0.07 * len(contradicting)
    confidence = round(max(0.15, min(0.92, score)), 4)

    explanation = (
        f"Illustrative heuristic score ({confidence:.2f}, not a calibrated probability): "
        f"derived from {len(ordered)} grouped alerts across {len(distinct_sensors)} channel(s) "
        f"within {span_seconds:.1f}s, {len(supporting)} supporting signal(s), and "
        f"{len(contradicting)} contradicting/uncertainty factor(s). Correlation does not prove causation."
    )

    grouping_reason = (
        f"Grouped {len(ordered)} alert(s) [{', '.join(a.alert_id for a in ordered)}] on "
        f"{', '.join(distinct_sensors)} within a {span_seconds:.1f}s window under rule {rule.rule_code}."
    )

    return CorrelationCandidate(
        satellite_id=satellite_id,
        rule_code=rule.rule_code,
        suspected_subsystem=rule.suspected_subsystem,
        hypothesis=rule.hypothesis_template,
        grouping_reason=grouping_reason,
        related_alert_ids=[a.alert_id for a in ordered],
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        confidence_score=confidence,
        confidence_explanation=explanation,
        window_start=window_start,
        window_end=window_end,
    )


class CorrelationService:
    """Persists, queries, and transitions causal correlation hypotheses in PostgreSQL."""

    @staticmethod
    def correlate_and_persist(
        db: Session,
        satellite_id: str = "SAT-01",
        window_seconds: float = DEFAULT_CORRELATION_WINDOW_SECONDS,
        include_resolved: bool = False,
        reference_time: Optional[datetime] = None,
    ) -> Tuple[List[CorrelationRead], List[CorrelationRead]]:
        """Evaluate persisted alerts in DB and upsert deduplicated correlations."""
        alert_query = select(Alert).where(Alert.satellite_id == satellite_id)
        if not include_resolved:
            alert_query = alert_query.where(Alert.status.in_(("ACTIVE", "ACKNOWLEDGED")))

        alert_rows = (
            db.execute(alert_query.order_by(desc(Alert.last_detected_at), desc(Alert.id)).limit(200))
            .scalars()
            .all()
        )
        alerts = [AlertRead.model_validate(r) for r in alert_rows]
        candidates = evaluate_correlations_for_alerts(
            alerts=alerts,
            satellite_id=satellite_id,
            window_seconds=window_seconds,
            reference_time=reference_time,
        )
        if not candidates:
            return [], []

        created_orms: List[Correlation] = []
        updated_orms: List[Correlation] = []

        for cand in candidates:
            existing = (
                db.execute(
                    select(Correlation)
                    .where(
                        Correlation.satellite_id == cand.satellite_id,
                        Correlation.rule_code == cand.rule_code,
                        Correlation.suspected_subsystem == cand.suspected_subsystem,
                        Correlation.status.in_(("ACTIVE", "ACKNOWLEDGED")),
                    )
                    .order_by(desc(Correlation.updated_at), desc(Correlation.id))
                    .limit(1)
                )
                .scalar_one_or_none()
            )

            if existing is not None:
                merged_ids = sorted(set(existing.related_alert_ids or []) | set(cand.related_alert_ids))
                changed = (
                    merged_ids != sorted(existing.related_alert_ids or [])
                    or abs(float(existing.confidence_score) - cand.confidence_score) > 0.001
                    or _ensure_utc(existing.window_end) != cand.window_end
                )
                if changed:
                    existing.related_alert_ids = merged_ids
                    existing.hypothesis = cand.hypothesis
                    existing.grouping_reason = cand.grouping_reason
                    existing.supporting_evidence = cand.supporting_evidence
                    existing.contradicting_evidence = cand.contradicting_evidence
                    existing.confidence_score = cand.confidence_score
                    existing.confidence_explanation = cand.confidence_explanation
                    existing.window_start = min(_ensure_utc(existing.window_start), cand.window_start)
                    existing.window_end = max(_ensure_utc(existing.window_end), cand.window_end)
                    updated_orms.append(existing)
            else:
                # Do not recreate if a DISMISSED correlation already covers the exact same alert IDs
                dismissed_match = (
                    db.execute(
                        select(Correlation)
                        .where(
                            Correlation.satellite_id == cand.satellite_id,
                            Correlation.rule_code == cand.rule_code,
                            Correlation.suspected_subsystem == cand.suspected_subsystem,
                            Correlation.status == "DISMISSED",
                        )
                        .order_by(desc(Correlation.updated_at), desc(Correlation.id))
                        .limit(1)
                    )
                    .scalar_one_or_none()
                )
                if dismissed_match is not None and set(cand.related_alert_ids).issubset(
                    set(dismissed_match.related_alert_ids or [])
                ):
                    continue

                new_corr = Correlation(
                    correlation_id=f"CORR-{uuid4().hex[:10].upper()}",
                    satellite_id=cand.satellite_id,
                    rule_code=cand.rule_code,
                    suspected_subsystem=cand.suspected_subsystem,
                    hypothesis=cand.hypothesis,
                    grouping_reason=cand.grouping_reason,
                    related_alert_ids=cand.related_alert_ids,
                    supporting_evidence=cand.supporting_evidence,
                    contradicting_evidence=cand.contradicting_evidence,
                    confidence_score=cand.confidence_score,
                    confidence_explanation=cand.confidence_explanation,
                    status="ACTIVE",
                    window_start=cand.window_start,
                    window_end=cand.window_end,
                )
                db.add(new_corr)
                created_orms.append(new_corr)

        if created_orms or updated_orms:
            db.commit()
            for row in created_orms:
                db.refresh(row)
            for row in updated_orms:
                db.refresh(row)

        return (
            [CorrelationRead.model_validate(r) for r in created_orms],
            [CorrelationRead.model_validate(r) for r in updated_orms],
        )

    @staticmethod
    def get_summary_counts(db: Session, satellite_id: Optional[str] = None) -> CorrelationSummaryCounts:
        base_filter = [Correlation.satellite_id == satellite_id] if satellite_id else []
        total = db.execute(select(func.count()).select_from(Correlation).where(*base_filter)).scalar_one()
        active = db.execute(
            select(func.count()).select_from(Correlation).where(*base_filter, Correlation.status == "ACTIVE")
        ).scalar_one()
        acknowledged = db.execute(
            select(func.count())
            .select_from(Correlation)
            .where(*base_filter, Correlation.status == "ACKNOWLEDGED")
        ).scalar_one()
        dismissed = db.execute(
            select(func.count())
            .select_from(Correlation)
            .where(*base_filter, Correlation.status == "DISMISSED")
        ).scalar_one()
        return CorrelationSummaryCounts(
            total=total,
            active=active,
            acknowledged=acknowledged,
            dismissed=dismissed,
        )

    @staticmethod
    def list_correlations(
        db: Session,
        satellite_id: Optional[str] = None,
        status_filter: Optional[CorrelationStatus] = None,
        suspected_subsystem: Optional[str] = None,
        window_seconds: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CorrelationRead], int, CorrelationSummaryCounts]:
        filters = []
        if satellite_id is not None:
            filters.append(Correlation.satellite_id == satellite_id)
        if status_filter is not None:
            filters.append(Correlation.status == status_filter)
        if suspected_subsystem is not None:
            filters.append(Correlation.suspected_subsystem == suspected_subsystem)
        if window_seconds is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
            filters.append(Correlation.window_end >= cutoff)

        total = db.execute(select(func.count()).select_from(Correlation).where(*filters)).scalar_one()
        rows = (
            db.execute(
                select(Correlation)
                .where(*filters)
                .order_by(desc(Correlation.updated_at), desc(Correlation.id))
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        summary = CorrelationService.get_summary_counts(db, satellite_id=satellite_id)
        return [CorrelationRead.model_validate(r) for r in rows], total, summary

    @staticmethod
    def get_correlation_detail(db: Session, correlation_id: str) -> CorrelationDetailResponse:
        row = db.execute(
            select(Correlation).where(Correlation.correlation_id == correlation_id)
        ).scalar_one_or_none()
        if row is None:
            raise CorrelationNotFoundError(correlation_id)

        alert_ids = row.related_alert_ids or []
        related_alerts: List[AlertRead] = []
        if alert_ids:
            alert_rows = (
                db.execute(select(Alert).where(Alert.alert_id.in_(alert_ids)))
                .scalars()
                .all()
            )
            related_alerts = [AlertRead.model_validate(a) for a in alert_rows]

        corr_read = CorrelationRead.model_validate(row)
        return CorrelationDetailResponse(**corr_read.model_dump(), related_alerts=related_alerts)

    @staticmethod
    def acknowledge_correlation(db: Session, correlation_id: str) -> CorrelationRead:
        row = db.execute(
            select(Correlation).where(Correlation.correlation_id == correlation_id)
        ).scalar_one_or_none()
        if row is None:
            raise CorrelationNotFoundError(correlation_id)
        if row.status == "DISMISSED":
            raise AppException(
                message="Dismissed correlations cannot be moved to ACKNOWLEDGED.",
                code="INVALID_CORRELATION_TRANSITION",
                status_code=status.HTTP_409_CONFLICT,
            )
        if row.status != "ACKNOWLEDGED":
            row.status = "ACKNOWLEDGED"
            row.acknowledged_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
        return CorrelationRead.model_validate(row)

    @staticmethod
    def dismiss_correlation(db: Session, correlation_id: str) -> CorrelationRead:
        row = db.execute(
            select(Correlation).where(Correlation.correlation_id == correlation_id)
        ).scalar_one_or_none()
        if row is None:
            raise CorrelationNotFoundError(correlation_id)
        if row.status != "DISMISSED":
            row.status = "DISMISSED"
            row.dismissed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
        return CorrelationRead.model_validate(row)

    @staticmethod
    def build_fault_graph(
        db: Session,
        satellite_id: str = "SAT-01",
        window_seconds: float = DEFAULT_CORRELATION_WINDOW_SECONDS,
    ) -> FaultGraphResponse:
        """Assemble the full subsystem, sensor, alert, and correlation graph from DB."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

        alert_rows = (
            db.execute(
                select(Alert)
                .where(
                    Alert.satellite_id == satellite_id,
                    Alert.last_detected_at >= cutoff,
                )
                .order_by(desc(Alert.last_detected_at), desc(Alert.id))
                .limit(25)
            )
            .scalars()
            .all()
        )
        alerts = [AlertRead.model_validate(a) for a in alert_rows]

        corr_rows = (
            db.execute(
                select(Correlation)
                .where(Correlation.satellite_id == satellite_id)
                .order_by(desc(Correlation.updated_at), desc(Correlation.id))
                .limit(25)
            )
            .scalars()
            .all()
        )
        correlations = [CorrelationRead.model_validate(c) for c in corr_rows]
        summary = CorrelationService.get_summary_counts(db, satellite_id=satellite_id)

        # Compute worst open status/severity per sensor and subsystem
        open_alerts = [a for a in alerts if a.status in ("ACTIVE", "ACKNOWLEDGED")]
        sensor_worst: Dict[str, str] = {}
        subsystem_worst: Dict[str, str] = {}

        for a in open_alerts:
            prev_s = sensor_worst.get(a.sensor_name)
            if prev_s is None or SEVERITY_RANK.get(a.severity, 0) > SEVERITY_RANK.get(prev_s, 0):
                sensor_worst[a.sensor_name] = a.severity

            primary_sub = (
                "SENSORS" if a.alert_type in INTEGRITY_ALERT_TYPES
                else SENSOR_TO_PRIMARY_SUBSYSTEM.get(a.sensor_name, "OBC")
            )
            prev_sub = subsystem_worst.get(primary_sub)
            if prev_sub is None or SEVERITY_RANK.get(a.severity, 0) > SEVERITY_RANK.get(prev_sub, 0):
                subsystem_worst[primary_sub] = a.severity

        for corr in correlations:
            if corr.status in ("ACTIVE", "ACKNOWLEDGED"):
                subsystem_worst.setdefault(corr.suspected_subsystem, "WARNING")

        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        # 1. Subsystem nodes
        for sub_id, sub in SUBSYSTEM_DEFINITIONS.items():
            sub_sev = subsystem_worst.get(sub_id)
            nodes.append(
                GraphNode(
                    id=f"sub:{sub_id}",
                    node_type="subsystem",
                    label=sub.name,
                    subsystem=sub_id,
                    status=sub_sev or "NOMINAL",
                    severity=sub_sev,
                    metadata={
                        "short_id": sub_id,
                        "description": sub.description,
                        "failure_modes": list(sub.failure_modes),
                    },
                )
            )

        # 2. Sensor nodes + sensor->subsystem edges
        for sensor_name, primary_sub in SENSOR_TO_PRIMARY_SUBSYSTEM.items():
            sev = sensor_worst.get(sensor_name)
            nodes.append(
                GraphNode(
                    id=f"sensor:{sensor_name}",
                    node_type="sensor",
                    label=sensor_name,
                    subsystem=primary_sub,
                    status=sev or "NOMINAL",
                    severity=sev,
                    metadata={"primary_subsystem": primary_sub},
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge:sensor-{sensor_name}-{primary_sub}",
                    source=f"sensor:{sensor_name}",
                    target=f"sub:{primary_sub}",
                    relationship="MEASURES",
                    description=f"{sensor_name} monitors {primary_sub}.",
                    active=sev is not None,
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge:sensors-group-{sensor_name}",
                    source="sub:SENSORS",
                    target=f"sensor:{sensor_name}",
                    relationship="INSTRUMENTS",
                    description=f"Instrumentation chain provides {sensor_name}.",
                    active=sev is not None,
                )
            )

        # 3. Subsystem dependency edges
        for dep in SUBSYSTEM_DEPENDENCY_EDGES:
            is_active = (
                dep.source in subsystem_worst and dep.target in subsystem_worst
            )
            edges.append(
                GraphEdge(
                    id=f"edge:dep-{dep.source}-{dep.target}-{dep.relationship}",
                    source=f"sub:{dep.source}",
                    target=f"sub:{dep.target}",
                    relationship=dep.relationship,
                    description=dep.description,
                    active=is_active,
                )
            )

        # 4. Persisted Alert nodes + alert->sensor edges
        for a in alerts:
            nodes.append(
                GraphNode(
                    id=f"alert:{a.alert_id}",
                    node_type="alert",
                    label=a.alert_type,
                    subsystem=SENSOR_TO_PRIMARY_SUBSYSTEM.get(a.sensor_name, "SENSORS"),
                    status=a.status,
                    severity=a.severity,
                    metadata={
                        "alert_id": a.alert_id,
                        "title": a.title,
                        "sensor_name": a.sensor_name,
                        "occurrence_count": a.occurrence_count,
                        "observed_value": a.observed_value,
                        "z_score": a.z_score,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge:alert-{a.alert_id}-sensor",
                    source=f"alert:{a.alert_id}",
                    target=f"sensor:{a.sensor_name}",
                    relationship="DETECTED_ON",
                    description=a.description,
                    active=a.status in ("ACTIVE", "ACKNOWLEDGED"),
                )
            )

        return FaultGraphResponse(
            satellite_id=satellite_id,
            window_seconds=window_seconds,
            nodes=nodes,
            edges=edges,
            correlations=correlations,
            summary=summary,
            timestamp=datetime.now(timezone.utc),
        )
