"""BE-00: Config and environment wiring. Loads from .env; no secrets in code."""
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),  # repo root or backend/
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str  # Project Settings → API → JWT Secret
    # JWT validation: issuer must match (e.g. https://<project-ref>.supabase.co/auth/v1)
    supabase_jwt_issuer: str = ""
    # Optional; default "authenticated" used if empty
    supabase_jwt_audience: str = "authenticated"
    # Clock skew leeway in seconds for exp/iat (30–60s recommended)
    supabase_jwt_leeway_seconds: int = 60

    @property
    def supabase_url_stripped(self) -> str:
        return self.supabase_url.rstrip("/")

    @property
    def jwt_issuer(self) -> str:
        """Issuer for JWT verification; derived from URL if not set."""
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer.rstrip("/")
        return f"{self.supabase_url_stripped}/auth/v1"

    @property
    def jwt_audience(self) -> str:
        return (self.supabase_jwt_audience or "authenticated").strip() or "authenticated"

    # BE-10: Embedding provider (OpenAI); single model per deployment
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    default_fast_model: str = "gpt-4o-mini"
    default_reasoning_model: str = "claude-3-5-sonnet-20241022"
    default_embedding_model: str = "text-embedding-3-small"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = 1536
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 8

    # IN-00: Fernet key for connector_secrets (generate: from cryptography.fernet import Fernet; Fernet.generate_key())
    connector_secrets_encryption_key: str = ""
    # Phase 15: AES-256-GCM key for connector/source config (32-byte base64 or raw)
    encryption_key: str = ""

    # Gravitre core DB URL (optional; Supabase used for default storage)
    database_url: str = ""

    # Stripe Billing (MVP)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_starter: str = ""
    stripe_price_id_growth: str = ""
    stripe_price_id_scale: str = ""
    stripe_price_id_node_monthly: str = ""
    stripe_price_id_node_annual: str = ""
    stripe_price_id_control_monthly: str = ""
    stripe_price_id_control_annual: str = ""
    stripe_price_id_command_monthly: str = ""
    stripe_price_id_command_annual: str = ""
    public_app_url: str = Field(default="", alias="NEXT_PUBLIC_APP_URL")

    # Phase 6: kill switches (default off)
    disable_execute: bool = False
    disable_connectors: bool = False
    disable_ingestion: bool = False

    # Phase 7: policy engine defaults (0/empty = disabled)
    policy_max_steps: int = 0
    policy_max_runtime_seconds: int = 0
    policy_allowed_envs: str = ""

    @model_validator(mode="after")
    def _validate_required_secrets(self) -> "Settings":
        env = (self.app_env or "dev").strip().lower()
        if env in {"prod", "production", "staging"}:
            missing: list[str] = []
            if not (self.openai_api_key or "").strip():
                missing.append("OPENAI_API_KEY")
            if not (self.connector_secrets_encryption_key or "").strip():
                missing.append("CONNECTOR_SECRETS_ENCRYPTION_KEY")
            if missing:
                raise ValueError(f"Missing required settings for {env}: {', '.join(missing)}")
        return self


def get_settings() -> Settings:
    return Settings()
