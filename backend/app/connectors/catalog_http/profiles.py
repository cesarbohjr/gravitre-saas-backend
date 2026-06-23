"""Vendor HTTP profiles for catalog tool bridge."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AuthKind = Literal["generic_oauth", "google_oauth", "slack_bot", "microsoft365", "zendesk", "github", "api_token", "none"]


@dataclass(frozen=True)
class VendorHttpProfile:
    vendor: str
    connector_type: str
    base_url: str
    auth: AuthKind
    path_prefix: str = ""
    extra_headers: tuple[tuple[str, str], ...] = ()


VENDOR_HTTP_PROFILES: dict[str, VendorHttpProfile] = {
    "asana": VendorHttpProfile("asana", "asana", "https://app.asana.com/api/1.0", "generic_oauth"),
    "airtable": VendorHttpProfile("airtable", "airtable", "https://api.airtable.com/v0", "generic_oauth"),
    "notion": VendorHttpProfile(
        "notion",
        "notion",
        "https://api.notion.com/v1",
        "generic_oauth",
        extra_headers=(("Notion-Version", "2022-06-28"),),
    ),
    "mailchimp": VendorHttpProfile("mailchimp", "mailchimp", "https://{dc}.api.mailchimp.com/3.0", "generic_oauth"),
    "intercom": VendorHttpProfile("intercom", "intercom", "https://api.intercom.io", "generic_oauth"),
    "freshdesk": VendorHttpProfile("freshdesk", "freshdesk", "https://{domain}.freshdesk.com/api/v2", "generic_oauth"),
    "monday": VendorHttpProfile("monday", "monday", "https://api.monday.com/v2", "generic_oauth"),
    "clickup": VendorHttpProfile("clickup", "clickup", "https://api.clickup.com/api/v2", "generic_oauth"),
    "constant_contact": VendorHttpProfile(
        "constant_contact", "constant_contact", "https://api.cc.email/v3", "generic_oauth"
    ),
    "odoo": VendorHttpProfile("odoo", "odoo", "{instance_url}/json/2", "generic_oauth"),
    "gorgias": VendorHttpProfile("gorgias", "gorgias", "https://{domain}.gorgias.com/api", "generic_oauth"),
    "microsoft_teams": VendorHttpProfile(
        "microsoft_teams", "microsoft_teams", "https://graph.microsoft.com/v1.0", "microsoft365"
    ),
    "mixpanel": VendorHttpProfile("mixpanel", "mixpanel", "https://mixpanel.com/api/2.0", "api_token"),
    "hootsuite": VendorHttpProfile("hootsuite", "hootsuite", "https://platform.hootsuite.com/v1", "generic_oauth"),
    "apollo": VendorHttpProfile("apollo", "apollo", "https://api.apollo.io/v1", "api_token"),
    "aws_s3": VendorHttpProfile("aws_s3", "aws_s3", "https://s3.{region}.amazonaws.com", "api_token"),
    "canva": VendorHttpProfile("canva", "canva", "https://api.canva.com/rest/v1", "generic_oauth"),
    "gusto": VendorHttpProfile("gusto", "gusto", "https://api.gusto.com/v1", "generic_oauth"),
    "adp": VendorHttpProfile("adp", "adp", "https://api.adp.com", "generic_oauth"),
    "absorb_lms": VendorHttpProfile("absorb_lms", "absorb_lms", "https://{domain}.myabsorb.com/api/rest/v2", "api_token"),
    "confluence": VendorHttpProfile(
        "confluence", "confluence", "https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/api/v2", "generic_oauth"
    ),
    "segment": VendorHttpProfile("segment", "segment", "https://api.segmentapis.com", "generic_oauth"),
    "stripe": VendorHttpProfile("stripe", "stripe", "https://api.stripe.com/v1", "api_token"),
    "pagerduty": VendorHttpProfile("pagerduty", "pagerduty", "https://api.pagerduty.com", "generic_oauth"),
    "github": VendorHttpProfile("github", "github", "https://api.github.com", "github"),
    "linkedin": VendorHttpProfile("linkedin", "linkedin", "https://api.linkedin.com/v2", "generic_oauth"),
    "clio": VendorHttpProfile("clio", "clio", "https://app.clio.com/api/v4", "generic_oauth"),
    "xero": VendorHttpProfile("xero", "xero", "https://api.xero.com/api.xro/2.0", "generic_oauth"),
    "quickbooks": VendorHttpProfile("quickbooks", "quickbooks", "https://quickbooks.api.intuit.com/v3", "generic_oauth"),
    "netsuite": VendorHttpProfile("netsuite", "netsuite", "{instance_url}/services/rest", "generic_oauth"),
    "workday": VendorHttpProfile("workday", "workday", "{instance_url}", "generic_oauth"),
    "marketo": VendorHttpProfile("marketo", "marketo", "https://{munchkin_id}.mktorest.com/rest", "generic_oauth"),
    "bamboohr": VendorHttpProfile("bamboohr", "bamboohr", "https://api.bamboohr.com/api/gateway.php/{subdomain}/v1", "api_token"),
    "greenhouse": VendorHttpProfile("greenhouse", "greenhouse", "https://harvest.greenhouse.io/v1", "api_token"),
    "motion": VendorHttpProfile("motion", "motion", "https://api.usemotion.com/v1", "generic_oauth"),
    "n8n": VendorHttpProfile("n8n", "n8n", "{instance_url}/api/v1", "api_token"),
    "plaid": VendorHttpProfile("plaid", "plaid", "https://production.plaid.com", "api_token"),
    "snowflake": VendorHttpProfile("snowflake", "snowflake", "https://{account}.snowflakecomputing.com", "api_token"),
    "shopify": VendorHttpProfile("shopify", "shopify", "https://{shop}.myshopify.com/admin/api/2024-01", "generic_oauth"),
    "twilio": VendorHttpProfile("twilio", "twilio", "https://api.twilio.com/2010-04-01", "api_token"),
    "typeform": VendorHttpProfile("typeform", "typeform", "https://api.typeform.com", "generic_oauth"),
    "zapier": VendorHttpProfile("zapier", "zapier", "https://hooks.zapier.com", "none"),
}
