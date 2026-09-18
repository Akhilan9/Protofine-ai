"""Deterministic Mock LLM Provider for offline testing and reproducible failure demonstrations."""
import json
import logging
from typing import Optional, List, Dict, Any, Callable
from app.llm.base import LLMProvider

logger = logging.getLogger("evidenceguard.llm.mock")


class MockLLMProvider(LLMProvider):
    """
    Deterministic LLM provider that simulates realistic LLM outputs.
    Allows exact replication of the self-check loop and intentional failure scenarios
    without requiring an active network connection or external API credentials.
    """

    def __init__(self, model_name: str = "mock-gpt-4o-mini"):
        self.model_name = model_name
        self._queued_responses: List[str] = []
        self._force_failure_scenario: Optional[str] = None
        self._custom_handler: Optional[Callable[[str, str], Optional[str]]] = None

    def get_model_name(self) -> str:
        return self.model_name

    def queue_response(self, response: str) -> None:
        """Enqueue a specific raw response for the next generate call."""
        self._queued_responses.append(response)

    def set_force_failure(self, scenario_name: Optional[str]) -> None:
        """Force a specific failure scenario (e.g., 'plausible_founding_year_error')."""
        self._force_failure_scenario = scenario_name

    def set_custom_handler(self, handler: Optional[Callable[[str, str], Optional[str]]]) -> None:
        """Set a dynamic callback handler for custom mock logic."""
        self._custom_handler = handler

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True
    ) -> str:
        # Check explicitly queued responses first
        if self._queued_responses:
            return self._queued_responses.pop(0)

        # Check custom handler if registered
        if self._custom_handler:
            custom_res = self._custom_handler(system_prompt, user_prompt)
            if custom_res is not None:
                return custom_res

        # Mutually exclusive role detection based on strict role tags
        lower_sys = system_prompt.lower()
        is_checker = "[role: checker]" in lower_sys or "adversarial factual integrity auditor" in lower_sys
        is_corrector = "[role: corrector]" in lower_sys or "precision factual editor" in lower_sys
        is_drafter = not (is_checker or is_corrector) and ("[role: drafter]" in lower_sys or "drafter" in lower_sys or "draft" in lower_sys)

        # Extract the question portion from user prompt to prevent accidental matches on evidence text
        import re
        q_match = re.search(r"(?:user question|question):\s*(.+?)(?:\n|$)", user_prompt, re.IGNORECASE)
        q_text = q_match.group(1).strip().lower() if q_match else user_prompt.lower()
        lower_user = user_prompt.lower()

        # =========================================================================
        # Scenario 5: Unanswerable Question (Revenue / Valuation)
        # Evaluated first to avoid overlap
        # =========================================================================
        if "revenue" in q_text or "valuation" in q_text or "arr" in q_text:
            if is_drafter:
                # Plausible hallucination of ungrounded financial metrics
                return json.dumps({
                    "answer": "NovaTech generated $15M in annual recurring revenue in 2024 with a $95M valuation."
                })
            if is_checker:
                return json.dumps({
                    "passed": False,
                    "failure_type": "unsupported_fact",
                    "claims": [
                        {
                            "claim": "NovaTech generated $15M in ARR in 2024",
                            "status": "unsupported",
                            "evidence_ids": [],
                            "reason": "No evidence provides annual recurring revenue data for NovaTech."
                        },
                        {
                            "claim": "NovaTech has a $95M valuation",
                            "status": "unsupported",
                            "evidence_ids": [],
                            "reason": "No evidence contains valuation figures for NovaTech."
                        }
                    ]
                })
            if is_corrector:
                return json.dumps({
                    "status": "flagged",
                    "answer": "The provided evidence does not contain information regarding NovaTech's annual revenue or valuation.",
                    "correction_notes": "All claims were unsupported by evidence. Question flagged as unanswerable from available knowledge base."
                })

        # =========================================================================
        # Scenario 1 & Scenario 3: Founding & Leadership
        # =========================================================================
        if "who founded" in q_text or "founding" in q_text or "start the company" in q_text:
            if is_drafter:
                # If failure scenario is active or forced, return plausible incorrect draft (2018 instead of 2019)
                if self._force_failure_scenario == "plausible_founding_year_error":
                    return json.dumps({
                        "answer": "NovaTech was founded in October 2018 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."
                    })
                # Otherwise standard accurate draft
                return json.dumps({
                    "answer": "NovaTech was founded in October 2019 by Dr. Priya Shah and Marcus Vance in Seattle, Washington."
                })

            if is_checker:
                if "2018" in lower_user:
                    return json.dumps({
                        "passed": False,
                        "failure_type": "contradicted_fact",
                        "claims": [
                            {
                                "claim": "NovaTech was founded in October 2018",
                                "status": "contradicted",
                                "evidence_ids": ["novatech-001"],
                                "reason": "Evidence explicitly states NovaTech was founded in October 2019, contradicting the draft's claim of 2018."
                            },
                            {
                                "claim": "NovaTech was founded by Dr. Priya Shah and Marcus Vance",
                                "status": "supported",
                                "evidence_ids": ["novatech-001"],
                                "reason": "Corroborated by source novatech-001."
                            },
                            {
                                "claim": "NovaTech is headquartered in Seattle, Washington",
                                "status": "supported",
                                "evidence_ids": ["novatech-001"],
                                "reason": "Corroborated by source novatech-001."
                            }
                        ]
                    })
                return json.dumps({
                    "passed": True,
                    "failure_type": None,
                    "claims": [
                        {
                            "claim": "NovaTech was founded in October 2019 by Dr. Priya Shah and Marcus Vance",
                            "status": "supported",
                            "evidence_ids": ["novatech-001"],
                            "reason": "Directly stated in novatech-001."
                        },
                        {
                            "claim": "The company is headquartered in Seattle, Washington",
                            "status": "supported",
                            "evidence_ids": ["novatech-001"],
                            "reason": "Directly stated in novatech-001."
                        }
                    ]
                })

            if is_corrector:
                return json.dumps({
                    "status": "corrected",
                    "answer": "NovaTech was founded in October 2019 by Dr. Priya Shah and Marcus Vance in Seattle, Washington.",
                    "correction_notes": "Corrected founding year from 2018 to 2019 based on source novatech-001."
                })

        # =========================================================================
        # Scenario 2: Pricing & Packaging
        # =========================================================================
        if "pricing" in lower_user or "cost" in lower_user or "standard tier" in lower_user:
            if is_drafter:
                return json.dumps({
                    "answer": "NovaSync Standard tier costs $499 per month per cluster, covering up to 5 worker nodes."
                })
            if is_checker:
                return json.dumps({
                    "passed": True,
                    "failure_type": None,
                    "claims": [
                        {
                            "claim": "NovaSync Standard tier costs $499 per month per cluster",
                            "status": "supported",
                            "evidence_ids": ["novatech-004"],
                            "reason": "Directly stated in novatech-004."
                        },
                        {
                            "claim": "NovaSync Standard tier covers up to 5 worker nodes",
                            "status": "supported",
                            "evidence_ids": ["novatech-004"],
                            "reason": "Directly stated in novatech-004."
                        }
                    ]
                })
            if is_corrector:
                return json.dumps({
                    "status": "verified",
                    "answer": "NovaSync Standard tier costs $499 per month per cluster, covering up to 5 worker nodes.",
                    "correction_notes": None
                })

        # =========================================================================
        # Scenario 4: Contradicted Platform Support (Windows Server)
        # =========================================================================
        if "windows" in lower_user or "platforms" in lower_user:
            if is_drafter:
                return json.dumps({
                    "answer": "NovaSync officially supports production deployments on Linux, Kubernetes 1.25+, and Windows Server."
                })
            if is_checker:
                return json.dumps({
                    "passed": False,
                    "failure_type": "contradicted_fact",
                    "claims": [
                        {
                            "claim": "NovaSync officially supports server installations on Linux and Kubernetes",
                            "status": "supported",
                            "evidence_ids": ["novatech-003"],
                            "reason": "Directly supported by novatech-003."
                        },
                        {
                            "claim": "NovaSync supports Windows Server in production",
                            "status": "contradicted",
                            "evidence_ids": ["novatech-003"],
                            "reason": "novatech-003 states Windows Server is in invite-only private preview and NOT supported in production."
                        }
                    ]
                })
            if is_corrector:
                return json.dumps({
                    "status": "corrected",
                    "answer": "NovaSync officially supports server installations on Linux distributions and Kubernetes 1.25+. Windows Server is currently in invite-only private preview and is not supported in production.",
                    "correction_notes": "Resolved contradiction: clarified that Windows Server is only in private preview and not supported for production."
                })


        # =========================================================================
        # Scenario 6: Multi-claim with one fabricated fact (Ruby on Rails)
        # =========================================================================
        if "technology stack" in lower_user or "languages" in lower_user or "ruby" in lower_user:
            if is_drafter:
                return json.dumps({
                    "answer": "NovaSync's core streaming engine is written in Rust, APIs are developed in Go with gRPC, metadata persistence uses PostgreSQL, and the frontend dashboard is written in Ruby on Rails."
                })
            if is_checker:
                return json.dumps({
                    "passed": False,
                    "failure_type": "unsupported_fact",
                    "claims": [
                        {
                            "claim": "NovaSync core streaming engine is written in Rust",
                            "status": "supported",
                            "evidence_ids": ["novatech-006"],
                            "reason": "Corroborated by novatech-006."
                        },
                        {
                            "claim": "Management plane APIs are developed in Go with gRPC",
                            "status": "supported",
                            "evidence_ids": ["novatech-006"],
                            "reason": "Corroborated by novatech-006."
                        },
                        {
                            "claim": "Metadata persistence is handled via clustered PostgreSQL",
                            "status": "supported",
                            "evidence_ids": ["novatech-006"],
                            "reason": "Corroborated by novatech-006."
                        },
                        {
                            "claim": "Frontend dashboard is written in Ruby on Rails",
                            "status": "unsupported",
                            "evidence_ids": [],
                            "reason": "No evidence mentions a frontend dashboard or Ruby on Rails."
                        }
                    ]
                })
            if is_corrector:
                return json.dumps({
                    "status": "corrected",
                    "answer": "NovaSync's core streaming engine is written in Rust, management plane APIs are developed in Go with gRPC, and metadata persistence is handled via clustered PostgreSQL.",
                    "correction_notes": "Removed unsupported claim regarding Ruby on Rails frontend dashboard."
                })

        # Fallback default responses
        if is_drafter:
            return json.dumps({"answer": "Based on the evidence, NovaTech operates NovaSync for enterprise data streaming."})
        if is_checker:
            return json.dumps({
                "passed": True,
                "failure_type": None,
                "claims": [
                    {
                        "claim": "NovaTech operates NovaSync",
                        "status": "supported",
                        "evidence_ids": ["novatech-002"],
                        "reason": "Supported by product overview."
                    }
                ]
            })
        if is_corrector:
            return json.dumps({
                "status": "verified",
                "answer": "Based on the evidence, NovaTech operates NovaSync for enterprise data streaming.",
                "correction_notes": None
            })

        return json.dumps({"status": "ok"})
