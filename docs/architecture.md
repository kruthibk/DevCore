# SAT-TRIAGE System Architecture

## Overview

SAT-TRIAGE is a full-stack satellite telemetry anomaly triage copilot built for **AVISHKAR'26** (Problem Statement 11) by **Team DevCore (`AV26-BF34B6F9D2`)**.

The application operates as one connected operational workflow:

```text
Telemetry Simulation -> Ingestion & Batch Persistence -> Real-Time Socket.IO Dashboard
-> Statistical & Integrity Detection -> Alert Persistence -> Correlation & Fault Graph
-> Runbook FAISS Retrieval -> Evidence-Linked AI Copilot -> Deterministic Verification Wall
-> Human Operator Decision -> Unified Incident & Audit Timeline
```

## Component Flow

```text
+-------------------------------------------------------+
|          React + Vite Mission Control UI              |
|  - Evidence-Linked AI Copilot (/copilot)              |
|  - Interactive Fault Graph + Hypothesis Inspector     |
|  - Live Alerts Queue + Evidence & Ack/Resolve         |
|  - Sensor Integrity Panel (System Diagnostics)        |
|  - Live Recharts Telemetry + Simulator Controls       |
+---------------------------+---------------------------+
                            | HTTP REST + Socket.IO (/socket.io)
                            v
+-------------------------------------------------------+
|      FastAPI + python-socketio (ASGI Sub-App)         |
|  - Simulator Loop -> TelemetryGenerator (NumPy)       |
|  - DetectionPipelineService (asyncio.Lock):           |
|      1. SensorIntegrityService (MISSING/FROZEN/...)   |
|      2. StatisticalAnomalyDetector (Pandas/SciPy)     |
|      3. AlertService (Deduplicate & Persist)          |
|      4. CorrelationService (Time-Window Causal Rules) |
|      5. Socket.IO Broadcast (alert:*, fault_graph:*)  |
|  - RAG & AI Copilot (/api/v1/copilot/*):              |
|      1. RunbookIngestion (manifest + MD chunking)     |
|      2. RAGVectorStore (FastEmbed + FAISS IndexFlatIP)|
|      3. CopilotService (Verified Telemetry + LLM/Guard|
+---------------------------+---------------------------+
                            | Scoped Sessions / Disk Persistence
                            v
+-------------------------------------------------------+
|       PostgreSQL 16 (Docker) & Local Data Store       |
|  - users, telemetry_readings, alerts, correlations    |
|  - backend/data/runbooks/ (3 approved MD + manifest)  |
|  - backend/data/faiss/ (runbooks.index, chunks.json)  |
+-------------------------------------------------------+
```

## Detection Algorithms & Limitations

1. **Rolling Baseline & Z-Score (`STATISTICAL_ANOMALY`):**
   - Uses a per-`(satellite_id, sensor_name)` bounded rolling window (`rolling_window_size = 30`) evaluated with `pandas.Series` mean and sample standard deviation (`ddof=1`) through a single authoritative `compute_z_score_stats()` helper shared across alerts, evidence, and UI explanations.
   - For attitude angles (`roll`, `pitch`, `yaw`), circular statistics (`atan2(mean(sin), mean(cos))`) and shortest signed circular deltas `((target - ref + 180) % 360) - 180` prevent false `358°` wrap jumps when crossing `+179°` to `-179°`.
   - Requires `min_baseline_samples = 8` before evaluating z-scores, guards against zero/near-zero standard deviation (`min_meaningful_std`), and applies a per-sensor `min_deviation_deadband` to prevent false alerts on slow orbital sinusoidal cycles.
   - **Baseline Contamination Safeguard:** Fault-injected samples (`quality_status != "NOMINAL"`) and numerically anomalous samples are excluded from updating the nominal rolling baseline window.
   - Records an `illustrative_two_tailed_p` via `scipy.stats.norm.sf` in `evidence` as supporting context only (not a calibrated fault probability or causal claim).

2. **Rate-of-Change (`RATE_OF_CHANGE`):**
   - Computes `|Δvalue / Δt|` across consecutive valid samples (using circular `±180°` difference for `roll`, `pitch`, and `yaw`) and flags excursions above sensor-specific `max_rate_per_sec` limits.

3. **Engineering Limits (`ENGINEERING_LIMIT`):**
   - Evaluates incoming values against centralized `engineering_warning` and `engineering_critical` operational bounds, explicitly distinct from statistical z-score deviations.

