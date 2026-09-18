"""Application configuration and environment management."""
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Settings
    OPENAI_API_KEY: Optional[str] = None
    MODEL_NAME: str = "gpt-4o-mini"
    LLM_PROVIDER: str = "mock"  # Can be "openai" or "mock"
    REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    @property
    def effective_provider(self) -> str:
        """Automatically use 'openai' if an explicit key is provided and LLM_PROVIDER is not explicitly 'mock'."""
        if self.LLM_PROVIDER.lower() == "openai" or (self.OPENAI_API_KEY and self.LLM_PROVIDER.lower() != "mock"):
            return "openai"
        return "mock"


settings = Settings()
