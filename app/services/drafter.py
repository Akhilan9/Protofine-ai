"""Drafter Service: Generates the initial answer from evidence."""
import json
import logging
import re
from typing import List
from app.models import EvidenceItem, DraftResult
from app.llm.base import LLMProvider

logger = logging.getLogger("evidenceguard.services.drafter")

DRAFTER_SYSTEM_PROMPT = """[ROLE: DRAFTER]
You are an AI assistant responsible for generating an initial answer to the user's question.
Your instructions:
1. Ground your answer in the provided evidence.
2. Formulate a direct, concise, and helpful answer.
3. If the evidence does not contain sufficient information to answer the question, state that clearly.
4. Do NOT include extraneous speculation.
5. Return your response strictly as valid JSON matching this schema:
{
  "answer": "Your direct factual response here."
}
"""


def _clean_json_text(text: str) -> str:
    """Strip markdown code blocks or trailing garbage from LLM response."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


async def run_drafter(
    question: str,
    evidence: List[EvidenceItem],
    provider: LLMProvider
) -> DraftResult:
    """
    Executes Stage 1: Drafter pass.
    
    Generates a draft answer using the provided evidence base.
    The raw output is preserved without artificial pre-filtering to expose genuine LLM behavior.
    """
    evidence_text = "\n\n".join(
        [f"[{item.source_id}] {item.title}:\n{item.content}" for item in evidence]
    )

    user_prompt = f"""EVIDENCE BASE:
{evidence_text}

QUESTION:
{question}

Provide your answer in strict JSON format:
{{"answer": "<concise answer>"}}"""

    logger.info(f"Generating initial draft for question: '{question[:60]}...'")
    raw_response = await provider.generate(
        system_prompt=DRAFTER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_mode=True
    )

    cleaned = _clean_json_text(raw_response)
    try:
        parsed = json.loads(cleaned)
        answer_text = parsed.get("answer", cleaned)
    except json.JSONDecodeError:
        logger.warning("Drafter did not return strict JSON; using cleaned text directly.")
        answer_text = cleaned

    return DraftResult(
        answer=answer_text,
        model=provider.get_model_name()
    )
