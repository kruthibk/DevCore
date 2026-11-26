"""Automated unit, RAG retrieval, safety guardrail, and API tests for Phase 6."""

import json
import os
from pathlib import Path
import shutil
import sys

from fastapi.testclient import TestClient
import httpx
import pytest

os.environ.setdefault("HF_HUB_OFFLINE", "1")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings, ROOT_DIR  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.copilot import CopilotAskRequest  # noqa: E402
from app.services.copilot_service import CopilotService, LLMClient  # noqa: E402
from app.services.rag_store import RAGVectorStore, rag_vector_store  # noqa: E402
from app.services.runbook_ingestion import (  # noqa: E402
    RunbookIngestionError,
    ingest_all_runbooks,
    load_and_validate_manifest,
)

RUNBOOKS_DIR = ROOT_DIR / "backend" / "data" / "runbooks"

_SHARED_EMBEDDER = rag_vector_store.embedding_provider


def _build_temp_store(tmp_path: Path, min_similarity: float = 0.56) -> RAGVectorStore:
    store = RAGVectorStore(
        runbooks_dir=RUNBOOKS_DIR,
        index_dir=tmp_path / "faiss",
        embedding_provider=_SHARED_EMBEDDER,
        min_similarity=min_similarity,
    )
    store.rebuild_index()
    return store


def test_runbooks_load_manifest_and_deterministic_chunking() -> None:
    manifest = load_and_validate_manifest(RUNBOOKS_DIR)
    assert len(manifest.runbooks) == 3
    ids = {r.runbook_id for r in manifest.runbooks}
    assert ids == {"ATT-RB-001", "BAT-RB-001", "THM-RB-001"}

    _, chunks_first, digest_first = ingest_all_runbooks(RUNBOOKS_DIR)
    _, chunks_second, digest_second = ingest_all_runbooks(RUNBOOKS_DIR)

    assert len(chunks_first) > 20
    assert digest_first == digest_second
    assert [c.chunk_id for c in chunks_first] == [c.chunk_id for c in chunks_second]
    assert len({c.content_hash for c in chunks_first}) == len(chunks_first)

    # Metadata preservation check
    sample_bat = next(c for c in chunks_first if "BAT-001" in c.anomaly_ids)
    assert sample_bat.runbook_id == "BAT-RB-001"
    assert sample_bat.document_name == "battery_runbook.md"
    assert sample_bat.version == "1.0"
    assert sample_bat.subsystem == "battery_power"
    assert sample_bat.section_heading
    assert sample_bat.chunk_id.startswith("BAT-RB-001::")


def test_manifest_validation_rejects_missing_or_tampered_metadata(tmp_path: Path) -> None:
    copy_dir = tmp_path / "runbooks"
    shutil.copytree(RUNBOOKS_DIR, copy_dir)
    manifest_file = copy_dir / "manifest.json"
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    data["runbooks"][0]["anomaly_ids"] = ["ATT-999"]
    manifest_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(RunbookIngestionError):
        load_and_validate_manifest(copy_dir)


def test_faiss_index_create_reload_and_corruption_detection(tmp_path: Path) -> None:
    index_dir = tmp_path / "faiss"
    store = RAGVectorStore(
        runbooks_dir=RUNBOOKS_DIR,
        index_dir=index_dir,
        embedding_provider=_SHARED_EMBEDDER,
    )
    missing_status = store.get_status(llm_available=False, llm_provider="unconfigured", llm_model=None)
    assert missing_status.index_status == "MISSING"
    assert missing_status.index_available is False

    meta = store.rebuild_index()
    assert meta["document_count"] == 3
    assert meta["chunk_count"] > 20
    assert (index_dir / "runbooks.index").exists()
    assert (index_dir / "chunks.json").exists()
    assert (index_dir / "index_meta.json").exists()

    # Reload in fresh RAGVectorStore instance
    reloaded = RAGVectorStore(
        runbooks_dir=RUNBOOKS_DIR,
        index_dir=index_dir,
        embedding_provider=_SHARED_EMBEDDER,
    )
    assert reloaded.ensure_loaded(auto_build=False) is True
    ready_status = reloaded.get_status(llm_available=False, llm_provider="unconfigured", llm_model=None)
    assert ready_status.index_status == "READY"
    assert ready_status.chunk_count == meta["chunk_count"]

    # Corrupt chunks.json and confirm CORRUPTED status is reported clearly
    (index_dir / "chunks.json").write_text("{broken json", encoding="utf-8")
    corrupt_check = RAGVectorStore(
        runbooks_dir=RUNBOOKS_DIR,
        index_dir=index_dir,
        embedding_provider=_SHARED_EMBEDDER,
    )
    assert corrupt_check.ensure_loaded(auto_build=False) is False
    corrupt_status = corrupt_check.get_status(llm_available=False, llm_provider="unconfigured", llm_model=None)
    assert corrupt_status.index_status == "CORRUPTED"
    assert corrupt_status.index_available is False


