"""LLM Provider factory and exports."""
from typing import Optional
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.mock_provider import MockLLMProvider
from app.config import settings


def get_llm_provider(force_provider: Optional[str] = None) -> LLMProvider:
    """
    Factory function to retrieve the configured LLM provider.
    
    If force_provider is specified ('gemini' or 'mock'), returns that provider.
    Otherwise defaults according to settings.effective_provider.
    """
    target = force_provider or settings.effective_provider
    if target.lower() == "gemini":
        return GeminiProvider()
    return MockLLMProvider()


__all__ = ["LLMProvider", "GeminiProvider", "MockLLMProvider", "get_llm_provider"]
