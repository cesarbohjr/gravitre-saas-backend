"""BE-00: Config and environment wiring. Loads from .env; no secrets in code."""
from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.connectors.secret_key import validate_connector_secrets_encryption_key


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
    supabase_jwt_secret: str  # Legacy HS256 secret; ES256 tokens verified via JWKS
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

    @property
    def embedding_model(self) -> str:
        """Single embedding model source of truth.

        Prefer DEFAULT_EMBEDDING_MODEL while keeping backward compatibility with
        OPENAI_EMBEDDING_MODEL for existing deployments.
        """
        return (
            (self.default_embedding_model or "").strip()
            or (self.openai_embedding_model or "").strip()
            or "text-embedding-3-small"
        )

    # BE-10: Embedding provider (OpenAI); single model per deployment
    openai_api_key: str = ""
    # Anthropic/Google ARE wired into the ModelRouter multi-provider failover
    # (see MODEL_TIERS + providers/). These keys enable those providers.
    anthropic_api_key: str = ""
    google_api_key: str = ""
    default_embedding_model: str = "text-embedding-3-small"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = 1536
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 8
    blob_read_write_token: str = ""
    ml_default_classifier: str = "random_forest"
    ml_anomaly_contamination: float = 0.1
    ml_forecast_horizon: int = 7
    redis_url: str = ""
    # Circuit breaker state backend: auto (Redis when REDIS_URL set, else memory),
    # memory (always per-process), redis (require Redis — falls back on error).
    circuit_breaker_backend: str = "auto"

    # IN-00: 32-byte connector secret key as 64-char hex (node backend/scripts/generate-connector-encryption-key.mjs)
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
    # Public API base for OAuth callbacks (defaults to same host as app in dev)
    api_public_url: str = ""

    # HubSpot OAuth (STA-13 / STA-14) — production app
    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    # Optional separate HubSpot app for staging/sandbox connectors
    hubspot_sandbox_client_id: str = ""
    hubspot_sandbox_client_secret: str = ""
    # HubSpot inbound webhooks (STA-16) — platform operator sets once per app
    hubspot_app_id: str = ""
    hubspot_developer_api_key: str = ""
    # Salesforce OAuth (STA-30)
    salesforce_client_id: str = ""
    salesforce_client_secret: str = ""
    salesforce_sandbox_client_id: str = ""
    salesforce_sandbox_client_secret: str = ""
    # QuickBooks Online OAuth (STA-33)
    quickbooks_client_id: str = ""
    quickbooks_client_secret: str = ""
    quickbooks_sandbox_client_id: str = ""
    quickbooks_sandbox_client_secret: str = ""
    # NetSuite OAuth (STA-56)
    netsuite_client_id: str = ""
    netsuite_client_secret: str = ""
    netsuite_sandbox_client_id: str = ""
    netsuite_sandbox_client_secret: str = ""
    # Jira Cloud OAuth (STA-36)
    jira_client_id: str = ""
    jira_client_secret: str = ""
    # Generic OAuth — Xero (PKCE)
    xero_client_id: str = ""
    xero_client_secret: str = ""
    # Generic OAuth — Mailchimp
    mailchimp_client_id: str = ""
    mailchimp_client_secret: str = ""
    # Generic OAuth — Airtable (PKCE)
    airtable_client_id: str = ""
    airtable_client_secret: str = ""
    # Generic OAuth — Asana
    asana_client_id: str = ""
    asana_client_secret: str = ""
    # Generic OAuth — Freshdesk (subdomain per connector at connect)
    freshdesk_client_id: str = ""
    freshdesk_client_secret: str = ""
    # Generic OAuth — Microsoft 365 / Graph (multitenant via /common/)
    microsoft365_client_id: str = ""
    microsoft365_client_secret: str = ""
    # PagerDuty OAuth (STA-37)
    pagerduty_client_id: str = ""
    pagerduty_client_secret: str = ""
    # Notion OAuth (STA-43)
    notion_client_id: str = ""
    notion_client_secret: str = ""
    # Marketo REST client credentials (STA-64); munchkin_id stored per connector
    marketo_client_id: str = ""
    marketo_client_secret: str = ""
    # Workday OAuth (STA-59)
    workday_client_id: str = ""
    workday_client_secret: str = ""
    workday_sandbox_client_id: str = ""
    workday_sandbox_client_secret: str = ""
    # Google OAuth — shared "Gravitre OAuth" app (Calendar, GA4, future Gmail/Drive)
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    # Google Analytics OAuth (STA-40); falls back from GOOGLE_OAUTH_* when unset
    google_analytics_client_id: str = ""
    google_analytics_client_secret: str = ""
    # Stripe usage-based (metered) billing: meter event name configured on the
    # Stripe Billing Meter that the metered price is attached to.
    stripe_meter_event_name: str = "ai_credits_used"
    # Per-plan metered (usage-based) price IDs tied to the AI-credits meter. When
    # set, they are added as an extra subscription/checkout line item so usage is
    # actually billed. Empty = flat-rate only (no usage billing).
    stripe_metered_price_id_node: str = ""
    stripe_metered_price_id_control: str = ""
    stripe_metered_price_id_command: str = ""
    # Marketplace v2 (STA-96): platform fee on partner connector usage (basis points, 2000 = 20%)
    marketplace_platform_fee_bps: int = 2000
    # Private connector runtime (STA-98): signed org bundles executed in subprocess sandbox
    private_connector_runtime_enabled: bool = True
    private_connector_sandbox_timeout_sec: int = 10
    # Shared secret for internal cron endpoints (e.g. usage sync). Not a user JWT.
    internal_api_secret: str = ""
    # In-process knowledge sync scheduler (STA-45). 0 = disabled.
    knowledge_sync_interval_seconds: int = 3600
    # In-process workflow schedule dispatcher (STA-47). 0 = disabled.
    workflow_schedule_interval_seconds: int = 60
    # In-process usage-sync scheduler interval (seconds). 0 disables it (e.g. if
    # you use the GitHub Action / a Railway cron service instead).
    usage_sync_interval_seconds: int = 3600
    # In-process async agent-job worker (durable operator/agent execution).
    agent_job_worker_enabled: bool = True
    agent_job_poll_seconds: int = 5
    # Durable workflow run queue consumer (STA-94). Requires REDIS_URL.
    workflow_queue_enabled: bool = True
    workflow_queue_poll_seconds: int = 5
    # White-label custom domain CNAME target (STA-84)
    enterprise_custom_domain_cname_target: str = "cname.gravitre.app"
    # Deployment region for RLS enforcement (us|eu). Set per regional Supabase/API deployment.
    deployment_data_region: str = "us"

    # Phase 6: kill switches (default off)
    disable_execute: bool = False
    disable_connectors: bool = False
    disable_ingestion: bool = False

    # AI governance / safety (chokepoint-enforced in ModelRouter)
    # Global LLM killswitch — when true, all model_router completions are refused.
    disable_ai: bool = False
    # Per-org sliding-window rate limit for LLM calls; 0 disables the limiter.
    ai_rate_limit_per_min: int = 0
    # Hard spend gate (default ON): block LLM calls once an org's period
    # ai_credits usage reaches ai_credits_included * ai_budget_overage_multiplier.
    # Fail-open on a transient billing-lookup error (availability > strict
    # enforcement on a DB blip); the per-org rate limiter remains the hard cap.
    ai_hard_budget_enabled: bool = True
    ai_budget_overage_multiplier: float = 2.0
    # OpenAI moderation API applied to all inputs before provider calls.
    # Default: True. Set False only for internal/dev deployments where cost
    # reduction outweighs moderation need. Fails open on moderation API
    # unavailability — the request proceeds if moderation cannot be reached.
    ai_moderation_enabled: bool = True
    ai_moderation_model: str = "omni-moderation-latest"
    # Redact PII (email/SSN/card/phone) from user + retrieved content before it
    # is sent to an external AI provider.
    ai_pii_redaction_enabled: bool = True
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_app_id: str = ""
    slack_signing_secret: str = ""

    # Multi-provider failover
    gemini_api_key: str = ""          # Google Gemini (GEMINI_API_KEY)
    voyage_api_key: str = ""          # Voyage AI embeddings fallback (VOYAGE_API_KEY)
    # True only after corpus is re-indexed with Voyage (1024-dim). See docs/voyage-reindex-runbook.md
    voyage_embedding_enabled: bool = False
    # Provider preference for the failover chain: openai | anthropic | gemini | auto
    preferred_ai_provider: str = "openai"
    # When false, only the preferred/OpenAI provider is used (no cross-provider failover).
    ai_failover_enabled: bool = True
    ai_failover_log_level: str = "warning"

    @property
    def gemini_key(self) -> str:
        """Gemini key, preferring GEMINI_API_KEY then GOOGLE_API_KEY."""
        return (self.gemini_api_key or self.google_api_key or "").strip()

    # Phase 7: policy engine defaults (0/empty = disabled)
    policy_max_steps: int = 0
    policy_max_runtime_seconds: int = 0
    policy_allowed_envs: str = ""

    @field_validator("connector_secrets_encryption_key")
    @classmethod
    def _validate_connector_secrets_key_format(cls, value: str) -> str:
        return validate_connector_secrets_encryption_key(value)

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


