"""Unit tests for the Adversarial Claim / Evidence Checker service."""
import pytest
import json
from app.models import EvidenceItem
from app.services.checker import run_checker, _clean_json_text
from app.llm.mock_provider import MockLLMProvider


@pytest.fixture
def sample_evidence():
    return [
        EvidenceItem(
            source_id="novatech-001",
            title="Company Founding",
            content="NovaTech was founded in October 2019 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."
        )
    ]


@pytest.mark.asyncio
async def test_clean_json_text_markdown_stripping():
    raw = "```json\n{\"passed\": true, \"claims\": []}\n```"
    cleaned = _clean_json_text(raw)
    assert cleaned == '{"passed": true, "claims": []}'

    raw_no_lang = "```\n{\"passed\": false}\n```"
    assert _clean_json_text(raw_no_lang) == '{"passed": false}'


@pytest.mark.asyncio
async def test_checker_all_claims_supported(sample_evidence):
    provider = MockLLMProvider()
    question = "Who founded NovaTech?"
    draft = "NovaTech was founded in October 2019 by Dr. Priya Shah and Marcus Vance."

    result = await run_checker(question, draft, sample_evidence, provider)

    assert result.passed is True
    assert result.failure_type is None
    assert len(result.claims) >= 1
    for c in result.claims:
        assert c.status == "supported"
        assert "novatech-001" in c.evidence_ids


@pytest.mark.asyncio
async def test_checker_detects_contradicted_claim(sample_evidence):
    provider = MockLLMProvider()
    question = "Who founded NovaTech?"
    draft = "NovaTech was founded in October 2018 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."

    result = await run_checker(question, draft, sample_evidence, provider)

    assert result.passed is False
    assert result.failure_type == "evidence_grounding_failure"
    contradicted = [c for c in result.claims if c.status == "contradicted"]
    assert len(contradicted) == 1
    assert "2018" in (contradicted[0].claim or contradicted[0].text)
    assert "novatech-001" in contradicted[0].evidence_ids


@pytest.mark.asyncio
async def test_checker_detects_unsupported_claim(sample_evidence):
    provider = MockLLMProvider()
    question = "What was NovaTech's revenue in 2024?"
    draft = "NovaTech generated $15M in annual recurring revenue in 2024 with a $95M valuation."

    result = await run_checker(question, draft, sample_evidence, provider)

    assert result.passed is False
    assert result.failure_type == "evidence_grounding_failure"
    assert any(c.status == "unsupported" for c in result.claims)


@pytest.mark.asyncio
async def test_checker_safety_rule_overrides_hallucinated_passed(sample_evidence):
    """
    Even if the LLM produces passed=true, if a claim is unsupported/contradicted,
    our deterministic safety code must enforce passed=False and failure_type=evidence_grounding_failure.
    """
    provider = MockLLMProvider()
    # Queue a response where the LLM claims passed: true despite an unsupported claim
    flawed_llm_json = json.dumps({
        "passed": True,  # Flawed LLM hallucination
        "failure_type": None,
        "claims": [
            {
                "claim": "NovaTech has 500 offices worldwide",
                "status": "unsupported",
                "evidence_ids": [],
                "reason": "Not in evidence"
            }
        ]
    })
    provider.queue_response(flawed_llm_json)

    result = await run_checker("How many offices does NovaTech have?", "NovaTech has 500 offices worldwide", sample_evidence, provider)

    # Safety rule should force passed to False
    assert result.passed is False
    assert result.failure_type == "evidence_grounding_failure"


@pytest.mark.asyncio
async def test_checker_malformed_json_fails_safely(sample_evidence):
    """If the LLM returns invalid non-JSON output, the checker must fail safely."""
    provider = MockLLMProvider()
    provider.queue_response("Sorry, I cannot format this as JSON.")

    result = await run_checker("Who founded NovaTech?", "NovaTech was founded in 2019", sample_evidence, provider)

    assert result.passed is False
    assert result.failure_type == "evidence_grounding_failure"
    assert len(result.claims) == 1
    assert "Failing safely" in result.claims[0].reason
