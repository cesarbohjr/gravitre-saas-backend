"""Prove what the three shadowed imports actually do at runtime.

No network: httpx.Client is replaced with a recorder so we capture the request
that WOULD have gone out, including which host and what ends up in the path.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import httpx

import app.connectors.github_api as github_api
import app.services.tool_service as ts

SENT: list[tuple[str, str, dict]] = []


class Recorder:
    def __init__(self, *a, **k):
        self.base_url = k.get("base_url", "")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def request(self, method, url, **kwargs):
        SENT.append((method, f"{self.base_url}{url}", kwargs.get("headers") or {}))
        return httpx.Response(200, json={}, request=httpx.Request(method, "https://x/"))


github_api.httpx = type("m", (), {"Client": Recorder, "HTTPError": httpx.HTTPError})


JIRA_TOKEN = "SENTINEL-JIRA-ACCESS-TOKEN"

print("=" * 78)
print("jira.issues.update  — executor line 2350:  update_issue(cloud_id, token, issue_id, fields)")
print("=" * 78)
try:
    ts.update_issue("jira-cloud-id-abc", JIRA_TOKEN, "PROJ-1", {"summary": "hello"})
except Exception as exc:  # noqa: BLE001
    print(f"raised: {type(exc).__name__}: {exc}")
for method, url, headers in SENT:
    print(f"  OUTBOUND {method} {url}")
    print(f"  auth header carries: {headers.get('Authorization')}")
    print(f"  Jira token present in URL path: {JIRA_TOKEN in url}")
SENT.clear()

print()
print("=" * 78)
print("jira.issues.get     — executor line 2289:  get_issue(cloud_id, token, issue_id, fields=...)")
print("=" * 78)
try:
    ts.get_issue("jira-cloud-id-abc", JIRA_TOKEN, "PROJ-1", fields=["summary"])
except Exception as exc:  # noqa: BLE001
    print(f"raised: {type(exc).__name__}: {exc}")
print(f"  outbound requests: {len(SENT)}")
SENT.clear()

print()
print("=" * 78)
print("quickbooks.invoices.list — executor line 1447: list_invoices(api_base, token, max_results=, start_position=)")
print("=" * 78)
try:
    ts.list_invoices("https://quickbooks.api/v3/company/123", "QB-TOKEN", max_results=25, start_position=1)
except Exception as exc:  # noqa: BLE001
    print(f"raised: {type(exc).__name__}: {exc}")
print(f"  outbound requests: {len(SENT)}")
