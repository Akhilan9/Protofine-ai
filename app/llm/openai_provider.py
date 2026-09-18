"""OpenAI LLM provider implementation using the official SDK."""
import logging
from typing import Optional
from openai import AsyncOpenAI, APIError, APITimeoutError, AuthenticationError
from app.llm.base import LLMProvider
from app.config import settings

logger = logging.getLogger("evidenceguard.llm.openai")


class OpenAIProvider(LLMProvider):
    """Production LLM provider using OpenAI chat completion API."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self._api_key = api_key or settings.OPENAI_API_KEY
        if not self._api_key or self._api_key.startswith("your_"):
            raise ValueError(
                "OpenAI API key is missing or placeholder. Set the OPENAI_API_KEY environment variable "
                "or switch LLM_PROVIDER to 'mock' for deterministic local testing."
            )
        self.model_name = model_name or settings.MODEL_NAME
        self.client = AsyncOpenAI(
            api_key=self._api_key,
            timeout=settings.REQUEST_TIMEOUT_SECONDS
        )

    def get_model_name(self) -> str:
        return self.model_name

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True
    ) -> str:
        try:
            kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0  # Zero temperature for factual consistency
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            logger.debug(f"Calling OpenAI API with model {self.model_name}")
            response = await self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            content = choice.message.content or "{}"
            return content

        except AuthenticationError as e:
            logger.error("OpenAI authentication failed: Invalid or expired API key")
            raise RuntimeError("OpenAI authentication failed. Please verify your OPENAI_API_KEY.") from e
        except APITimeoutError as e:
            logger.error(f"OpenAI API request timed out after {settings.REQUEST_TIMEOUT_SECONDS}s")
            raise TimeoutError(f"LLM request timed out after {settings.REQUEST_TIMEOUT_SECONDS} seconds.") from e
        except APIError as e:
            logger.error(f"OpenAI API error encountered: {e.message}")
            raise RuntimeError(f"OpenAI API error: {e.message}") from e
        except Exception as e:
            logger.error(f"Unexpected error communicating with OpenAI: {str(e)}")
            raise RuntimeError(f"LLM generation failed: {str(e)}") from e
