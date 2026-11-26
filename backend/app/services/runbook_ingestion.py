"""Manifest validation and deterministic Markdown-aware runbook ingestion."""

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from app.schemas.copilot import RunbookChunk, RunbookManifestEntry, RunbookManifestSchema

MAX_CHUNK_CHARS = 1600

# Maps Section 5 troubleshooting procedure headings to their owning anomaly IDs.
PROCEDURE_SECTION_ANOMALY_MAP: Dict[str, List[str]] = {
    "5.1 procedure for sudden voltage drop": ["BAT-001"],
    "5.2 procedure for abnormal battery temperature": ["BAT-002"],
    "5.3 procedure for unexpected current behaviour": ["BAT-003"],
    "5.4 procedure for unexpected state of charge change": ["BAT-004"],
    "5.1 procedure for sudden temperature rise": ["THM-001"],
    "5.2 procedure for unexpected temperature drop": ["THM-002"],
    "5.3 procedure for temperature sensor inconsistency": ["THM-003"],
    "5.4 procedure for continuous temperature fluctuation": ["THM-004"],
    "5.1 procedure for unexpected attitude deviation": ["ATT-001"],
    "5.2 procedure for unusual angular velocity": ["ATT-002"],
    "5.3 procedure for attitude sensor inconsistency": ["ATT-003"],
    "5.4 procedure for persistent attitude error": ["ATT-004"],
}

SUBSYSTEM_ANOMALY_PREFIX: Dict[str, str] = {
    "battery_power": "BAT-",
    "temperature_thermal": "THM-",
    "attitude_adcs": "ATT-",
}

EXPECTED_RUNBOOK_ANOMALIES: Dict[str, List[str]] = {
    "ATT-RB-001": ["ATT-001", "ATT-002", "ATT-003", "ATT-004"],
    "THM-RB-001": ["THM-001", "THM-002", "THM-003", "THM-004"],
    "BAT-RB-001": ["BAT-001", "BAT-002", "BAT-003", "BAT-004"],
}

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
ANOMALY_ID_RE = re.compile(r"\b(?:BAT|THM|ATT)-\d{3}\b")


class RunbookIngestionError(RuntimeError):
    """Raised when runbook manifest or source documents fail validation."""


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-")
    return slug[:48] or "section"


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()


def load_and_validate_manifest(runbooks_dir: Path) -> RunbookManifestSchema:
    """Load manifest.json and validate runbook IDs, subsystems, anomaly IDs, and files."""
    manifest_path = runbooks_dir / "manifest.json"
    if not manifest_path.exists():
        raise RunbookIngestionError(f"Runbook manifest not found at {manifest_path}")

    try:
        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = RunbookManifestSchema.model_validate(raw_manifest)
    except Exception as exc:  # noqa: BLE001
        raise RunbookIngestionError(f"Invalid runbook manifest: {exc}") from exc

    if not manifest.runbooks:
        raise RunbookIngestionError("Runbook manifest declares zero runbooks.")

    seen_ids = set()
    seen_files = set()
    seen_subsystems = set()

    for entry in manifest.runbooks:
        if entry.runbook_id in seen_ids:
            raise RunbookIngestionError(f"Duplicate runbook_id in manifest: {entry.runbook_id}")
        if entry.filename in seen_files:
            raise RunbookIngestionError(f"Duplicate filename in manifest: {entry.filename}")
        if entry.subsystem in seen_subsystems:
            raise RunbookIngestionError(f"Duplicate subsystem in manifest: {entry.subsystem}")
        seen_ids.add(entry.runbook_id)
        seen_files.add(entry.filename)
        seen_subsystems.add(entry.subsystem)

        expected_anomalies = EXPECTED_RUNBOOK_ANOMALIES.get(entry.runbook_id)
        if expected_anomalies is not None and entry.anomaly_ids != expected_anomalies:
            raise RunbookIngestionError(
                f"Anomaly IDs for {entry.runbook_id} must match {expected_anomalies}, got {entry.anomaly_ids}"
            )

        doc_path = runbooks_dir / entry.filename
        if not doc_path.exists() or not doc_path.is_file():
            raise RunbookIngestionError(f"Runbook file missing: {doc_path}")

        content = doc_path.read_text(encoding="utf-8")
        if not content.strip():
            raise RunbookIngestionError(f"Runbook file is empty: {doc_path}")
        if entry.runbook_id not in content:
            raise RunbookIngestionError(f"Runbook ID {entry.runbook_id} not found inside {entry.filename}")
        if entry.version not in content:
            raise RunbookIngestionError(f"Version {entry.version} not found inside {entry.filename}")
        for anomaly_id in entry.anomaly_ids:
            if anomaly_id not in content:
                raise RunbookIngestionError(
                    f"Declared anomaly ID {anomaly_id} missing from {entry.filename}"
                )

    return manifest


