"""Embedding provider, persistent FAISS vector store, and semantic retrieval engine."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import faiss
import numpy as np
from fastembed import TextEmbedding

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.copilot import (
    CopilotStatusResponse,
    RetrievedEvidenceChunk,
    RunbookChunk,
)
from app.services.runbook_ingestion import RunbookIngestionError, ingest_all_runbooks

logger = get_logger(__name__)

SUBSYSTEM_ALIASES: Dict[str, str] = {
    "eps": "battery_power",
    "bat": "battery_power",
    "bat-rb-001": "battery_power",
    "battery": "battery_power",
    "power": "battery_power",
    "battery_power": "battery_power",
    "thm": "temperature_thermal",
    "thm-rb-001": "temperature_thermal",
    "thermal": "temperature_thermal",
    "temperature": "temperature_thermal",
    "temperature_thermal": "temperature_thermal",
    "adcs": "attitude_adcs",
    "att": "attitude_adcs",
    "att-rb-001": "attitude_adcs",
    "attitude": "attitude_adcs",
    "attitude_adcs": "attitude_adcs",
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9_+-]+")
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "to", "of",
    "in", "on", "for", "with", "when", "what", "how", "why", "which", "should",
    "do", "does", "did", "can", "could", "if", "and", "or", "from", "into",
    "by", "that", "this", "it", "its", "anomalies", "anomaly", "investigate",
    "investigated", "checked", "check",
}

BATTERY_POWER_CUES = (
    "battery_voltage",
    "battery voltage",
    "battery temperature",
    "voltage drop",
    "power bus",
    "charging",
    "discharging",
    "state of charge",
    "soc",
    "eps",
    "electrical power",
)

THERMAL_BROAD_CUES = (
    "electronics temperature",
    "instrument temperature",
    "internal temperature",
    "thermal control",
    "radiator",
    "heater",
    "cooling",
    "environmental heating",
    "multiple temperature sensors",
    "temperature spike",
    "temperature drop",
    "temperature fluctuation",
)


class EmbeddingProvider(Protocol):
    """Protocol for text embedding providers compatible with FAISS retrieval."""

    model_name: str
    dimension: int

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        """Return L2-normalized float32 embeddings of shape (N, D)."""

    def embed_query(self, text: str) -> np.ndarray:
        """Return L2-normalized float32 embedding of shape (1, D)."""


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    return (arr / norms).astype(np.float32)


class FastEmbedProvider:
    """Local quantized ONNX dense embedding provider powered by FastEmbed."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: Optional[Path] = None,
        dimension: int = 384,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.dimension = dimension
        self._model: Optional[TextEmbedding] = None
        self._lock = threading.Lock()

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    kwargs: Dict[str, Any] = {"model_name": self.model_name}
                    if self.cache_dir is not None:
                        self.cache_dir.mkdir(parents=True, exist_ok=True)
                        kwargs["cache_dir"] = str(self.cache_dir)
                    self._model = TextEmbedding(**kwargs)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        model = self._get_model()
        raw = list(model.embed(list(texts), batch_size=1))
        vectors = _l2_normalize(np.asarray(raw, dtype=np.float32))
        self.dimension = int(vectors.shape[1])
        return vectors

    def embed_query(self, text: str) -> np.ndarray:
        model = self._get_model()
        raw = list(model.query_embed(text))
        vectors = _l2_normalize(np.asarray(raw, dtype=np.float32))
        self.dimension = int(vectors.shape[1])
        return vectors


class RAGIndexError(RuntimeError):
    """Raised when FAISS index creation or validation fails."""


def normalize_subsystem_filter(value: Optional[str]) -> Optional[str]:
    """Normalize user or subsystem codes (e.g., EPS -> battery_power)."""
    if not value or not value.strip():
        return None
    cleaned = value.strip().lower()
    return SUBSYSTEM_ALIASES.get(cleaned, value.strip())


def _tokenize(text: str) -> set:
    return {
        tok.lower()
        for tok in TOKEN_RE.findall(text)
        if tok.lower() not in STOPWORDS and len(tok) > 1
    }


