"""Centralised, environment-driven configuration.

All secrets and tunables live in environment variables (or `.env`).
Two DB URLs are exposed: APP_DATABASE_URL (read-write) and READONLY_DATABASE_URL
(SELECT-only user restricted to allow-listed tables). The NL2SQL service must
use the read-only URL only. Use get_settings() (cached) to access.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment and `.env`.

    Keys (env):
        GEMINI_API_KEY           : Google Gemini API key
        GEMINI_MODEL             : model name (default gemini-2.5-flash)
        APP_DATABASE_URL         : SQLAlchemy URL for app (read-write)
        READONLY_DATABASE_URL    : SQLAlchemy URL for SELECT-only NL2SQL user
        REDIS_URL                : redis://host:port/db
        CORS_ALLOW_ORIGINS       : comma-separated origins (default http://localhost:5173)
        LANGFUSE_ENABLED         : 'true' to forward Gemini calls to Langfuse
        LANGFUSE_PUBLIC_KEY/SECRET/HOST
        ALLOWED_TABLES           : comma-separated NL2SQL whitelist
    """

    # --- LLM ---
    groq_api_key: str = Field("dummy", alias="GROQ_API_KEY")
    llm_model: str = Field("llama-3.3-70b-versatile", alias="LLM_MODEL")

    # --- DBs ---
    app_database_url: str = Field(
        "mysql+aiomysql://dashboard_app:app_pw@mysql:3306/school_db",
        alias="APP_DATABASE_URL",
    )
    readonly_database_url: str = Field(
        "mysql+aiomysql://nl2sql_reader:reader_pw@mysql:3306/school_db",
        alias="READONLY_DATABASE_URL",
    )

    # --- Redis ---
    redis_url: str = Field("redis://redis:6379/0", alias="REDIS_URL")

    # --- CORS ---
    cors_allow_origins: str = Field(
        "http://localhost:5173,http://localhost:3000", alias="CORS_ALLOW_ORIGINS"
    )

    # --- Observability / Langfuse ---
    langfuse_enabled: bool = Field(False, alias="LANGFUSE_ENABLED")
    langfuse_public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field("", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field("https://us.cloud.langfuse.com", alias="LANGFUSE_HOST")

    # --- NL2SQL allow-list (defense in depth alongside the read-only DB user) ---
    allowed_tables: str = Field(
        "students,teachers,classes,attendance,assessments,assignments,fees,"
        "behavior_notes,student_summary,alerts,digests,chat_logs,courses,fee_invoices,payments,users",
        alias="ALLOWED_TABLES",
    )
    
    # --- NL2SQL Safety ---
    nl2sql_confidence_threshold: float = Field(0.5, alias="NL2SQL_CONFIDENCE_THRESHOLD")

    # --- Cache TTLs (seconds) ---
    dashboard_cache_ttl: int = 300         # 5 min
    narrative_cache_ttl: int = 3600        # 1 hr

    # --- App ---
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Helpers ----------------------------------------------------------

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def allowed_tables_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_tables.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached Settings accessor (avoid re-parsing env on every request)."""
    return Settings()
