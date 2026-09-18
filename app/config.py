"""Application configuration and environment management for Google Gemini & Mock providers."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Google Gemini Settings
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_PROVIDER: str = "mock"  # "gemini" or "mock"
    REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    @property
    def effective_provider(self) -> str:
        """Return 'gemini' if explicitly selected or if an active key is present without an explicit 'mock' setting."""
        if self.LLM_PROVIDER.lower() == "gemini":
            return "gemini"
        if self.GEMINI_API_KEY and self.LLM_PROVIDER.lower() != "mock":
            return "gemini"
        return "mock"

    @property
    def effective_model(self) -> str:
        """Return the actual configured model name according to active provider."""
        if self.effective_provider == "gemini":
            return self.GEMINI_MODEL
        return "deterministic-mock"


settings = Settings()