4. **Cross-Signal Sensor Integrity (`SENSOR_MISSING`, `SENSOR_FROZEN`, `SENSOR_INVALID`, `SENSOR_STALE`):**
   - Inspects raw values and timezone-aware timestamps independently of simulator `quality_status` labels, tracked per `(satellite_id, sensor_name)`.
   - All sensor integrity findings carry `WARNING` severity (data-reliability advisories, not `CRITICAL` spacecraft failures).
   - `MISSING`: null readings (excluded from statistical baselines).
   - `FROZEN`: `6` consecutive identical values within `1e-9` tolerance.
   - `INVALID`: `NaN`/`Inf`, missing/naive timestamps, or values outside `physical_valid_range`.
   - `STALE`: evaluated periodically by `_staleness_loop()` in `TelemetrySimulatorService` when `simulator_running=True` and elapsed time exceeds `6.0s`; when stopped, channels report `STREAM_INACTIVE`.

5. **Alert Deduplication, Cooldown & Lifecycle:**
   - Active/acknowledged duplicates keyed by `(satellite_id, sensor_name, alert_type)` respect `dedup_cooldown_seconds = 10.0` (bypassed only on severity escalation) and update `last_detected_at` + increment `occurrence_count` instead of creating duplicate rows.
   - Lower-severity updates preserve the peak-severity atomic snapshot (`title`, `description`, `observed_value`, `z_score`, `evidence`) while recording `latest_observed_value` in `evidence`.
   - Lifecycle transitions: `ACTIVE` → `ACKNOWLEDGED` → `RESOLVED` (explicitly by operator or automatically after `recovery_consecutive_samples = 5` consecutive clean nominal ticks, preserving full persisted history).

## Hybrid Causal Fault Graph & Alert Correlation (Phase 5)

1. **Configurable Subsystem Dependency Graph (`fault_graph_config.py`):**
   - Defines five spacecraft subsystems (`EPS`, `THERMAL`, `ADCS`, `OBC`, `SENSORS`), their failure modes, sensor mappings (`battery_voltage` → `EPS`, `temperature` → `THERMAL`, `roll`/`pitch`/`yaw` → `ADCS`, with `SENSORS` instrumenting all five channels), and directed coupling relationships (`PROVIDES_POWER`, `THERMAL_COUPLING`, `ATTITUDE_SOLAR_COUPLING`, `ATTITUDE_THERMAL_COUPLING`, `TELEMETRY_BUS`, `CONTROL_LOOP`).
2. **Time-Window Alert Correlation & Rule Engine (`correlation_engine.py`):**
   - Groups open Phase 4 persisted alerts within a configurable sliding time window (`DEFAULT_CORRELATION_WINDOW_SECONDS = 120.0`) by temporal proximity, sensor channels, alert categories (physical anomaly vs. sensor integrity), severity, and explicit domain causal rules (`EPS_THERMAL_COUPLED_FAULT`, `ADCS_EPS_SOLAR_COUPLING`, `OBC_MULTI_CHANNEL_INTEGRITY`, `EPS_UNDERVOLTAGE_CLUSTER`, `THERMAL_EXCURSION_CLUSTER`, `ADCS_ATTITUDE_CLUSTER`, plus single-sensor integrity advisories).
   - Uses deterministic rule-based correlation only — never delegates causal reasoning to an LLM.
3. **Supporting/Contradicting Evidence, Illustrative Confidence & Limitations:**
   - Records both **supporting evidence** (matched alert types, temporal proximity, severity, multi-detector agreement) and **contradicting/alternative evidence** (such as coupled attitude channels remaining nominal, or sensor integrity flags reducing confidence in physical failure interpretations).
   - Computes an **illustrative heuristic `confidence_score`** accompanied by a plain-language explanation. Hypotheses explicitly represent **possible common causes**, never confirmed failures; correlation never proves causation, and human operators retain final authority.
4. **Correlation Persistence & Lifecycle (`correlations` table):**
   - Persists each active group (`correlation_id`, `satellite_id`, `rule_code`, `suspected_subsystem`, `hypothesis`, `grouping_reason`, `related_alert_ids`, `supporting_evidence`, `contradicting_evidence`, `confidence_score`, `confidence_explanation`, `status`, `window_start`, `window_end`, timestamps).
   - Operator actions (`ACTIVE` → `ACKNOWLEDGED` or `DISMISSED`) persist in PostgreSQL and broadcast updates over Socket.IO (`correlation:new`, `correlation:updated`, `fault_graph:update`).

## Evidence-Linked RAG & AI Copilot (Phase 6)

1. **Manifest-Validated Runbook Ingestion (`runbook_ingestion.py`):**
   - Loads `backend/data/runbooks/manifest.json` and validates `ATT-RB-001` (`attitude_runbook.md`), `THM-RB-001` (`temperature_runbook.md`), and `BAT-RB-001` (`battery_runbook.md`), checking runbook IDs, versions, subsystem ownership, and anomaly IDs (`ATT-001`..`ATT-004`, `THM-001`..`THM-004`, `BAT-001`..`BAT-004`).
   - Performs deterministic Markdown-aware section chunking (`H1`/`H2`/`H3`), preserves headings and tables, avoids duplicates via SHA-256 `content_hash`, and attaches `chunk_id`, `runbook_id`, `document_name`, `version`, `subsystem`, `anomaly_ids`, and `section_heading` metadata to every chunk (`87` total chunks across `3` runbooks).
