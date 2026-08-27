"""Settings and configuration management for FitForge Agent."""

import os
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Application settings with environment variable fallback and validation."""

    execution_mode: str = Field(
        default="deterministic",
        description="Active execution mode: 'deterministic' or 'gemini'",
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash",
        description="Google Gemini model identifier for ADK execution",
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for live execution (optional in deterministic mode)",
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"],
        description="CORS allowed origins",
    )
    log_level: str = Field(default="info", description="Logging level")

    @field_validator("execution_mode")
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        mode = v.strip().lower()
        if mode not in {"deterministic", "gemini"}:
            raise ValueError(
                f"Invalid EXECUTION_MODE '{v}'. Must be either 'deterministic' or 'gemini'."
            )
        return mode

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from current OS environment variables."""
        mode = os.environ.get("EXECUTION_MODE", "deterministic")
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        origins_str = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
        origins = [o.strip() for o in origins_str.split(",") if o.strip()]
        log_level = os.environ.get("LOG_LEVEL", "info")

        return cls(
            execution_mode=mode,
            gemini_model=model,
            gemini_api_key=api_key if api_key and api_key.strip() else None,
            allowed_origins=origins,
            log_level=log_level,
        )

    @property
    def is_deterministic_mode(self) -> bool:
        return self.execution_mode == "deterministic"

    @property
    def is_gemini_mode(self) -> bool:
        return self.execution_mode == "gemini"

    def validate_credentials(self) -> None:
        """Verify required credentials exist for active mode."""
        if self.is_gemini_mode and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required when EXECUTION_MODE='gemini'."
            )

    def sanitized_dict(self) -> dict:
        """Return configuration dictionary with sensitive credentials redacted."""
        return {
            "execution_mode": self.execution_mode,
            "gemini_model": self.gemini_model,
            "has_api_key": bool(self.gemini_api_key),
            "allowed_origins": self.allowed_origins,
            "log_level": self.log_level,
        }


# Global settings singleton initialized from environment
settings = Settings.from_env()


def get_settings() -> Settings:
    """Return latest settings from environment."""
    return Settings.from_env()