def _compute_ranking_score(
    query: str,
    chunk: RunbookChunk,
    similarity_score: float,
) -> float:
    """Combine dense cosine similarity with small bounded context tie-breakers."""
    # Never boost unrelated out-of-domain queries above evidence thresholds.
    if similarity_score < 0.25:
        return round(similarity_score, 4)

    q_lower = query.lower()
    q_tokens = _tokenize(query)
    chunk_tokens = _tokenize(f"{chunk.section_heading} {chunk.text}")
    overlap = len(q_tokens & chunk_tokens) / max(len(q_tokens), 1)
    lexical_bonus = min(0.08, overlap * 0.08)

    context_bonus = 0.0
    # Exact anomaly ID mention
    for aid in chunk.anomaly_ids:
        if aid.lower() in q_lower:
            context_bonus += 0.08

    # Angle wrapping guidance cue (+179 / -179 / angle wrapping)
    if ("179" in q_lower or "wrap" in q_lower or "358" in q_lower) and (
        "179" in chunk.text or "angle-wrapping" in chunk.text.lower()
    ):
        context_bonus += 0.10

    # Distinguish battery-temperature in electrical-power context vs broad thermal
    has_battery_cue = any(cue in q_lower for cue in BATTERY_POWER_CUES)
    has_broad_thermal_cue = any(cue in q_lower for cue in THERMAL_BROAD_CUES)
    if has_battery_cue and not has_broad_thermal_cue:
        if chunk.subsystem == "battery_power":
            context_bonus += 0.05
    elif has_broad_thermal_cue and not ("battery voltage" in q_lower or "power" in q_lower):
        if chunk.subsystem == "temperature_thermal":
            context_bonus += 0.05

    return round(similarity_score + lexical_bonus + context_bonus, 4)


def _make_snippet(chunk: RunbookChunk, max_len: int = 320) -> str:
    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    body_lines = [line for line in lines if not line.startswith("[")]
    joined = " ".join(body_lines)
    if len(joined) <= max_len:
        return joined
    return joined[: max_len - 3].rstrip() + "..."


