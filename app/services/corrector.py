"""Corrector Service: Corrects ungrounded drafts or flags unanswerable queries."""
import json
import logging
import re
from typing import List
from app.models import EvidenceItem, CheckResult, FinalResult
from app.llm.base import LLMProvider

logger = logging.getLogger("evidenceguard.services.corrector")

CORRECTOR_SYSTEM_PROMPT = """[ROLE: CORRECTOR]
You are a precision factual editor and safety corrector.
An unverified draft answer has been audited and found to contain unsupported or contradicted factual claims.

Your strict rules:
1. Ground your correction EXCLUSIVELY in the provided trusted evidence.
2. Remove any claims that were flagged as unsupported.
3. Correct any contradicted claims to match the exact factual statements in the evidence.
4. NEVER invent replacement facts, extrapolate, or guess.
5. If the evidence does NOT contain the necessary information to truthfully answer the user's question, you MUST set status to "flagged" and state clearly:
   "The available evidence does not specify [requested information]."
6. If the answer can be truthfully formed using only supported evidence facts, set status to "corrected".
7. Include concise 'correction_notes' explaining what was fixed or why it was flagged.
8. Return strict JSON adhering to this schema:
{
  "status": "corrected | flagged",
  "answer": "<Truthful, evidence-grounded answer>",
  "correction_notes": "<Brief explanation of what was fixed or why flagged>"
}
"""


def _clean_json_text(text: str) -> str:
    """Strip markdown code fences from response string."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


async def run_corrector(
    question: str,
    draft_answer: str,
    check_result: CheckResult,
    evidence: List[EvidenceItem],
    provider: LLMProvider
) -> FinalResult:
    """
    Executes Stage 3: Correction Pass.
    
    Triggered only when Stage 2 checker detects failures.
    Produces a truthful, corrected answer or flags unanswerable queries.
    """
    evidence_text = "\n\n".join(
        [f"[{item.source_id}] {item.title}:\n{item.content}" for item in evidence]
    )

    failed_claims_summary = "\n".join([
        f"- Claim: '{c.claim}' | Status: {c.status.upper()} | Reason: {c.reason}"
        for c in check_result.claims
        if c.status in ("unsupported", "contradicted")
    ])

    user_prompt = f"""TRUSTED EVIDENCE BASE:
{evidence_text}

USER QUESTION:
{question}

ORIGINAL DRAFT (CONTAINED ERRORS):
{draft_answer}

AUDIT FAILURES TO FIX:
{failed_claims_summary}

Produce your corrected or flagged final response in strict JSON."""

    logger.info("Running correction pass to resolve audit failures...")
    raw_response = await provider.generate(
        system_prompt=CORRECTOR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_mode=True
    )

    cleaned = _clean_json_text(raw_response)
    try:
        data = json.loads(cleaned)
        status = data.get("status", "corrected").lower()
        if status not in ("corrected", "flagged"):
            status = "corrected"
        answer = data.get("answer", "")
        notes = data.get("correction_notes")
    except json.JSONDecodeError:
        logger.error("Corrector output failed JSON decode; falling back to flagged status.")
        return FinalResult(
            title="FLAGGED FINAL RESULT",
            status="flagged",
            answer="The draft answer could not be safely corrected against available evidence.",
            correction_notes="Corrector output was malformed."
        )

    # Safety safeguard: if no evidence supported the claim and answer is empty
    if not answer:
        return FinalResult(
            title="FLAGGED FINAL RESULT",
            status="flagged",
            answer="The available evidence does not contain sufficient facts to answer the question.",
            correction_notes="No facts were corroborated by trusted evidence."
        )

    title = "CORRECTED FINAL RESULT" if status == "corrected" else "FLAGGED FINAL RESULT"
    return FinalResult(
        title=title,
        status=status,
        answer=answer,
        correction_notes=notes
    )
