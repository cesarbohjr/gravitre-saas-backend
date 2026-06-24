"""OAuth 2.0 provider registry — authorization-code connectors only.

Excluded: apiKey/IAM/database vendors, Plaid Link, Claude platform AI, Snowflake (dedicated
config module; OAuth gated), partner-gated flows without verified self-serve apps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenRequestStyle(str, Enum):
    FORM = "form"
    JSON = "json"
    BASIC_AUTH = "basic_auth"


@dataclass(frozen=True)
class OAuthProviderSpec:
    vendor: str
    authorize_url: str
    token_url: str
    scopes: str = ""
    token_style: TokenRequestStyle = TokenRequestStyle.FORM
    authorize_extra: dict[str, str] = field(default_factory=dict)
    requires_subdomain: bool = False
    requires_instance_url: bool = False
    requires_pkce: bool = False
    partner_gated: bool = False
    accept_header: str = "application/json"
    token_response_json: bool = True
    notes: str = ""
    # Shorter app-domain callback (ClickUp/PagerDuty UIs reject long /api/connectors/oauth/... paths).
    app_redirect_path: str = ""


def _specs() -> dict[str, OAuthProviderSpec]:
    entries: list[OAuthProviderSpec] = [
        OAuthProviderSpec(
            vendor="zapier",
            authorize_url="https://zapier.com/oauth/authorize",
            token_url="https://zapier.com/oauth/token",
            partner_gated=True,
            notes="Zapier platform partner app",
        ),
        OAuthProviderSpec(
            vendor="mailchimp",
            authorize_url="https://login.mailchimp.com/oauth2/authorize",
            token_url="https://login.mailchimp.com/oauth2/token",
        ),
        OAuthProviderSpec(
            vendor="constant_contact",
            authorize_url="https://authz.constantcontact.com/oauth2/default/v1/authorize",
            token_url="https://authz.constantcontact.com/oauth2/default/v1/token",
            scopes="contact_data campaign_data offline_access",
        ),
        OAuthProviderSpec(
            vendor="hootsuite",
            authorize_url="https://platform.hootsuite.com/oauth2/auth",
            token_url="https://platform.hootsuite.com/oauth2/token",
            partner_gated=True,
            notes="Hootsuite developer app approval required",
        ),
        OAuthProviderSpec(
            vendor="xero",
            authorize_url="https://login.xero.com/identity/connect/authorize",
            token_url="https://identity.xero.com/connect/token",
            scopes="openid profile email accounting.transactions accounting.contacts offline_access",
            requires_pkce=True,
        ),
        OAuthProviderSpec(
            vendor="clio",
            authorize_url="https://app.clio.com/oauth/authorize",
            token_url="https://app.clio.com/oauth/token",
            scopes="contacts_read matters_read",
            notes="Clio Manage API v4 read scopes for intake and conflict workflows",
        ),
        OAuthProviderSpec(
            vendor="airtable",
            authorize_url="https://airtable.com/oauth2/v1/authorize",
            token_url="https://airtable.com/oauth2/v1/token",
            scopes="data.records:read data.records:write schema.bases:read",
            requires_pkce=True,
        ),
        OAuthProviderSpec(
            vendor="asana",
            authorize_url="https://app.asana.com/-/oauth_authorize",
            token_url="https://app.asana.com/-/oauth_token",
            scopes="default",
        ),
        OAuthProviderSpec(
            vendor="clickup",
            authorize_url="https://app.clickup.com/api",
            token_url="https://api.clickup.com/api/v2/oauth/token",
            app_redirect_path="/api/auth/callback/clickup",
            notes="Use short redirect URL in ClickUp app settings",
        ),
        OAuthProviderSpec(
            vendor="freshdesk",
            authorize_url="https://{subdomain}.freshdesk.com/oauth/authorize",
            token_url="https://{subdomain}.freshdesk.com/oauth/token",
            requires_subdomain=True,
        ),
        OAuthProviderSpec(
            vendor="intercom",
            authorize_url="https://app.intercom.com/oauth",
            token_url="https://api.intercom.io/auth/eagle/token",
            token_style=TokenRequestStyle.JSON,
        ),
        OAuthProviderSpec(
            vendor="github",
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scopes="repo read:user",
            accept_header="application/json",
            token_response_json=False,
        ),
        OAuthProviderSpec(
            vendor="monday",
            authorize_url="https://auth.monday.com/oauth2/authorize",
            token_url="https://auth.monday.com/oauth2/token",
            scopes="boards:read boards:write",
        ),
        OAuthProviderSpec(
            vendor="gusto",
            authorize_url="https://api.gusto.com/oauth/authorize",
            token_url="https://api.gusto.com/oauth/token",
            partner_gated=True,
            notes="Gusto partner / developer approval required",
        ),
        OAuthProviderSpec(
            vendor="odoo",
            authorize_url="{instance_url}/web/auth/oauth2/authorize",
            token_url="{instance_url}/web/auth/oauth2/token",
            requires_instance_url=True,
            notes="Self-hosted; API key is common alternative",
        ),
        OAuthProviderSpec(
            vendor="canva",
            authorize_url="https://www.canva.com/api/oauth/authorize",
            token_url="https://api.canva.com/rest/v1/oauth/token",
            requires_pkce=True,
            partner_gated=True,
            notes="PKCE required; Canva Connect partner program",
        ),
        OAuthProviderSpec(
            vendor="microsoft365",
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            scopes="offline_access User.Read Mail.Read Mail.Send Calendars.ReadWrite Files.ReadWrite.All ChannelMessage.Send",
            notes="Microsoft Entra app; tenant-specific consent may apply",
        ),
        OAuthProviderSpec(
            vendor="zendesk",
            authorize_url="https://{subdomain}.zendesk.com/oauth/authorizations/new",
            token_url="https://{subdomain}.zendesk.com/oauth/tokens",
            scopes="read write",
            requires_subdomain=True,
            notes="Tools prefer OAuth token; API token fallback supported",
        ),
    ]
    return {spec.vendor: spec for spec in entries}


OAUTH_PROVIDER_REGISTRY: dict[str, OAuthProviderSpec] = _specs()
GENERIC_OAUTH_VENDORS: frozenset[str] = frozenset(OAUTH_PROVIDER_REGISTRY.keys())
PKCE_OAUTH_VENDORS: frozenset[str] = frozenset(v for v, s in OAUTH_PROVIDER_REGISTRY.items() if s.requires_pkce)
PARTNER_GATED_OAUTH_VENDORS: frozenset[str] = frozenset(
    v for v, s in OAUTH_PROVIDER_REGISTRY.items() if s.partner_gated
)

_VENDOR_ALIASES: dict[str, str] = {
    "constantcontact": "constant_contact",
    "mondaycom": "monday",
    "microsoft_365": "microsoft365",
    "ms365": "microsoft365",
    "githubapp": "github",
}


def normalize_generic_vendor(vendor: str) -> str | None:
    key = vendor.strip().lower().replace(" ", "").replace("-", "").replace("_", "").replace(".", "")
    if key in _VENDOR_ALIASES:
        key = _VENDOR_ALIASES[key]
    if key in OAUTH_PROVIDER_REGISTRY:
        return key
    underscored = vendor.strip().lower().replace(" ", "_").replace("-", "_")
    if underscored in OAUTH_PROVIDER_REGISTRY:
        return underscored
    if underscored in _VENDOR_ALIASES:
        resolved = _VENDOR_ALIASES[underscored]
        if resolved in OAUTH_PROVIDER_REGISTRY:
            return resolved
    return None


def resolve_url_template(url: str, *, subdomain: str = "", instance_url: str = "") -> str:
    base = (instance_url or "").strip().rstrip("/")
    sub = (subdomain or "").strip()
    return (
        url.replace("{subdomain}", sub)
        .replace("{account}", sub)
        .replace("{instance_url}", base)
    )


def provider_context_from_connector_config(config: dict[str, Any]) -> dict[str, str]:
    cfg = config or {}
    subdomain = str(
        cfg.get("subdomain")
        or cfg.get("zendesk_subdomain")
        or cfg.get("snowflake_account")
        or cfg.get("account")
        or ""
    ).strip()
    instance_url = str(cfg.get("instance_url") or cfg.get("instanceUrl") or cfg.get("odoo_url") or "").strip()
    return {"subdomain": subdomain, "instance_url": instance_url}