class RAGVectorStore:
    """Manages deterministic FAISS indexing, disk persistence, validation, and retrieval."""

    def __init__(
        self,
        runbooks_dir: Path,
        index_dir: Path,
        embedding_provider: EmbeddingProvider,
        min_similarity: float = 0.56,
    ) -> None:
        self.runbooks_dir = runbooks_dir
        self.index_dir = index_dir
        self.embedding_provider = embedding_provider
        self.min_similarity = min_similarity
        self._lock = threading.RLock()

        self._index: Optional[faiss.Index] = None
        self._chunks: List[RunbookChunk] = []
        self._meta: Dict[str, Any] = {}
        self._status: str = "MISSING"
        self._diagnostic_message: str = "FAISS index has not been built yet."

    @property
    def index_file(self) -> Path:
        return self.index_dir / "runbooks.index"

    @property
    def chunks_file(self) -> Path:
        return self.index_dir / "chunks.json"

    @property
    def meta_file(self) -> Path:
        return self.index_dir / "index_meta.json"

    def _validate_files(self) -> None:
        files = [self.index_file, self.chunks_file, self.meta_file]
        exists = [p.exists() for p in files]
        if not any(exists):
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "MISSING"
            self._diagnostic_message = (
                f"FAISS index not found at {self.index_dir}. Run /api/v1/copilot/reindex to build."
            )
            return

        if not all(exists):
            missing = [p.name for p, flag in zip(files, exists) if not flag]
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "CORRUPTED"
            self._diagnostic_message = f"Incomplete FAISS index artifacts; missing: {', '.join(missing)}"
            return

        try:
            meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            raw_chunks = json.loads(self.chunks_file.read_text(encoding="utf-8"))
            chunks = [RunbookChunk.model_validate(item) for item in raw_chunks]
            index = faiss.read_index(str(self.index_file))
        except Exception as exc:  # noqa: BLE001
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "CORRUPTED"
            self._diagnostic_message = f"Failed to read FAISS index or metadata: {exc}"
            return

        if len(chunks) == 0 or index.ntotal <= 0:
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "CORRUPTED"
            self._diagnostic_message = "FAISS index contains zero vectors or chunks."
            return

        if index.ntotal != len(chunks):
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "CORRUPTED"
            self._diagnostic_message = (
                f"Index count mismatch: FAISS has {index.ntotal} vectors, chunks.json has {len(chunks)}."
            )
            return

        expected_dim = int(meta.get("embedding_dim", 0))
        if expected_dim <= 0 or index.d != expected_dim:
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "CORRUPTED"
            self._diagnostic_message = (
                f"Embedding dimension mismatch: FAISS has d={index.d}, meta has {expected_dim}."
            )
            return

        if meta.get("embedding_model") != self.embedding_provider.model_name:
            self._index = None
            self._chunks = []
            self._meta = {}
            self._status = "CORRUPTED"
            self._diagnostic_message = (
                f"Embedding model mismatch: index built with {meta.get('embedding_model')}, "
                f"configured model is {self.embedding_provider.model_name}."
            )
            return

        self._index = index
        self._chunks = chunks
        self._meta = meta
        self._status = "READY"
        self._diagnostic_message = (
            f"FAISS index READY with {len(chunks)} chunks across {meta.get('document_count', 0)} runbooks."
        )

    def ensure_loaded(self, auto_build: bool = False) -> bool:
        """Load and validate existing FAISS artifacts, optionally building if missing."""
        with self._lock:
            if self._status == "READY" and self._index is not None:
                return True
            self._validate_files()
            if self._status == "READY":
                return True
            if auto_build and self._status == "MISSING":
                self.rebuild_index()
                return self._status == "READY"
            return False

    def rebuild_index(self) -> Dict[str, Any]:
        """Ingest runbooks, compute embeddings, persist FAISS index, and validate."""
        with self._lock:
            try:
                manifest, chunks, corpus_digest = ingest_all_runbooks(self.runbooks_dir)
            except RunbookIngestionError as exc:
                self._status = "CORRUPTED"
                self._diagnostic_message = f"Runbook ingestion failed: {exc}"
                raise RAGIndexError(self._diagnostic_message) from exc

            if not chunks:
                self._status = "CORRUPTED"
                self._diagnostic_message = "Chunking produced zero runbook chunks."
                raise RAGIndexError(self._diagnostic_message)

            texts = [chunk.text for chunk in chunks]
            vectors = _l2_normalize(self.embedding_provider.embed_documents(texts))
            if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or not np.all(np.isfinite(vectors)):
                self._status = "CORRUPTED"
                self._diagnostic_message = "Embedding generation returned invalid vector dimensions or NaN/Inf."
                raise RAGIndexError(self._diagnostic_message)

            dim = int(vectors.shape[1])
            index = faiss.IndexFlatIP(dim)
            index.add(vectors)
            if index.ntotal != len(chunks):
                self._status = "CORRUPTED"
                self._diagnostic_message = (
                    f"FAISS indexing failed: expected {len(chunks)} vectors, got {index.ntotal}."
                )
                raise RAGIndexError(self._diagnostic_message)

            self.index_dir.mkdir(parents=True, exist_ok=True)
            tmp_index = self.index_dir / "runbooks.index.tmp"
            tmp_chunks = self.index_dir / "chunks.json.tmp"
            tmp_meta = self.index_dir / "index_meta.json.tmp"

            meta_payload = {
                "schema_version": "1.0",
                "embedding_model": self.embedding_provider.model_name,
                "embedding_dim": dim,
                "document_count": len(manifest.runbooks),
                "chunk_count": len(chunks),
                "corpus_hash": corpus_digest,
                "supported_channels": list(manifest.supported_simulator_channels),
                "last_indexed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "runbooks": [
                    {
                        "runbook_id": rb.runbook_id,
                        "filename": rb.filename,
                        "version": rb.version,
                        "subsystem": rb.subsystem,
                        "anomaly_ids": rb.anomaly_ids,
                        "chunk_count": sum(1 for c in chunks if c.runbook_id == rb.runbook_id),
                    }
                    for rb in sorted(manifest.runbooks, key=lambda r: r.runbook_id)
                ],
            }

            faiss.write_index(index, str(tmp_index))
            tmp_chunks.write_text(
                json.dumps([c.model_dump(mode="json") for c in chunks], indent=2),
                encoding="utf-8",
            )
            tmp_meta.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

            tmp_index.replace(self.index_file)
            tmp_chunks.replace(self.chunks_file)
            tmp_meta.replace(self.meta_file)

            self._validate_files()
            if self._status != "READY":
                raise RAGIndexError(f"Post-write FAISS index validation failed: {self._diagnostic_message}")

            logger.info(
                "Built and verified runbook FAISS index",
                extra={
                    "document_count": len(manifest.runbooks),
                    "chunk_count": len(chunks),
                    "embedding_model": self.embedding_provider.model_name,
                    "embedding_dim": dim,
                    "index_dir": str(self.index_dir),
                },
            )
            return dict(self._meta)

    def get_status(
        self,
        llm_available: bool,
        llm_provider: str,
        llm_model: Optional[str],
    ) -> CopilotStatusResponse:
        """Inspect current index status without fabricating success."""
        with self._lock:
            self._validate_files()
            return CopilotStatusResponse(
                index_status=self._status,  # type: ignore[arg-type]
                index_available=self._status == "READY",
                indexing_status=(
                    "indexed"
                    if self._status == "READY"
                    else ("not_indexed" if self._status == "MISSING" else "corrupted")
                ),
                document_count=int(self._meta.get("document_count", 0)),
                chunk_count=int(self._meta.get("chunk_count", 0)),
                embedding_model=self.embedding_provider.model_name,
                embedding_dim=self._meta.get("embedding_dim"),
                index_path=str(self.index_dir),
                llm_available=llm_available,
                llm_provider=llm_provider,
                llm_model=llm_model,
                diagnostic_message=self._diagnostic_message,
                supported_channels=list(
                    self._meta.get(
                        "supported_channels",
                        ["battery_voltage", "temperature", "roll", "pitch", "yaw"],
                    )
                ),
                runbooks=list(self._meta.get("runbooks", [])),
                last_indexed_at=self._meta.get("last_indexed_at"),
            )

    def retrieve(
        self,
        query: str,
        subsystem: Optional[str] = None,
        anomaly_id: Optional[str] = None,
        top_k: int = 5,
        min_similarity: Optional[float] = None,
    ) -> Tuple[List[RetrievedEvidenceChunk], bool, str]:
        """Search FAISS index with metadata filtering and relevance sufficiency verification."""
        if not query or not query.strip():
            return [], False, "Query is empty; provide a telemetry anomaly or operational question."

        with self._lock:
            if self._status != "READY" or self._index is None:
                self._validate_files()
            if self._status != "READY" or self._index is None:
                return [], False, f"Retrieval unavailable: {self._diagnostic_message}"

            threshold = self.min_similarity if min_similarity is None else min_similarity
            normalized_subsystem = normalize_subsystem_filter(subsystem)
            normalized_anomaly = anomaly_id.strip().upper() if anomaly_id and anomaly_id.strip() else None

            query_vec = _l2_normalize(self.embedding_provider.embed_query(query.strip()))
            pool_size = min(self._index.ntotal, max(top_k * 8, len(self._chunks)))
            scores, indices = self._index.search(query_vec, pool_size)

            candidates: List[RetrievedEvidenceChunk] = []
            for raw_score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._chunks):
                    continue
                chunk = self._chunks[int(idx)]
                if normalized_subsystem and chunk.subsystem != normalized_subsystem:
                    continue
                if normalized_anomaly and normalized_anomaly not in [a.upper() for a in chunk.anomaly_ids]:
                    continue

                sim = round(float(raw_score), 4)
                rank_score = _compute_ranking_score(query, chunk, sim)
                candidates.append(
                    RetrievedEvidenceChunk(
                        chunk_id=chunk.chunk_id,
                        runbook_id=chunk.runbook_id,
                        document_name=chunk.document_name,
                        document_title=chunk.document_title,
                        version=chunk.version,
                        subsystem=chunk.subsystem,
                        anomaly_ids=list(chunk.anomaly_ids),
                        section_heading=chunk.section_heading,
                        section_path=chunk.section_path,
                        similarity_score=sim,
                        ranking_score=rank_score,
                        snippet=_make_snippet(chunk),
                        text=chunk.text,
                    )
                )

            candidates.sort(key=lambda item: (item.ranking_score, item.similarity_score), reverse=True)
            selected = candidates[:top_k]

            if not selected:
                return (
                    [],
                    False,
                    "No runbook sections matched the requested query and metadata filters.",
                )

            top_similarity = max(item.similarity_score for item in selected)
            if top_similarity < threshold:
                return (
                    selected,
                    False,
                    (
                        f"Retrieved runbook similarity ({top_similarity:.2f}) is below the configured "
                        f"relevance threshold ({threshold:.2f}); evidence is insufficient to support an operational claim."
                    ),
                )

            return (
                selected,
                True,
                f"Retrieved {len(selected)} relevant runbook section(s) (top similarity {top_similarity:.2f}).",
            )


def create_default_rag_store(settings: Optional[Settings] = None) -> RAGVectorStore:
    """Construct the singleton RAGVectorStore from application settings."""
    cfg = settings or get_settings()
    provider = FastEmbedProvider(
        model_name=cfg.embedding_model_name,
        cache_dir=cfg.resolve_project_path(cfg.embedding_cache_dir),
    )
    return RAGVectorStore(
        runbooks_dir=cfg.resolve_project_path(cfg.runbooks_dir),
        index_dir=cfg.resolve_project_path(cfg.faiss_index_dir),
        embedding_provider=provider,
        min_similarity=cfg.rag_min_similarity,
    )


rag_vector_store = create_default_rag_store()
