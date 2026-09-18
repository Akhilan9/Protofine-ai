"""Comprehensive pipeline test suite covering all 6 mandatory scenarios."""
import pytest
import os
from app.services.pipeline import run_evidenceguard_pipeline
from app.llm.mock_provider import MockLLMProvider
from app.llm.gemini_provider import GeminiProvider


# =========================================================================
# TEST 1: Clean supported answer
# Expected: PASS / VERIFIED
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_1_clean_supported_founding():
    provider = MockLLMProvider()
    question = "Who founded NovaTech and where is it headquartered?"
    evidence_ids = ["novatech-001"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider
    )

    assert response.check.passed is True
    assert response.check.failure_type is None
    assert response.final.status == "verified"
    assert response.final.answer == response.draft.answer
    assert "Priya Shah" in response.final.answer
    assert "2019" in response.final.answer
    assert response.provider == "mock"
    assert response.model == "deterministic-mock"


# =========================================================================
# TEST 2: Another fully supported answer
# Expected: PASS / VERIFIED
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_2_clean_supported_pricing():
    provider = MockLLMProvider()
    question = "What is the pricing for NovaSync Standard tier and how many nodes are included?"
    evidence_ids = ["novatech-004"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider
    )

    assert response.check.passed is True
    assert response.check.failure_type is None
    assert response.final.status == "verified"
    assert "$499" in response.final.answer
    assert "5 worker nodes" in response.final.answer


# =========================================================================
# TEST 3: Confident wrong answer (PRIMARY FAILURE DEMO)
# Plausible incorrect fact: Draft says 2018 instead of 2019
# Expected: FAIL -> CORRECTED
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_3_confident_wrong_draft_founding_year():
    provider = MockLLMProvider()
    # Force the plausible failure scenario in the mock
    provider.set_force_failure("plausible_founding_year_error")
    forced_wrong_draft = "NovaTech was founded in October 2018 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."

    question = "Who founded NovaTech and what year did they start the company?"
    evidence_ids = ["novatech-001"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider,
        forced_draft=forced_wrong_draft
    )

    # 1. Draft contained the subtle plausible error
    assert "2018" in response.draft.answer
    assert "2019" not in response.draft.answer

    # 2. Checker caught the grounding failure
    assert response.check.passed is False
    assert response.check.failure_type == "evidence_grounding_failure"
    contradicted = [c for c in response.check.claims if c.status == "contradicted"]
    assert len(contradicted) == 1
    assert "2018" in (contradicted[0].claim or contradicted[0].text)
    assert "novatech-001" in contradicted[0].evidence_ids

    # 3. Correction stage resolved the error using trusted evidence
    assert response.final.status == "corrected"
    assert "2019" in response.final.answer
    assert "2018" not in response.final.answer
    assert response.final.correction_notes is not None


# =========================================================================
# TEST 4: Contradicted factual claim
# Draft asserts Windows Server is supported in production
# Expected: FAIL -> CORRECTED
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_4_contradicted_windows_support():
    provider = MockLLMProvider()
    question = "Does NovaSync support production deployment on Windows Server?"
    evidence_ids = ["novatech-003"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider
    )

    # Checker caught the contradiction under evidence_grounding_failure
    assert response.check.passed is False
    assert response.check.failure_type == "evidence_grounding_failure"
    assert any(c.status == "contradicted" for c in response.check.claims)

    # Final answer corrected to reflect truth
    assert response.final.status == "corrected"
    assert "private preview" in response.final.answer.lower()
    assert "not supported in production" in response.final.answer.lower()


# =========================================================================
# TEST 5: Question not answerable from evidence
# Draft invents revenue metrics; no evidence exists
# Expected: FLAGGED / insufficient evidence
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_5_unanswerable_insufficient_evidence():
    provider = MockLLMProvider()
    question = "What was NovaTech's total annual recurring revenue and valuation in 2024?"
    evidence_ids = ["novatech-001", "novatech-002"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider
    )

    # Checker flags unsupported claims under evidence_grounding_failure
    assert response.check.passed is False
    assert response.check.failure_type == "evidence_grounding_failure"

    # Corrector refuses to guess and flags as insufficient evidence
    assert response.final.status == "flagged"
    assert "does not contain" in response.final.answer.lower() or "does not specify" in response.final.answer.lower()


# =========================================================================
# TEST 6: Multiple claims where one claim is unsupported
# Draft lists Rust, Go, PostgreSQL, and fabricated Ruby on Rails
# Expected: FAIL -> CORRECTED (removes Ruby, preserves verified tech)
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_6_multi_claim_one_unsupported():
    provider = MockLLMProvider()
    question = "What is the complete technology stack for NovaSync?"
    evidence_ids = ["novatech-006"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider
    )

    # Checker should show mixed statuses
    assert response.check.passed is False
    assert response.check.failure_type == "evidence_grounding_failure"
    statuses = [c.status for c in response.check.claims]
    assert "supported" in statuses
    assert "unsupported" in statuses

    # Final answer should preserve supported and excise unsupported
    assert response.final.status == "corrected"
    assert "Rust" in response.final.answer
    assert "Go" in response.final.answer
    assert "PostgreSQL" in response.final.answer
    assert "Ruby" not in response.final.answer


from app.config import settings

# =========================================================================
# OPTIONAL INTEGRATION TEST: Real Google Gemini API
# Only executes if GEMINI_API_KEY is configured in environment or .env
# =========================================================================
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("your_"),
    reason="GEMINI_API_KEY not configured; skipping live Gemini integration test"
)
async def test_live_gemini_integration():
    """
    Validates end-to-end structural compliance of the real Gemini integration.
    Does not assert brittle exact strings; validates response structure and status.
    """
    provider = GeminiProvider()
    question = "Who founded NovaTech and in what year was it established?"
    evidence_ids = ["novatech-001"]

    response = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider
    )

    # Validate structural properties
    assert response.provider == "gemini"
    assert response.model == provider.get_model_name()
    assert response.draft.answer != ""
    assert len(response.check.claims) > 0
    assert response.final.status in ("verified", "corrected", "flagged")
    assert response.final.answer != ""
    # Fact grounding sanity check
    assert "Priya Shah" in response.final.answer or "2019" in response.final.answer
