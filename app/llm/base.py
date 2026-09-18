"""Abstract Base Class for LLM Providers."""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for LLM completion providers."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True
    ) -> str:
        """
        Generate a completion given a system prompt and user prompt.

        Args:
            system_prompt: Guiding instructions / role behavior.
            user_prompt: Specific input context and user query.
            json_mode: Whether to enforce valid JSON output format.

        Returns:
            The raw text string completion from the model.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the active model name identifier."""
        pass
