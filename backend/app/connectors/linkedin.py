"""LinkedIn prospect enrichment (STA-63).

Uses LinkedIn Marketing API when OAuth token is configured; otherwise returns a
structured stub from caller-supplied fields (see docs/integration/linkedin-sales-nav.md).
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import Settings
from app.connectors.hubspot_oauth import load_oauth_tokens

LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0

LINKEDIN_VERSION_HEADER = "202405"


class LinkedInAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{LINKEDIN_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": LINKEDIN_VERSION_HEADER,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, json=json_body, params=params)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise LinkedInAPIError(
                    f"LinkedIn API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if not response.text:
                return {}
            return response.json()
        except LinkedInAPIError:
            raise
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise LinkedInAPIError(str(exc)) from exc
    raise LinkedInAPIError(str(last_error or "LinkedIn request failed"))


def _normalize_input(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": str(params.get("email") or params.get("emailAddress") or "").strip() or None,
        "first_name": str(params.get("first_name") or params.get("firstName") or "").strip() or None,
        "last_name": str(params.get("last_name") or params.get("lastName") or "").strip() or None,
        "company": str(params.get("company") or params.get("companyName") or "").strip() or None,
        "title": str(params.get("title") or params.get("jobTitle") or "").strip() or None,
        "linkedin_url": str(
            params.get("linkedin_url") or params.get("linkedinUrl") or params.get("profile_url") or ""
        ).strip()
        or None,
    }


def build_stub_enrichment(params: dict[str, Any]) -> dict[str, Any]:
    """Structured enrichment from manual / CRM fields when API is unavailable."""
    fields = _normalize_input(params)
    full_name = " ".join(p for p in (fields["first_name"], fields["last_name"]) if p) or None
    return {
        "source": "manual_stub",
        "enriched": False,
        "prospect": {
            "email": fields["email"],
            "firstName": fields["first_name"],
            "lastName": fields["last_name"],
            "fullName": full_name,
            "company": fields["company"],
            "title": fields["title"],
            "linkedinUrl": fields["linkedin_url"],
        },
        "confidence": 40 if any(fields.values()) else 0,
        "notes": "LinkedIn Marketing API token not configured or enrichment unavailable; using input fields.",
    }


def _marketing_api_enrichment(access_token: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Best-effort Marketing API enrichment (organization + email hash lookup)."""
    fields = _normalize_input(params)
    email = fields["email"]
    if not email:
        return None

    try:
        me = _request("GET", "/me", access_token)
    except LinkedInAPIError:
        return None

    prospect: dict[str, Any] = {
        "email": email,
        "firstName": fields["first_name"],
        "lastName": fields["last_name"],
        "company": fields["company"],
        "title": fields["title"],
        "linkedinUrl": fields["linkedin_url"],
    }
    member_id = me.get("id") if isinstance(me, dict) else None
    if member_id:
        prospect["linkedInMemberId"] = str(member_id)

    org_name = fields["company"]
    if org_name:
        try:
            org_search = _request(
                "GET",
                "/organizationSearch",
                access_token,
                params={"q": "search", "keywords": org_name, "count": 1},
            )
            elements = org_search.get("elements") if isinstance(org_search, dict) else None
            if isinstance(elements, list) and elements:
                org = elements[0] if isinstance(elements[0], dict) else {}
                prospect["companyLinkedInId"] = org.get("id") or org.get("urn")
                prospect["company"] = org.get("localizedName") or org_name
        except LinkedInAPIError:
            pass

    full_name = " ".join(p for p in (prospect.get("firstName"), prospect.get("lastName")) if p) or None
    if full_name:
        prospect["fullName"] = full_name

    return {
        "source": "linkedin_marketing_api",
        "enriched": True,
        "prospect": prospect,
        "confidence": 70 if prospect.get("companyLinkedInId") else 55,
        "notes": "Partial enrichment via LinkedIn Marketing API; full Sales Navigator data requires partner APIs.",
    }


def load_linkedin_access_token(
    client: Any,
    connector_id: str,
    settings: Settings,
) -> str | None:
    if not (settings.connector_secrets_encryption_key or "").strip():
        return None
    tokens = load_oauth_tokens(client, connector_id, settings)
    if not tokens:
        return None
    token = str(tokens.get("access_token") or "").strip()
    return token or None


def enrich_prospect(
    *,
    params: dict[str, Any],
    access_token: str | None = None,
) -> dict[str, Any]:
    """`linkedin.prospect.enrich` — Marketing API when token present, else stub."""
    if access_token:
        try:
            api_result = _marketing_api_enrichment(access_token, params)
            if api_result:
                return api_result
        except LinkedInAPIError:
            pass
    return build_stub_enrichment(params)


def fetch_linkedin_post_engagement(access_token: str, post_id: str) -> float:
    """Best-effort LinkedIn social engagement score for a published post/share URN."""
    share_urn = post_id if post_id.startswith("urn:") else f"urn:li:share:{post_id}"
    encoded = share_urn.replace(":", "%3A").replace("/", "%2F")
    try:
        stats = _request("GET", f"/socialActions/{encoded}/statistics", access_token)
    except LinkedInAPIError:
        return 0.0
    if not isinstance(stats, dict):
        return 0.0
    elements = stats.get("elements")
    if isinstance(elements, list) and elements:
        row = elements[0] if isinstance(elements[0], dict) else {}
        total = 0.0
        for key in ("likeCount", "commentCount", "shareCount", "clickCount", "impressionCount"):
            try:
                total += float(row.get(key) or 0.0)
            except (TypeError, ValueError):
                continue
        return total
    total_share_statistics = stats.get("totalShareStatistics")
    if isinstance(total_share_statistics, dict):
        score = 0.0
        for key in ("likeCount", "commentCount", "shareCount", "clickCount", "impressionCount"):
            try:
                score += float(total_share_statistics.get(key) or 0.0)
            except (TypeError, ValueError):
                continue
        return score
    return 0.0
