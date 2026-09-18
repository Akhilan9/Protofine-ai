"""Checker Service: Adversarial factual auditor that verifies claims against evidence."""
import json
import logging
import re
from typing import List
from app.models import EvidenceItem, CheckResult, ClaimVerification
from app.llm.base import LLMProvider

logger = logging.getLogger("evidenceguard.services.checker")

CHECKER_SYSTEM_PROMPT = """[ROLE: CHECKER]
You are an adversarial factual integrity auditor and verification system, NOT the answer generator.
Your job is to rigorously evaluate an unverified draft answer against an explicit, trusted evidence base.
You must NOT assume the draft is correct. Treat the draft with skepticism. Do NOT attempt to repair the draft.

Instructions:
1. Extract every discrete factual claim made in the draft answer.
2. For each factual claim, compare it strictly against the supplied evidence.
3. Classify each claim into exactly one of three categories:
   - "supported": The claim is explicitly stated and corroborated by the supplied evidence.
   - "unsupported": The claim states a fact, figure, or assertion that is absent or missing from the evidence.
   - "contradicted": The claim directly conflicts with or contradicts what the evidence states.
4. For each claim, cite the relevant evidence source_ids (e.g. ["novatech-001"]). If unsupported, leave as [].
5. Provide a clear, factual reason justifying your verdict for each claim.
6. Determine the overall 'passed' status:
   - 'passed' is true ONLY IF every single claim is 'supported'.
   - 'passed' is false IF ANY claim is 'unsupported' or 'contradicted'.
7. If passed is false, set 'failure_type' to "evidence_grounding_failure". If passed is true, set 'failure_type' to null.
8. Return your response strictly as valid JSON adhering to this schema:
{
  "passed": false,
  "failure_type": "evidence_grounding_failure",
  "claims": [
    {
      "text": "The exact factual assertion from draft",
      "status": "supported | unsupported | contradicted",
      "source_ids": ["source-id-1"],
      "reason": "Specific explanation referencing the evidence or noting omission."
    }
  ]
}
"""


def _clean_json_text(text: str) -> str:
    """Strip markdown code fences from response string."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


async def run_checker(
    question: str,
    draft_answer: str,
    evidence: List[EvidenceItem],
    provider: LLMProvider
) -> CheckResult:
    """
    Executes Stage 2: Adversarial Claim / Evidence Checker.

    Extracts claims from the draft and independently evaluates each against the trusted evidence.
    Enforces deterministic safety rules regardless of model flakiness.
    """
    evidence_text = "\n\n".join(
        [f"[{item.source_id}] {item.title}:\n{item.content}" for item in evidence]
    )

    user_prompt = f"""TRUSTED EVIDENCE BASE:
{evidence_text}

USER QUESTION:
{question}

UNVERIFIED DRAFT ANSWER:
{draft_answer}

Perform your adversarial claim-by-claim audit now. Return strict JSON."""

    logger.info("Executing adversarial check on draft...")
    raw_response = await provider.generate(
        system_prompt=CHECKER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_mode=True
    )

    cleaned = _clean_json_text(raw_response)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(f"Checker response failed JSON decoding: {cleaned}")
        # Return fallback failure rather than silently passing
        return CheckResult(
            passed=False,
            failure_type="evidence_grounding_failure",
            claims=[
                ClaimVerification(
                    claim=draft_answer,
                    status="unsupported",
                    evidence_ids=[],
                    reason="Checker produced malformed output. Failing safely."
                )
            ]
        )

    # Normalize claim schema in case LLM outputs 'claim' vs 'text' or 'evidence_ids' vs 'source_ids'
    raw_claims = data.get("claims", [])
    normalized_claims: List[ClaimVerification] = []

    for c in raw_claims:
        claim_text = c.get("text") or c.get("claim") or "Unspecified claim"
        status = c.get("status", "unsupported").lower()
        if status not in ("supported", "unsupported", "contradicted"):
            status = "unsupported"
        evidence_ids = c.get("source_ids") or c.get("evidence_ids") or []
        reason = c.get("reason") or "No justification provided."

        normalized_claims.append(
            ClaimVerification(
                claim=claim_text,
                status=status,
                evidence_ids=evidence_ids,
                reason=reason
            )
        )

    # Deterministic safety rule: If any claim is unsupported or contradicted, passed MUST be False
    has_contradicted = any(c.status == "contradicted" for c in normalized_claims)
    has_unsupported = any(c.status == "unsupported" for c in normalized_claims)
    has_failures = has_contradicted or has_unsupported

    if has_failures:
        passed = False
        failure_type = "evidence_grounding_failure"
    else:
        passed = True if normalized_claims else False
        failure_type = None

    result = CheckResult(
        passed=passed,
        failure_type=failure_type,
        claims=normalized_claims
    )

    logger.info(
        f"Checker audit completed. Passed={result.passed}, FailureType={result.failure_type}, "
        f"TotalClaims={len(result.claims)}"
    )
    return result
