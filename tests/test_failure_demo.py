"""Dedicated reproducible verification of the primary failure demonstration."""
import pytest
from app.services.pipeline import run_evidenceguard_pipeline
from app.llm.mock_provider import MockLLMProvider
from app.data.loader import get_evidence_by_id


@pytest.mark.asyncio
async def test_intentional_failure_story_reproducibility():
    """
    Formally proves the three conditions of the self-check loop:
    1. DRAFT != TRUTH (Drafter generates plausible error: 2018 instead of 2019)
    2. CHECK = FAIL   (Adversarial auditor detects contradicted founding year under evidence_grounding_failure)
    3. CORRECTION = SUCCESS (Corrector replaces 2018 with 2019 based strictly on evidence)
    """
    provider = MockLLMProvider()
    evidence_id = "novatech-001"
    evidence_item = get_evidence_by_id(evidence_id)
    assert evidence_item is not None

    truth_year = "2019"
    hallucinated_year = "2018"
    assert truth_year in evidence_item.content
    assert hallucinated_year not in evidence_item.content

    # Inject plausible wrong draft
    plausible_wrong_draft = (
        "NovaTech was founded in October 2018 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."
    )

    response = await run_evidenceguard_pipeline(
        question="Who founded NovaTech and what year did they start?",
        evidence_ids=[evidence_id],
        provider=provider,
        forced_draft=plausible_wrong_draft
    )

    # 1. PROVE: DRAFT != TRUTH
    assert hallucinated_year in response.draft.answer, "Draft must contain the incorrect year."
    assert truth_year not in response.draft.answer, "Draft must NOT contain the truth year."

    # 2. PROVE: CHECK = FAIL
    assert response.check.passed is False, "Checker must FAIL on contradicted/unsupported draft."
    assert response.check.failure_type == "evidence_grounding_failure"
    contradicted_claims = [c for c in response.check.claims if c.status == "contradicted"]
    assert len(contradicted_claims) > 0, "Must identify the specific contradicted claim."
    claim_text = getattr(contradicted_claims[0], "claim", getattr(contradicted_claims[0], "text", ""))
    assert hallucinated_year in claim_text
    assert evidence_id in contradicted_claims[0].evidence_ids

    # 3. PROVE: CORRECTION = SUCCESS
    assert response.final.status == "corrected", "Final status must be 'corrected'."
    assert truth_year in response.final.answer, "Final answer must restore the ground truth (2019)."
    assert hallucinated_year not in response.final.answer, "Final answer must eliminate the hallucination (2018)."
    assert "Priya Shah" in response.final.answer, "Final answer must preserve valid supported facts."
