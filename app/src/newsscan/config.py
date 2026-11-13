"""Application settings, read from environment variables (prefix NEWSSCAN_) or a local .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from newsscan import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSSCAN_", extra="ignore")

    # Infrastructure
    database_url: str = "sqlite:///./newsscan.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: Path = Path("./data/uploads")

    # Upload limits. These protect the worker from oversized or hostile files.
    max_upload_mb: int = 10
    max_pages: int = 10
    max_image_pixels: int = 40_000_000

    # OCR
    ocr_lang: str = "eng"
    ocr_timeout_seconds: int = 60

    # Claim checking (ADR-005). Both keys live in .env only. SecretStr keeps them out of reprs and logs.
    groq_api_key: SecretStr | None = None
    groq_model: str = ""  # no default on purpose: the owner picks from Groq's current model list
    fact_check_api_key: SecretStr | None = None
    max_claims_per_scan: int = 5

    # Upload rate limit per visitor (ADR-013). 0 switches that window off.
    rate_limit_per_minute: int = 10
    rate_limit_per_day: int = 100

    # Delete the uploaded file this many days after the scan (ADR-014). 0 switches cleanup off.
    upload_retention_days: int = 0

    # Operations
    log_level: str = "INFO"
    celery_always_eager: bool = False  # run tasks inline; used by tests only
    worker_metrics_port: int = 9101

    pipeline_version: str = __version__

    @property
    def claim_checking_enabled(self) -> bool:
        """Off unless every setting is present, so the OCR text is never sent out by accident."""
        return bool(self.groq_api_key and self.groq_model and self.fact_check_api_key)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