2. **Embeddings & Persistent FAISS Index (`rag_store.py`):**
   - Computes 384-dimensional L2-normalized dense embeddings via `FastEmbed` (`BAAI/bge-small-en-v1.5`, quantized ONNX cached under `backend/data/models/`) and indexes them with `faiss.IndexFlatIP` (exact cosine similarity).
   - Persists `runbooks.index`, `chunks.json`, and `index_meta.json` under `backend/data/faiss/` via atomic replacement and validates file integrity, vector counts, dimensions, and model match on load (reporting `READY`, `MISSING`, or `CORRUPTED` transparently without silent fallbacks).
3. **Context-Aware Semantic Retrieval:**
   - Supports `subsystem` filtering (including alias mapping `EPS`/`THERMAL`/`ADCS`), `anomaly_id` filtering, and configurable `top_k`, while ranking with `RAG_MIN_SIMILARITY = 0.56` sufficiency gating.
   - Separates electrical-power battery temperature context (`BAT-RB-001`) from broader spacecraft thermal control (`THM-RB-001`) and preserves ADCS angle-wrapping rules (`+179°` to `-179°` vs `358°` rotation).
4. **Grounded AI Copilot & Safety Boundaries (`copilot_service.py`):**
   - Supplies only verified telemetry readings (`battery_voltage`, `temperature`, `roll`, `pitch`, `yaw`), persisted PostgreSQL alerts/correlations, and retrieved runbook chunks to the optional configured LLM (`GEMINI_API_KEY` with default `gemini-3.1-flash-lite`, `OPENAI_API_KEY`, or `LLM_API_KEY`).
   - If no LLM key is configured, vector retrieval still executes and returns `generation_status = "LLM_UNAVAILABLE"` with inspectable chunks rather than fabricated AI answers.
   - Post-generation guardrails strip ungrounded citations not matching retrieved `chunk_id` / `(runbook_id, section_heading)`, reject fabricated unsupported telemetry channels (`battery_current`, `battery_soc`, `angular_velocity`, `reaction_wheel_speed`, `electronics_temperature`), block autonomous spacecraft command language, enforce correlation != causation, and handle malformed LLM JSON safely (`MALFORMED_LLM_RESPONSE`).

## Verification Wall, Human Approval & Unified Incident Architecture

1. **JWT Authentication & Socket.IO Handshake (`security.py`, `rbac.py`, `auth.py`, `socket_manager.py`, `token_revocation.py`):**
   - Registration (`POST /api/v1/auth/register`) hashes passwords with `bcrypt`, enforces `OPERATOR` role assignment (ignoring privilege escalation fields), and returns an HS256 JWT signed with `JWT_SECRET_KEY` (`JWT_EXPIRE_MINUTES = 480`).
   - Protected REST endpoints and Socket.IO `/socket.io` handshakes require a valid JWT checked against `revoked_tokens` (`POST /api/v1/auth/logout`) and `users.is_active`.
2. **Server-Side RBAC (`OPERATOR`, `ADMIN`, `admin.py`):**
   - `OPERATOR` accesses telemetry, alerts, correlations, Copilot queries (with automatic alert + correlation context linking), Verification Wall evaluations, human decisions, and incident logs.
   - `ADMIN` inherits all `OPERATOR` permissions plus simulator control, FAISS reindexing, and `/api/v1/admin/users*` management (self-role-change and self-deactivation blocked with `HTTP 403`).
3. **Deterministic Verification Wall (`verification.py`, `verification_wall.py`):**
   - Independently evaluates `COPILOT` or `MANUAL` recommendations across 10 deterministic checks. Stores immutable `Recommendation` (`linked_incident_id`) and `Verification` rows (`VERIFIED`, `NEEDS_REVIEW`, `REJECTED`).
4. **Human Operator Approval & Unified Incident Registry (`decisions.py`, `incident.py`, `incident_service.py`, `incidents.py`):**
   - Separates AI output, automated Verification Wall status, and human operator decision (`APPROVED`, `REJECTED`, `INVESTIGATION_REQUESTED`), permanently enforcing `command_executed = false`.
   - Recording a decision automatically links or creates one unified `Incident` (`linked_recommendation_id`, `linked_alert_ids`, `linked_correlation_ids`) without duplicate incidents and appends `RECOMMENDATION_LINKED`, `VERIFICATION_RECORDED`, `DECISION_RECORDED`, `STATUS_CHANGE`, and `NOTE_ADDED` rows to `incident_logs`.
5. **Security Limitations:**
   - Single-secret HS256 JWTs without refresh-token rotation or MFA; revoked JTIs remain in `revoked_tokens` until administrative cleanup; synthetic telemetry Socket.IO events are broadcast-only and never carry spacecraft commands.
