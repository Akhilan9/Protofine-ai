"""EvidenceGuard AI Pipeline orchestrator."""
import logging
import time
from typing import Optional, List
from app.models import (
    AnswerResponse,
    DraftResult,
    FinalResult
)
from app.data.loader import get_all_evidence, get_evidence_by_ids
from app.llm import get_llm_provider, LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.services.drafter import run_drafter
from app.services.checker import run_checker
from app.services.corrector import run_corrector
from app.config import settings

logger = logging.getLogger("evidenceguard.pipeline")


async def run_evidenceguard_pipeline(
    question: str,
    evidence_ids: Optional[List[str]] = None,
    provider: Optional[LLMProvider] = None,
    forced_draft: Optional[str] = None
) -> AnswerResponse:
    """
    Executes the three-stage self-check factual answer pipeline:
    1. Drafter Pass (Draft answer from evidence)
    2. Checker Pass (Adversarial claim verification against evidence)
    3. Finalization (Verified or Precision Correction Pass)
    """
    start_time = time.perf_counter()
    active_provider = provider or get_llm_provider()

    # Determine provider identity cleanly
    is_gemini = isinstance(active_provider, GeminiProvider)
    provider_name = "gemini" if is_gemini else "mock"
    model_name = active_provider.get_model_name()

    # Retrieve relevant evidence records
    if evidence_ids:
        evidence = get_evidence_by_ids(evidence_ids)
    else:
        evidence = get_all_evidence()

    if not evidence:
        raise ValueError("Evidence base is empty. Cannot evaluate factual claims without evidence.")

    logger.info(
        f"[PIPELINE_START] Question: '{question}' | EvidenceCount: {len(evidence)} | "
        f"Provider: {provider_name} | Model: {model_name}"
    )

    # ---------------------------------------------------------
    # STAGE 1: DRAFTER PASS
    # ---------------------------------------------------------
    if forced_draft:
        draft = DraftResult(answer=forced_draft, model=model_name)
        logger.info(f"[STAGE 1: DRAFT (FORCED)] {draft.answer}")
    else:
        draft = await run_drafter(question, evidence, active_provider)
        logger.info(f"[STAGE 1: DRAFT] {draft.answer}")

    # ---------------------------------------------------------
    # STAGE 2: CHECKER PASS (Adversarial Factual Audit)
    # ---------------------------------------------------------
    check = await run_checker(question, draft.answer, evidence, active_provider)
    logger.info(
        f"[STAGE 2: CHECK] Passed={check.passed} | FailureType={check.failure_type} | "
        f"ClaimsAudited={len(check.claims)}"
    )

    # ---------------------------------------------------------
    # STAGE 3: RESOLUTION & CONDITIONAL CORRECTION
    # ---------------------------------------------------------
    if check.passed:
        final = FinalResult(
            status="verified",
            answer=draft.answer,
            correction_notes="All claims independently verified against trusted evidence."
        )
        logger.info("[STAGE 3: RESOLUTION] Draft passed verification directly.")
    else:
        logger.info("[STAGE 3: CORRECTION] Check failed. Executing correction pass...")
        final = await run_corrector(question, draft.answer, check, evidence, active_provider)
        logger.info(f"[STAGE 3: CORRECTION RESULT] Status: {final.status} | Notes: {final.correction_notes}")

    elapsed = time.perf_counter() - start_time
    logger.info(
        f"[PIPELINE_COMPLETE] Status: {final.status} | Provider: {provider_name} | "
        f"Model: {model_name} | Latency: {elapsed:.3f}s | Claims: {len(check.claims)}"
    )

    return AnswerResponse(
        question=question,
        provider=provider_name,
        model=model_name,
        evidence_used=evidence,
        draft=draft,
        check=check,
        final=final
    )
