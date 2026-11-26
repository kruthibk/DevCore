"""Versioned REST endpoints for Runbook RAG indexing and AI Copilot triage."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.schemas.copilot import CopilotAskRequest, CopilotAskResponse, CopilotStatusResponse
from app.services.copilot_service import copilot_service
from app.services.rag_store import RAGIndexError

router = APIRouter(prefix="/copilot", tags=["AI Copilot & RAG"])


@router.get(
    "/status",
    response_model=CopilotStatusResponse,
    summary="Get FAISS index health, embedding metadata, and LLM availability",
)
def get_copilot_status(
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> CopilotStatusResponse:
    return copilot_service.get_status()


@router.post(
    "/ask",
    response_model=CopilotAskResponse,
    summary="Retrieve grounded runbook evidence and generate investigative triage guidance",
)
async def ask_copilot(
    payload: CopilotAskRequest,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> CopilotAskResponse:
    return await copilot_service.ask(request=payload, db=db)


@router.post(
    "/reindex",
    response_model=CopilotStatusResponse,
    summary="Deterministically rebuild and validate the runbook FAISS vector index",
)
def reindex_runbooks(
    _: ActorContext = Depends(require_roles("ADMIN")),
) -> CopilotStatusResponse:
    try:
        return copilot_service.reindex()
    except RAGIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