def _extract_chunk_anomaly_ids(
    entry: RunbookManifestEntry,
    section_heading: str,
    body_text: str,
) -> List[str]:
    """Infer chunk-specific anomaly IDs without tagging every chunk with all IDs."""
    own_prefix = SUBSYSTEM_ANOMALY_PREFIX.get(entry.subsystem, "")
    allowed = set(entry.anomaly_ids)

    matched_in_heading = [
        aid for aid in ANOMALY_ID_RE.findall(section_heading) if aid in allowed
    ]
    if matched_in_heading:
        return list(dict.fromkeys(matched_in_heading))

    normalized_heading = section_heading.lower().strip()
    if normalized_heading in PROCEDURE_SECTION_ANOMALY_MAP:
        return list(PROCEDURE_SECTION_ANOMALY_MAP[normalized_heading])

    # Avoid assigning every anomaly ID on catalog/metadata tables or overview sections.
    if "metadata" in normalized_heading or "detector event-to-runbook" in normalized_heading:
        return []

    found_own = [
        aid
        for aid in ANOMALY_ID_RE.findall(body_text)
        if aid in allowed and (not own_prefix or aid.startswith(own_prefix))
    ]
    unique_own = list(dict.fromkeys(found_own))
    if len(unique_own) == 1:
        return unique_own
    return []


def _split_oversized_section(body_text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split an oversized section cleanly at blank-line boundaries while keeping tables intact."""
    stripped = body_text.strip()
    if len(stripped) <= max_chars:
        return [stripped] if stripped else []

    paragraphs = re.split(r"\n{2,}", stripped)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue
        addition = len(para_clean) + (2 if current else 0)
        if current and current_len + addition > max_chars:
            chunks.append("\n\n".join(current))
            current = [para_clean]
            current_len = len(para_clean)
        else:
            current.append(para_clean)
            current_len += addition

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _parse_markdown_sections(markdown_text: str) -> Tuple[str, List[Tuple[str, str, str]]]:
    """Parse Markdown into ordered (section_heading, section_path, body_text) tuples."""
    lines = _normalize_text(markdown_text).splitlines()
    doc_title = ""
    h2_heading = ""
    current_heading = ""
    current_path = ""
    buffer: List[str] = []
    sections: List[Tuple[str, str, str]] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        buffer.clear()
        if body and current_heading:
            sections.append((current_heading, current_path or current_heading, body))

    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            if level == 1:
                flush()
                doc_title = heading_text
                h2_heading = ""
                current_heading = heading_text
                current_path = heading_text
                continue
            if level == 2:
                flush()
                h2_heading = heading_text
                current_heading = heading_text
                current_path = heading_text
                continue
            if level == 3:
                flush()
                current_heading = heading_text
                current_path = f"{h2_heading} > {heading_text}" if h2_heading else heading_text
                continue
        buffer.append(line)

    flush()
    return doc_title, sections


def chunk_markdown_runbook(entry: RunbookManifestEntry, markdown_text: str) -> List[RunbookChunk]:
    """Chunk one Markdown runbook deterministically with full section & provenance metadata."""
    parsed_title, sections = _parse_markdown_sections(markdown_text)
    document_title = parsed_title or entry.title
    chunks: List[RunbookChunk] = []
    seen_hashes = set()

    for section_heading, section_path, body_text in sections:
        parts = _split_oversized_section(body_text, max_chars=MAX_CHUNK_CHARS)
        anomaly_ids = _extract_chunk_anomaly_ids(entry, section_heading, body_text)

        for sub_idx, part in enumerate(parts):
            contextual_text = (
                f"[{entry.runbook_id} | {entry.subsystem} | {section_path}]\n"
                f"{section_heading}\n\n{part}"
            ).strip()
            content_hash = sha256(
                f"{entry.runbook_id}|{entry.version}|{section_path}|{contextual_text}".encode("utf-8")
            ).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)

            chunk_id = (
                f"{entry.runbook_id}::{_slugify(section_heading)}::{sub_idx}::{content_hash[:8]}"
            )
            chunks.append(
                RunbookChunk(
                    chunk_id=chunk_id,
                    runbook_id=entry.runbook_id,
                    document_name=entry.filename,
                    document_title=document_title,
                    version=entry.version,
                    subsystem=entry.subsystem,
                    anomaly_ids=anomaly_ids,
                    section_heading=section_heading,
                    section_path=section_path,
                    document_type=entry.document_type,
                    keywords=list(entry.keywords),
                    text=contextual_text,
                    content_hash=content_hash,
                    char_count=len(contextual_text),
                )
            )

    return chunks


def ingest_all_runbooks(runbooks_dir: Path) -> Tuple[RunbookManifestSchema, List[RunbookChunk], str]:
    """Load, validate, and deterministically chunk all runbooks declared in manifest.json."""
    manifest = load_and_validate_manifest(runbooks_dir)
    all_chunks: List[RunbookChunk] = []
    seen_chunk_hashes = set()

    for entry in sorted(manifest.runbooks, key=lambda item: item.runbook_id):
        content = (runbooks_dir / entry.filename).read_text(encoding="utf-8")
        doc_chunks = chunk_markdown_runbook(entry, content)
        for chunk in doc_chunks:
            if chunk.content_hash in seen_chunk_hashes:
                continue
            seen_chunk_hashes.add(chunk.content_hash)
            all_chunks.append(chunk)

    corpus_digest = sha256(
        json.dumps([chunk.content_hash for chunk in all_chunks], sort_keys=False).encode("utf-8")
    ).hexdigest()
    return manifest, all_chunks, corpus_digest
