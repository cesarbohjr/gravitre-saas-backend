"""Nango-backed long-tail connector registry.

This registry is intentionally separate from Gravitre's native OAuth registry.
Adding a vendor here never changes an existing native connector's auth path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path


@dataclass(frozen=True)
class NangoConnectorSpec:
    vendor: str
    display_name: str
    integration_id: str
    category: str
    description: str
    provider_key: str | None = None
    auth_mode: str = "OAUTH2"
    native_fallback: bool = False

    @property
    def provider(self) -> str:
        return self.integration_id if self.provider_key is None else self.provider_key


_SPECS = [
    NangoConnectorSpec("servicenow", "ServiceNow", "servicenow", "Customer Support", "IT service management and enterprise workflows"),
    NangoConnectorSpec("connectsecure", "ConnectSecure", "connectsecure", "DevOps / Incidents", "Cybersecurity posture and vulnerability management"),
    NangoConnectorSpec("sage_intacct", "Sage Intacct", "sage-intacct", "Payments / Finance", "Cloud financial management and accounting"),
    NangoConnectorSpec("front", "Front", "front", "Customer Support", "Shared inbox and customer operations"),
    NangoConnectorSpec("gong", "Gong", "gong", "Sales / Prospecting", "Revenue intelligence and conversation insights"),
    NangoConnectorSpec("highlevel", "HighLevel", "highlevel", "CRM / Marketing", "CRM, marketing automation, and customer engagement"),
    NangoConnectorSpec("instantly", "Instantly", "instantly", "Sales / Prospecting", "Outbound email and lead engagement"),
    NangoConnectorSpec("smartlead", "Smartlead.ai", "smartlead-ai", "Sales / Prospecting", "Cold email campaigns and reply tracking"),
    NangoConnectorSpec("quickmail", "QuickMail", "quickmail", "Sales / Prospecting", "Cold email sequencing and outreach"),
    NangoConnectorSpec("hunter", "Hunter", "hunter", "Sales / Prospecting", "Business email discovery and verification"),
    NangoConnectorSpec("snov", "Snov.io", "snov", "Sales / Prospecting", "Contact enrichment, verification and outreach"),
    NangoConnectorSpec("emailable", "Emailable", "emailable", "Sales / Prospecting", "Email address verification"),
    NangoConnectorSpec("millionverifier", "MillionVerifier", "millionverifier", "Sales / Prospecting", "Email address verification"),
    NangoConnectorSpec("attio", "Attio", "attio", "CRM / Marketing", "Flexible CRM and relationship intelligence"),
    NangoConnectorSpec("close", "Close", "close", "CRM / Marketing", "Sales CRM and communication"),
    NangoConnectorSpec("ashby", "Ashby", "ashby", "HR / People", "Recruiting and talent operations"),
    NangoConnectorSpec("hibob", "HiBob", "hibob", "HR / People", "HRIS and people operations"),
    NangoConnectorSpec("ukg_pro", "UKG Pro", "ukg-pro", "HR / People", "Enterprise HR, payroll, and workforce management"),
    NangoConnectorSpec("box", "Box", "box", "Storage / Dev / Infra", "Cloud content management and file storage"),
    NangoConnectorSpec("dropbox", "Dropbox", "dropbox", "Storage / Dev / Infra", "Cloud file storage and collaboration"),
    NangoConnectorSpec("zoom", "Zoom", "zoom", "Communication", "Meetings, webinars, and communications"),
    NangoConnectorSpec("discord", "Discord", "discord", "Communication", "Community messaging and collaboration"),
    NangoConnectorSpec("sap_s4hana_cloud", "SAP S/4HANA Cloud", "sap-s4hana-cloud", "Operations / Workflow", "Enterprise ERP and business operations"),
    NangoConnectorSpec("sharepoint_online", "SharePoint Online", "sharepoint-online", "Storage / Dev / Infra", "Microsoft content, sites, and document collaboration"),
    NangoConnectorSpec("freshservice", "Freshservice", "freshservice", "Customer Support", "IT service management and service desk"),
    NangoConnectorSpec("kustomer", "Kustomer", "kustomer", "Customer Support", "Customer service CRM and support operations"),
    NangoConnectorSpec("helpscout", "Help Scout", "help-scout", "Customer Support", "Customer support and shared inbox"),
    NangoConnectorSpec("copper", "Copper", "copper", "CRM / Marketing", "CRM for Google Workspace teams"),
    NangoConnectorSpec("zoho_crm", "Zoho CRM", "zoho-crm", "CRM / Marketing", "CRM and sales automation"),
    NangoConnectorSpec("lever", "Lever", "lever", "HR / People", "Applicant tracking and recruiting"),
    NangoConnectorSpec("deel", "Deel", "deel", "HR / People", "Global payroll, HR, and contractor management"),
    NangoConnectorSpec("rippling", "Rippling", "rippling", "HR / People", "HR, payroll, identity, and device operations"),
    NangoConnectorSpec("personio", "Personio", "personio", "HR / People", "HRIS and recruiting for SMBs"),
    NangoConnectorSpec("ramp", "Ramp", "ramp", "Payments / Finance", "Corporate cards, spend, and expense management"),
    NangoConnectorSpec("brex", "Brex", "brex", "Payments / Finance", "Corporate cards, spend, and cash management"),
    NangoConnectorSpec("chargebee", "Chargebee", "chargebee", "Payments / Finance", "Subscription billing and revenue operations"),
    NangoConnectorSpec("docusign", "DocuSign", "docusign", "Operations / Workflow", "Electronic signatures and agreement workflows"),
    NangoConnectorSpec("dropbox_sign", "Dropbox Sign", "dropbox-sign", "Operations / Workflow", "Electronic signatures and document workflows"),
    NangoConnectorSpec("pax8", "Pax8", "pax8", "Operations / Workflow", "Cloud marketplace and MSP operations"),
    NangoConnectorSpec("autotask", "Autotask PSA", "autotask", "Operations / Workflow", "PSA, ticketing, projects, and MSP operations"),
    NangoConnectorSpec("halo_psa", "HaloPSA", "halopsa", "Operations / Workflow", "PSA and service management for MSPs"),
    NangoConnectorSpec("syncro", "Syncro", "syncro", "Operations / Workflow", "RMM and PSA for MSPs"),
    NangoConnectorSpec("huntress", "Huntress", "huntress", "DevOps / Incidents", "Managed cybersecurity and threat operations"),
    NangoConnectorSpec("sentinelone", "SentinelOne", "sentinelone", "DevOps / Incidents", "Endpoint security and threat detection"),
    NangoConnectorSpec("crowdstrike", "CrowdStrike", "crowdstrike", "DevOps / Incidents", "Endpoint protection and threat intelligence"),
    NangoConnectorSpec("okta", "Okta", "okta", "Storage / Dev / Infra", "Identity and access management"),
    NangoConnectorSpec("jumpcloud", "JumpCloud", "jumpcloud", "Storage / Dev / Infra", "Directory, identity, and device management"),
    NangoConnectorSpec("duo", "Duo", "duo", "Storage / Dev / Infra", "Multi-factor authentication and access security"),
    NangoConnectorSpec("onepassword", "1Password", "1password", "Storage / Dev / Infra", "1Password Events API authorization for audit events"),
    NangoConnectorSpec("microsoft_intune", "Microsoft Intune", "microsoft-intune", "Storage / Dev / Infra", "Endpoint and mobile device management"),
    NangoConnectorSpec("jamf_pro", "Jamf Pro", "jamf-pro", "Storage / Dev / Infra", "Apple device management"),
    NangoConnectorSpec("braintree", "Braintree", "braintree", "Payments / Finance", "Payment processing"),
    NangoConnectorSpec("recurly", "Recurly", "recurly", "Payments / Finance", "Subscription management and recurring billing"),
]


# Provider template names are distinct from our stable integration unique keys.
# Empty mappings deliberately fail closed until Nango supports that provider.
_PROVIDER_OVERRIDES = {
    "hibob": "hibob-service-user", "sap_s4hana_cloud": "sap-odata-basic",
    "helpscout": "helpscout-mailbox", "halo_psa": "halo-psa",
    "duo": "cisco-duo-admin", "onepassword": "1password-events",
    "jamf_pro": "jamf", "syncro": "", "recurly": "",
}
_AUTH_MODES = {
    "ashby": "BASIC",
    "autotask": "API_KEY",
    "cal_com": "API_KEY",
    "chargebee": "BASIC",
    "connectsecure": "BASIC",
    "crowdstrike": "OAUTH2_CC",
    "discourse": "API_KEY",
    "drata": "API_KEY",
    "duo": "BASIC",
    "freshsales": "API_KEY",
    "freshservice": "BASIC",
    "gong": "BASIC",
    "halo_psa": "OAUTH2_CC",
    "hibob": "BASIC",
    "humaans": "API_KEY",
    "huntress": "BASIC",
    "instantly": "API_KEY",
    "smartlead": "API_KEY",
    "quickmail": "API_KEY",
    "hunter": "API_KEY",
    "snov": "API_KEY",
    "emailable": "API_KEY",
    "millionverifier": "API_KEY",
    "jamf_pro": "OAUTH2_CC",
    "jumpcloud": "API_KEY",
    "klaviyo": "API_KEY",
    "kustomer": "API_KEY",
    "lemlist": "BASIC",
    "metabase": "API_KEY",
    "microsoft_intune": "OAUTH2_CC",
    "onepassword": "API_KEY",
    "pax8": "OAUTH2_CC",
    "personio": "OAUTH2_CC",
    "recharge": "API_KEY",
    "rippling": "API_KEY",
    "sage_intacct": "TWO_STEP",
    "sap_s4hana_cloud": "BASIC",
    "sentinelone": "API_KEY",
    "sentry": "API_KEY",
    "talentlms": "API_KEY",
    "toggl": "BASIC",
    "ukg_pro": "BASIC"
}

_SPECS = [replace(s, provider_key=_PROVIDER_OVERRIDES.get(s.vendor), auth_mode=_AUTH_MODES.get(s.vendor, "OAUTH2")) for s in _SPECS]
BUSINESS_CONNECTORS = json.loads(Path(__file__).with_name("managed_business_connectors.json").read_text())
_SPECS.extend(NangoConnectorSpec(**{k: row[k] for k in (
    "vendor", "display_name", "integration_id", "category", "description", "provider_key", "auth_mode"
)}) for row in BUSINESS_CONNECTORS)

NANGO_CONNECTOR_REGISTRY: dict[str, NangoConnectorSpec] = {spec.vendor: spec for spec in _SPECS}
NANGO_CONNECTOR_VENDORS: frozenset[str] = frozenset(NANGO_CONNECTOR_REGISTRY)

# Opt-in replacements for confirmed failed native authorization. Healthy native
# accounts keep their existing path and are never migrated by a health check.
NANGO_FALLBACK_REGISTRY = {
    vendor: NangoConnectorSpec(vendor, display, f"gravitre-{provider}", category,
                              "Optional managed authorization for reconnecting an account",
                              provider_key=provider, native_fallback=True)
    for vendor, display, provider, category in (
        ("slack", "Slack", "slack", "Communication"),
        ("google_ads", "Google Ads", "google-ads", "CRM / Marketing"),
        ("google_analytics", "Google Analytics", "google-analytics", "CRM / Marketing"),
    )
}


def get_nango_connector_spec(vendor: str) -> NangoConnectorSpec | None:
    key = vendor.strip().lower().replace("-", "_").replace(" ", "_")
    return NANGO_CONNECTOR_REGISTRY.get(key) or NANGO_FALLBACK_REGISTRY.get(key)
