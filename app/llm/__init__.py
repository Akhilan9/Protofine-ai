"""LLM Provider factory and exports."""
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.mock_provider import MockLLMProvider
from app.config import settings


def get_llm_provider(force_provider: str = None) -> LLMProvider:
    """
    Factory function to retrieve the configured LLM provider.
    
    If force_provider is specified ('openai' or 'mock'), returns that provider.
    Otherwise defaults according to settings.effective_provider.
    """
    target = force_provider or settings.effective_provider
    if target.lower() == "openai":
        return OpenAIProvider()
    return MockLLMProvider()


__all__ = ["LLMProvider", "OpenAIProvider", "MockLLMProvider", "get_llm_provider"]