# ---------------------------------------------------------------------------
# Multi-provider model tiering (typed; consumed by the router/failover layer)
# ---------------------------------------------------------------------------
# complexity tier -> provider -> model id
MODEL_TIERS: dict[str, dict[str, str]] = {
    "low": {
        "openai": "gpt-5.4-mini",
        "anthropic": "claude-haiku-4-5-20251001",
        "gemini": "gemini-2.5-flash",
    },
    "medium": {
        "openai": "gpt-5.5",
        "anthropic": "claude-sonnet-4-6",
        "gemini": "gemini-2.5-pro",
    },
    "high": {
        "openai": "gpt-5.5",
        "anthropic": "claude-sonnet-4-6",
        "gemini": "gemini-2.5-pro",
    },
}

# task-type string (TaskType value) -> complexity tier
TASK_COMPLEXITY: dict[str, str] = {
    "classification": "low",
    "intent_detection": "low",
    "summarization": "low",
    "content_generation": "medium",
    "rag_answering": "medium",
    "optimization": "medium",
    "workflow_planning": "high",
    "decision_reasoning": "high",
    "agent_debate": "high",
}


class SettingsNotConfiguredError(RuntimeError):
    def __init__(self, missing_fields: list[str]):
        self.missing_fields = missing_fields
        super().__init__(f"Missing required settings: {', '.join(missing_fields)}")


def _extract_missing_fields(exc: ValidationError) -> list[str]:
    missing: list[str] = []
    for err in exc.errors():
        if err.get("type") != "missing":
            continue
        loc = err.get("loc") or []
        if not loc:
            continue
        field = str(loc[0])
        if field not in missing:
            missing.append(field)
    return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_fields = _extract_missing_fields(exc)
        raise SettingsNotConfiguredError(missing_fields=missing_fields) from exc
