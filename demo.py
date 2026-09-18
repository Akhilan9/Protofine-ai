"""Standalone deterministic demo CLI for EvidenceGuard AI self-check loop."""
import asyncio
import argparse
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.llm.mock_provider import MockLLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.services.pipeline import run_evidenceguard_pipeline
from app.data.loader import get_evidence_by_ids


async def main():
    parser = argparse.ArgumentParser(description="EvidenceGuard AI Self-Check Loop Demonstration")
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real Google Gemini API instead of deterministic mock (requires GEMINI_API_KEY)"
    )
    args = parser.parse_args()

    # Define the primary failure scenario
    question = "Who founded NovaTech and what year did they start the company?"
    evidence_ids = ["novatech-001"]

    if args.real:
        print("\n[INFO] Running demo with REAL Google Gemini API...")
        provider = GeminiProvider()
        forced_draft = None
    else:
        print("\n[INFO] Running demo with DETERMINISTIC mock provider (no API key required)...")
        provider = MockLLMProvider()
        # Force the plausible failure scenario in the mock
        provider.set_force_failure("plausible_founding_year_error")
        # Plausible wrong draft that looks completely believable to a human
        forced_draft = "NovaTech was founded in October 2018 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."

    evidence_records = get_evidence_by_ids(evidence_ids)
    evidence_summary = "\n".join([f"[{e.source_id}] {e.content}" for e in evidence_records])

    # Run the 3-stage pipeline
    result = await run_evidenceguard_pipeline(
        question=question,
        evidence_ids=evidence_ids,
        provider=provider,
        forced_draft=forced_draft
    )

    print("\n" + "=" * 60)
    print("       EVIDENCEGUARD SELF-CHECK DEMO")
    print("=" * 60)
    print(f"PROVIDER: {result.provider}")
    print(f"MODEL:    {result.model}")
    print("\nQUESTION:")
    print(result.question)

    print("\nTRUSTED EVIDENCE:")
    print(evidence_summary)

    print("\nFIRST LLM DRAFT:")
    print(f"\"{result.draft.answer}\"")

    print("\nCHECK RESULT:")
    if result.check.passed:
        print("PASSED")
    else:
        print("FAILED")
        print(f"\nFAILURE FAMILY:\n{result.check.failure_type}")
        print("\nCLAIM-BY-CLAIM SKEPTICAL AUDIT:")
        for c in result.check.claims:
            badge = f"[{c.status.upper()}]"
            claim_text = getattr(c, "claim", getattr(c, "text", ""))
            sources = f"(Sources: {', '.join(c.evidence_ids)})" if c.evidence_ids else "(No source match)"
            print(f"  * {badge:<16} {sources}")
            print(f"    Claim:  \"{claim_text}\"")
            print(f"    Reason: {c.reason}\n")
    stage3_title = getattr(result.final, "title", None) or (
        "FINAL VERIFIED RESULT" if result.final.status == "verified"
        else "CORRECTED FINAL RESULT" if result.final.status == "corrected"
        else "FLAGGED FINAL RESULT"
    )
    print(f"\n{stage3_title}:")
    print(f"\"{result.final.answer}\"")

    print("\nFINAL STATUS:")
    print(result.final.status.upper())
    if result.final.correction_notes:
        print(f"Audit Notes: {result.final.correction_notes}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
