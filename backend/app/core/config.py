from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cloudtab:cloudtab_dev@localhost:5432/cloudtab"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://cloudtab:cloudtab_dev@localhost:5432/cloudtab"

    @model_validator(mode="after")
    def _normalise_db_urls(self) -> "Settings":
        # Accept legacy postgres:// or plain postgresql:// and upgrade to the
        # correct SQLAlchemy 2.x async dialect string.
        for old, new in (
            ("postgres://", "postgresql+asyncpg://"),
            ("postgresql://", "postgresql+asyncpg://"),
        ):
            if self.DATABASE_URL.startswith(old):
                self.DATABASE_URL = self.DATABASE_URL.replace(old, new, 1)
                break

        # Always derive the sync URL from the (now normalised) async URL so
        # only DATABASE_URL needs to be set in the environment.
        self.DATABASE_URL_SYNC = self.DATABASE_URL.replace("+asyncpg", "+psycopg2", 1)
        return self

    # Redis — use the compose service name so it works in any Docker deployment
    # without needing to set REDIS_URL explicitly
    REDIS_URL: str = "redis://redis:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption
    ENCRYPTION_KEY: str = "change-me-generate-with-fernet"

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Admin seed
    ADMIN_EMAIL: str = "admin@cloudtab.local"
    ADMIN_PASSWORD: str = "changeme123"

    # Logging
    LOG_LEVEL: str = "INFO"

    # S3 (optional — only needed when backup storage_type is "s3")
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str | None = None  # For MinIO / S3-compatible services


settings = Settings()