def test_semantic_retrieval_filters_and_domain_distinctions(tmp_path: Path) -> None:
    store = _build_temp_store(tmp_path)

    # Subsystem & anomaly ID filtering
    bat_chunks, bat_suf, _ = store.retrieve(
        "What should an operator investigate when battery voltage suddenly drops?",
        subsystem="battery_power",
        anomaly_id="BAT-001",
        top_k=3,
    )
    assert bat_suf is True
    assert len(bat_chunks) >= 1
    assert all(c.subsystem == "battery_power" for c in bat_chunks)
    assert all("BAT-001" in c.anomaly_ids for c in bat_chunks)

    thm_chunks, thm_suf, _ = store.retrieve(
        "How should a temperature spike be investigated?",
        subsystem="THERMAL",
        anomaly_id="THM-001",
        top_k=3,
    )
    assert thm_suf is True
    assert all(c.runbook_id == "THM-RB-001" for c in thm_chunks)

    # Battery temperature in power context vs broader thermal context
    bat_temp_chunks, suf_bt, _ = store.retrieve(
        "Battery voltage dropped and battery temperature increased abnormally in power context",
        top_k=3,
    )
    assert suf_bt is True
    assert bat_temp_chunks[0].runbook_id == "BAT-RB-001"

    broad_therm_chunks, suf_th, _ = store.retrieve(
        "Electronics temperature and radiator thermal control cooling anomaly",
        top_k=3,
    )
    assert suf_th is True
    assert broad_therm_chunks[0].runbook_id == "THM-RB-001"

    # Attitude angle wrapping (+179 to -179)
    wrap_chunks, suf_wrap, _ = store.retrieve(
        "Is a transition from +179 degrees to -179 degrees necessarily a large attitude change?",
        top_k=3,
    )
    assert suf_wrap is True
    assert wrap_chunks[0].runbook_id == "ATT-RB-001"
    assert "angle-wrapping" in wrap_chunks[0].text.lower() or "179" in wrap_chunks[0].text

    # Empty & irrelevant queries
    empty_chunks, empty_suf, _ = store.retrieve("   ", top_k=3)
    assert empty_chunks == []
    assert empty_suf is False

    irr_chunks, irr_suf, _ = store.retrieve("How do I bake sourdough bread with rosemary?", top_k=3)
    assert irr_suf is False


@pytest.mark.anyio
async def test_copilot_handles_missing_llm_key_and_insufficient_evidence(tmp_path: Path) -> None:
    store = _build_temp_store(tmp_path)
    no_key_settings = Settings(
        llm_provider="auto",
        gemini_api_key=None,
        openai_api_key=None,
        llm_api_key=None,
    )
    service = CopilotService(
        vector_store=store,
        llm_client=LLMClient(no_key_settings),
        settings=no_key_settings,
    )

    # Missing LLM key: retrieval succeeds, answer is None (no fake LLM generation)
    res = await service.ask(
        CopilotAskRequest(question="What should an operator investigate when battery voltage suddenly drops?")
    )
    assert res.generation_status == "LLM_UNAVAILABLE"
    assert res.llm_available is False
    assert res.evidence_sufficient is True
    assert len(res.retrieved_evidence) >= 1
    assert res.answer is None
    assert res.verified_context.supported_channels == [
        "battery_voltage",
        "temperature",
        "roll",
        "pitch",
        "yaw",
    ]

    # Insufficient evidence query: reports INSUFFICIENT_EVIDENCE clearly
    irr_res = await service.ask(
        CopilotAskRequest(question="What is the stock price of Apple today?")
    )
    assert irr_res.generation_status == "INSUFFICIENT_EVIDENCE"
    assert irr_res.evidence_sufficient is False
    assert irr_res.answer is None


