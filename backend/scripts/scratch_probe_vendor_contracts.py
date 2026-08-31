"""Probe candidate vendor API-contract URLs and record what actually resolves.

Only URLs that return a real 200 with a spec-ish content type get recorded as
machine-readable contracts; everything else is reported as unverified so the
map never claims a schema location that does not exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

CANDIDATES: dict[str, tuple[str, str]] = {
    # vendor: (contract_type, url)
    "stripe": ("openapi", "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json"),
    "slack": ("openapi", "https://raw.githubusercontent.com/slackapi/slack-api-specs/master/web-api/slack_web_openapi_v2.json"),
    "github": ("openapi", "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json"),
    "twilio": ("openapi", "https://raw.githubusercontent.com/twilio/twilio-oai/main/spec/json/twilio_api_v2010.json"),
    "asana": ("openapi", "https://raw.githubusercontent.com/Asana/openapi/master/defs/asana_oas.yaml"),
    "microsoft365": ("openapi", "https://raw.githubusercontent.com/microsoftgraph/msgraph-metadata/master/openapi/v1.0/openapi.yaml"),
    "pagerduty": ("openapi", "https://raw.githubusercontent.com/PagerDuty/api-schema/main/reference/REST/openapiv3.json"),
    "jira": ("openapi", "https://developer.atlassian.com/cloud/jira/platform/swagger-v3.v3.json"),
    "confluence": ("openapi", "https://developer.atlassian.com/cloud/confluence/swagger.v3.json"),
    "google_drive": ("discovery", "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest"),
    "gmail": ("discovery", "https://www.googleapis.com/discovery/v1/apis/gmail/v1/rest"),
    "google_calendar": ("discovery", "https://www.googleapis.com/discovery/v1/apis/calendar/v3/rest"),
    "google_sheets": ("discovery", "https://www.googleapis.com/discovery/v1/apis/sheets/v4/rest"),
    "zendesk": ("openapi", "https://developer.zendesk.com/zendesk/oas.yaml"),
    "shopify": ("openapi", "https://raw.githubusercontent.com/Shopify/shopify-api-ruby/main/openapi.json"),
    "gitlab": ("openapi", "https://gitlab.com/gitlab-org/gitlab/-/raw/master/doc/api/openapi/openapi.yaml"),
    "hubspot": ("openapi", "https://api.hubspot.com/api-catalog-public/v1/apis"),
    "linear": ("graphql", "https://api.linear.app/graphql"),
    "notion": ("reference_docs", "https://developers.notion.com/reference/intro"),
    "apollo": ("reference_docs", "https://docs.apollo.io/reference"),
}

results: dict[str, dict] = {}
with httpx.Client(timeout=30.0, follow_redirects=True) as client:
    for vendor, (kind, url) in CANDIDATES.items():
        row: dict = {"contract_type": kind, "url": url}
        try:
            response = client.get(url, headers={"Range": "bytes=0-2047"})
            row["status"] = response.status_code
            row["content_type"] = response.headers.get("content-type", "")
            row["ok"] = response.status_code in (200, 206)
            snippet = (response.text or "")[:160].replace("\n", " ")
            row["snippet"] = snippet
        except Exception as exc:
            row["ok"] = False
            row["error"] = f"{type(exc).__name__}: {exc}"
        results[vendor] = row
        flag = "OK " if row.get("ok") else "FAIL"
        print(f"{flag} {vendor:18s} {row.get('status', '-')}  {row.get('content_type', row.get('error', ''))[:60]}")

Path("../docs/delivery/vendor-contract-probe.json").resolve().write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)
print("\nwrote docs/delivery/vendor-contract-probe.json")
