"""Where each vendor publishes a machine-checkable API contract.

This is the field a future drift scan needs: for an action's api_reference to be
diffable, something authoritative has to diff it against. Every URL below was
fetched live on the recorded date and returned a real 200/206 — none are
asserted from memory, because a contract URL that quietly 404s would make a
drift scan silently pass.

Vendors absent from this table have no verified machine-readable contract. That
is recorded as absence, not guessed at.
"""
from __future__ import annotations

from dataclasses import dataclass

PROBED = "2026-08-29"


@dataclass(frozen=True)
class VendorContract:
    contract_type: str  # openapi | discovery | graphql | reference_docs
    url: str
    verified_at: str
    note: str = ""


VENDOR_CONTRACTS: dict[str, VendorContract] = {
    "stripe": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
        PROBED,
    ),
    "slack": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/slackapi/slack-api-specs/master/web-api/slack_web_openapi_v2.json",
        PROBED,
    ),
    "github": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json",
        PROBED,
    ),
    "twilio": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/twilio/twilio-oai/main/spec/json/twilio_api_v2010.json",
        PROBED,
        note="Core 2010-04-01 API only; Studio/Verify have separate specs.",
    ),
    "asana": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/Asana/openapi/master/defs/asana_oas.yaml",
        PROBED,
    ),
    "microsoft365": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/microsoftgraph/msgraph-metadata/master/openapi/v1.0/openapi.yaml",
        PROBED,
        note="Microsoft Graph v1.0. Covers teams/sharepoint/onedrive/users actions.",
    ),
    "pagerduty": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/PagerDuty/api-schema/main/reference/REST/openapiv3.json",
        PROBED,
    ),
    "jira": VendorContract(
        "openapi",
        "https://developer.atlassian.com/cloud/jira/platform/swagger-v3.v3.json",
        PROBED,
    ),
    "confluence": VendorContract(
        "openapi",
        "https://developer.atlassian.com/cloud/confluence/swagger.v3.json",
        PROBED,
    ),
    "google_drive": VendorContract(
        "discovery",
        "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest",
        PROBED,
    ),
    "gmail": VendorContract(
        "discovery",
        "https://www.googleapis.com/discovery/v1/apis/gmail/v1/rest",
        PROBED,
    ),
    "google_calendar": VendorContract(
        "discovery",
        "https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest",
        PROBED,
    ),
    "google_sheets": VendorContract(
        "discovery",
        "https://www.googleapis.com/discovery/v1/apis/sheets/v4/rest",
        PROBED,
    ),
    "zendesk": VendorContract(
        "openapi",
        "https://developer.zendesk.com/zendesk/oas.yaml",
        PROBED,
    ),
    "hubspot": VendorContract(
        "openapi",
        "https://api.hubspot.com/public/api/spec/v1/specs",
        PROBED,
        note="Index of per-API OpenAPI specs; the CRM v3 objects spec is the one "
        "the crm/v3/objects/* actions map to.",
    ),
    "gitlab": VendorContract(
        "openapi",
        "https://gitlab.com/gitlab-org/gitlab/-/raw/master/doc/api/openapi/openapi_v2.yaml",
        PROBED,
    ),
    "brevo": VendorContract(
        "openapi",
        "https://api.brevo.com/v3/swagger_definition_v3.yml",
        PROBED,
    ),
    "paypal": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/paypal/paypal-rest-api-specifications/main/openapi/checkout_orders_v2.json",
        PROBED,
        note="Checkout Orders v2 only; payments/payouts/disputes are separate specs.",
    ),
    "intercom": VendorContract(
        "openapi",
        "https://raw.githubusercontent.com/intercom/Intercom-OpenAPI/main/descriptions/2.11/api.intercom.io.yaml",
        PROBED,
    ),
    "monday": VendorContract(
        "graphql",
        "https://api.monday.com/v2/get_schema",
        PROBED,
    ),
    "notion": VendorContract(
        "reference_docs",
        "https://developers.notion.com/reference/intro",
        PROBED,
        note="Human documentation only — Notion publishes no OpenAPI spec, so "
        "these actions cannot be machine-diffed.",
    ),
    "apollo": VendorContract(
        "reference_docs",
        "https://docs.apollo.io/reference",
        PROBED,
        note="Human documentation only — no published OpenAPI spec.",
    ),
}

# Actions are namespaced per Google product but share one discovery family.
_VENDOR_ALIASES = {
    "google_docs": "google_drive",
    "drive": "google_drive",
    "sheets": "google_sheets",
    "calendar": "google_calendar",
    "microsoft365_teams": "microsoft365",
    "outlook": "microsoft365",
}


def vendor_contract(vendor: str) -> VendorContract | None:
    key = _VENDOR_ALIASES.get(vendor, vendor)
    return VENDOR_CONTRACTS.get(key)
