"""Second probe round for vendors whose first candidate URL 404'd."""
from __future__ import annotations

import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

CANDIDATES = [
    ("hubspot", "https://api.hubapi.com/api-catalog-public/v1/apis"),
    ("hubspot", "https://api.hubspot.com/public/api/spec/v1/specs"),
    ("gitlab", "https://gitlab.com/gitlab-org/gitlab/-/raw/master/doc/api/openapi/openapi_v2.yaml"),
    ("gitlab", "https://gitlab.com/gitlab-org/gitlab/-/raw/master/doc/api/openapi/openapi.yaml"),
    ("shopify", "https://shopify.dev/admin-graphql-direct-proxy"),
    ("brevo", "https://api.brevo.com/v3/swagger_definition_v3.yml"),
    ("paypal", "https://raw.githubusercontent.com/paypal/paypal-rest-api-specifications/main/openapi/checkout_orders_v2.json"),
    ("clickup", "https://developer.clickup.com/openapi/673cf4cfdca96a0019533cad"),
    ("intercom", "https://raw.githubusercontent.com/intercom/Intercom-OpenAPI/main/descriptions/2.11/api.intercom.io.yaml"),
    ("monday", "https://api.monday.com/v2/get_schema"),
]

with httpx.Client(timeout=30.0, follow_redirects=True) as client:
    for vendor, url in CANDIDATES:
        try:
            r = client.get(url, headers={"Range": "bytes=0-1023"})
            ok = r.status_code in (200, 206)
            print(f"{'OK ' if ok else 'FAIL'} {vendor:10s} {r.status_code}  {r.headers.get('content-type','')[:44]}  {url}")
        except Exception as exc:
            print(f"FAIL {vendor:10s} {type(exc).__name__}  {url}")