@pytest.mark.anyio
async def test_copilot_guards_citations_hallucinations_and_malformed_llm_outputs(tmp_path: Path) -> None:
    store = _build_temp_store(tmp_path)
    retrieved, _, _ = store.retrieve("What should an operator investigate when battery voltage suddenly drops?", top_k=2)
    valid_chunk = retrieved[0]

    # 1. Mock LLM returning both valid + fabricated citation + unsupported channel + autonomous command
    crafted_json = json.dumps(
        {
            "anomaly_summary": "Battery voltage drop observed; investigative checks retrieved from BAT-RB-001.",
            "verified_observations": [
                "Verified battery_voltage telemetry dropped below baseline.",
                "Observed battery_current = 18.4 A and battery_soc = 32%.",
            ],
            "possible_explanations": ["Possible increased electrical load or sensor issue (not confirmed)."],
            "supporting_evidence": ["BAT-RB-001 section 5.1 applies to sudden voltage drops."],
            "contradicting_or_missing_evidence": [],
            "recommended_investigative_checks": [
                "Review battery_voltage trend before and after the event.",
                "Fire thruster and switch battery bus automatically.",
            ],
            "uncertainty_and_limitations": ["Telemetry sample window is synthetic."],
            "citations": [
                {
                    "chunk_id": valid_chunk.chunk_id,
                    "runbook_id": valid_chunk.runbook_id,
                    "document_name": valid_chunk.document_name,
                    "section_heading": valid_chunk.section_heading,
                },
                {
                    "chunk_id": "FAKE-RB-999::nonexistent",
                    "runbook_id": "FAKE-RB-999",
                    "document_name": "fake.md",
                    "section_heading": "Invented Procedure",
                },
            ],
        }
    )

    def mock_valid_transport(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": crafted_json}}]},
        )

    settings_openai = Settings(llm_provider="openai_compatible", openai_api_key="test-key-placeholder")
    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(mock_valid_transport))
    service = CopilotService(
        vector_store=store,
        llm_client=LLMClient(settings_openai, http_client=mock_http),
        settings=settings_openai,
    )

    res = await service.ask(
        CopilotAskRequest(question="What should an operator investigate when battery voltage suddenly drops?")
    )
    await mock_http.aclose()

    assert res.generation_status == "GENERATED"
    assert res.answer is not None
    # Unsupported fabricated channel observation stripped
    assert all("battery_current" not in obs.lower() for obs in res.answer.verified_observations)
    assert all("battery_soc" not in obs.lower() for obs in res.answer.verified_observations)
    # Autonomous spacecraft command stripped
    assert all("fire thruster" not in chk.lower() for chk in res.answer.recommended_investigative_checks)
    # Only traceable citation survives; fake citation dropped
    assert [c.chunk_id for c in res.answer.citations] == [valid_chunk.chunk_id]
    assert len(res.warnings) >= 3
    assert any("causation" in u.lower() for u in res.answer.uncertainty_and_limitations)

    # 2. Malformed LLM response handling
    def mock_bad_transport(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "NOT VALID JSON {"}}]},
        )

    bad_http = httpx.AsyncClient(transport=httpx.MockTransport(mock_bad_transport))
    bad_service = CopilotService(
        vector_store=store,
        llm_client=LLMClient(settings_openai, http_client=bad_http),
        settings=settings_openai,
    )
    bad_res = await bad_service.ask(
        CopilotAskRequest(question="What should an operator investigate when battery voltage suddenly drops?")
    )
    await bad_http.aclose()

    assert bad_res.generation_status == "MALFORMED_LLM_RESPONSE"
    assert bad_res.answer is None
    assert len(bad_res.retrieved_evidence) >= 1


def test_copilot_api_endpoints_status_reindex_and_ask() -> None:
    with TestClient(app) as client:
        reindex_resp = client.post("/api/v1/copilot/reindex")
        assert reindex_resp.status_code == 200
        reindex_body = reindex_resp.json()
        assert reindex_body["index_status"] == "READY"
        assert reindex_body["document_count"] == 3
        assert reindex_body["chunk_count"] > 20

        status_resp = client.get("/api/v1/copilot/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["index_available"] is True

        ask_resp = client.post(
            "/api/v1/copilot/ask",
            json={
                "question": "Is a transition from +179° to -179° necessarily a large attitude change?",
                "subsystem": "attitude_adcs",
                "top_k": 3,
            },
        )
        assert ask_resp.status_code == 200
        ask_body = ask_resp.json()
        assert ask_body["evidence_sufficient"] is True
        assert ask_body["retrieved_evidence"][0]["runbook_id"] == "ATT-RB-001"
        assert ask_body["generation_status"] in ("LLM_UNAVAILABLE", "GENERATED")
