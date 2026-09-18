"""API route definitions for EvidenceGuard AI."""
import logging
from typing import List
from fastapi import APIRouter, HTTPException, status
from app.models import AnswerRequest, AnswerResponse, EvidenceItem, HealthResponse
from app.data.loader import get_all_evidence, get_evidence_by_ids
from app.services.pipeline import run_evidenceguard_pipeline
from app.config import settings

logger = logging.getLogger("evidenceguard.routes")

router = APIRouter(prefix="/api/v1", tags=["evidenceguard"])


@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
async def health_check():
    """Verify service readiness, active provider, and evidence dataset size."""
    evidence = get_all_evidence()
    return HealthResponse(
        status="ok",
        provider=settings.effective_provider,
        model=settings.effective_model,
        evidence_count=len(evidence)
    )


@router.get("/evidence", response_model=List[EvidenceItem], summary="Inspect Trusted Evidence Base")
async def list_evidence():
    """Retrieve all trusted factual evidence records available to the system."""
    return get_all_evidence()


@router.post("/answer", response_model=AnswerResponse, summary="Execute Self-Check Factual Answer Loop")
async def answer_question(request: AnswerRequest):
    """
    Main endpoint:
    1. Drafts an answer using LLM
    2. Runs an adversarial second pass checking for unsupported factual claims
    3. Corrects or flags the answer if errors are detected
    4. Returns a complete structured audit trail
    """
    # Validate question text
    clean_q = request.question.strip()
    if not clean_q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Question string cannot be empty or whitespace only."
        )

    # Validate evidence IDs if provided
    if request.evidence_ids:
        try:
            get_evidence_by_ids(request.evidence_ids)
        except KeyError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )

    try:
        response = await run_evidenceguard_pipeline(
            question=clean_q,
            evidence_ids=request.evidence_ids
        )
        return response
    except TimeoutError as e:
        logger.error(f"Request timeout during pipeline execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM provider timed out while evaluating factual claims."
        )
    except RuntimeError as e:
        logger.error(f"Runtime error in pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Pipeline error: {str(e)}"
        )
    except Exception as e:
        logger.exception("Unexpected error processing request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while processing the request."
        )
