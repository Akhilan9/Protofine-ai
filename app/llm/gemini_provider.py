"""Google Gemini LLM provider implementation using the official google-genai SDK."""
import asyncio
import logging
from typing import Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError
from app.llm.base import LLMProvider
from app.config import settings

logger = logging.getLogger("evidenceguard.llm.gemini")


class GeminiProvider(LLMProvider):
    """Production LLM provider using Google Gemini models via google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        if not self._api_key or self._api_key.startswith("your_"):
            raise ValueError(
                "Google Gemini API key is missing or placeholder. Set the GEMINI_API_KEY environment variable "
                "or switch LLM_PROVIDER to 'mock' for deterministic offline execution."
            )
        self.model_name = model_name or settings.GEMINI_MODEL
        self.client = genai.Client(api_key=self._api_key)

    def get_model_name(self) -> str:
        return self.model_name

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True
    ) -> str:
        """
        Generate completion using Gemini with optional JSON mode enforcement and controlled retry.
        """
        max_attempts = 2
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.0,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )
                if json_mode:
                    config.response_mime_type = "application/json"

                logger.debug(f"Calling Google Gemini API (model={self.model_name}, attempt={attempt})")
                
                # Execute with timeout guard
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=user_prompt,
                        config=config
                    ),
                    timeout=settings.REQUEST_TIMEOUT_SECONDS
                )

                content = response.text or "{}"
                return content

            except asyncio.TimeoutError as e:
                logger.error(f"Gemini API request timed out after {settings.REQUEST_TIMEOUT_SECONDS}s")
                raise TimeoutError(f"Gemini request timed out after {settings.REQUEST_TIMEOUT_SECONDS} seconds.") from e
            except APIError as e:
                status_code = getattr(e, "code", None)
                msg = str(e)
                # Check for authentication errors (do not retry)
                if status_code in (401, 403) or "API key not valid" in msg or "PERMISSION_DENIED" in msg:
                    logger.error("Gemini authentication failed: Invalid or unauthorized GEMINI_API_KEY")
                    raise RuntimeError("Gemini authentication failed. Please verify your GEMINI_API_KEY.") from e
                # Check for quota / rate limits (do not retry)
                if status_code == 429 or "RESOURCE_EXHAUSTED" in msg:
                    logger.error("Gemini rate limit or quota exceeded")
                    raise RuntimeError("Gemini API rate limit or quota exceeded.") from e
                
                logger.warning(f"Gemini API error on attempt {attempt}: {msg}")
                last_error = e
                if attempt < max_attempts:
                    await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"Unexpected error communicating with Gemini on attempt {attempt}: {str(e)}")
                last_error = e
                if attempt < max_attempts:
                    await asyncio.sleep(1.0)

        raise RuntimeError(f"Gemini generation failed after {max_attempts} attempts: {str(last_error)}")
