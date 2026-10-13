"""OPT-IN: provider deletion semantics against REAL provider SANDBOX accounts.

REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS. Without them every test here is skipped;
that skip is expected in CI and in local runs. Nothing else in the suite is skipped for
lack of credentials: the offline evidence lives in
``tests/services/test_provider_deletion_http_contracts.py``.

What it checks: that each provider still answers the way deletion propagation relies on
(archived / trashed / soft-deleted read as "exclude", only a confirmed deletion reads as
"purge", a live record reads as live), using the production connector functions.

Safety:
* Read-only. Only GET requests (and Notion/HubSpot GET-by-id reads) are made; nothing
  is created, archived, deleted or restored upstream, and no database is touched.
* Refuses, by FAILING rather than skipping, any account that does not identify itself
  as a sandbox (HubSpot ``accountType``; Atlassian sandbox site URL; Zendesk / Notion
  sandbox naming, see each guard), and refuses to run when the process is configured as
  production (APP_ENV / ENVIRONMENT / RAILWAY_ENVIRONMENT_NAME).

Setup (owner): in each sandbox, create one record per state below and export its id.

  GRAVITRE_PROVIDER_SANDBOX_TESTS=1
  # Confluence (sandbox site, e.g. https://<name>-sandbox-<n>.atlassian.net)
  SANDBOX_CONFLUENCE_TOKEN, SANDBOX_CONFLUENCE_CLOUD_ID,
  SANDBOX_CONFLUENCE_LIVE_PAGE_ID, SANDBOX_CONFLUENCE_ARCHIVED_PAGE_ID,
  SANDBOX_CONFLUENCE_TRASHED_PAGE_ID, SANDBOX_CONFLUENCE_PURGED_PAGE_ID
  # HubSpot (sandbox or developer test account)
  SANDBOX_HUBSPOT_TOKEN, SANDBOX_HUBSPOT_LIVE_NOTE_ID,
  SANDBOX_HUBSPOT_ARCHIVED_NOTE_ID, SANDBOX_HUBSPOT_DELETED_NOTE_ID
  # Zendesk (sandbox subdomain)
  SANDBOX_ZENDESK_SUBDOMAIN, SANDBOX_ZENDESK_EMAIL, SANDBOX_ZENDESK_API_TOKEN,
  SANDBOX_ZENDESK_LIVE_TICKET_ID, SANDBOX_ZENDESK_SOFT_DELETED_TICKET_ID
  # Notion (a dedicated workspace whose name contains "sandbox")
  SANDBOX_NOTION_TOKEN, SANDBOX_NOTION_LIVE_PAGE_ID,
  SANDBOX_NOTION_TRASHED_PAGE_ID, SANDBOX_NOTION_DELETED_PAGE_ID

Run: ``python -m pytest -q tests/integration/test_provider_deletion_sandbox.py -rs``
Any id left unset skips only the check that needs it.
"""
from __future__ import annotations

import os
import re

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("GRAVITRE_PROVIDER_SANDBOX_TESTS") != "1",
    reason=(
        "REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS: opt-in provider sandbox checks "
        "(set GRAVITRE_PROVIDER_SANDBOX_TESTS=1 and the SANDBOX_* variables)"
    ),
)


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _need(*names: str) -> list[str]:
    values = [_env(n) for n in names]
    missing = [n for n, v in zip(names, values, strict=True) if not v]
    if missing:
        pytest.skip(f"REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS: {', '.join(missing)} not set")
    return values


@pytest.fixture(autouse=True)
def _refuse_production_runtime():
    for var in ("APP_ENV", "ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME"):
        if _env(var).lower() in {"prod", "production"}:
            pytest.fail(f"refusing to run provider sandbox checks with {var}={_env(var)}")


# ------------------------------------------------------------------ Confluence


def _confluence_guard(token: str, cloud_id: str) -> None:
    with httpx.Client(timeout=30) as http:
        resp = http.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    resp.raise_for_status()
    site = next((s for s in resp.json() if isinstance(s, dict) and s.get("id") == cloud_id), None)
    url = str((site or {}).get("url") or "")
    # Atlassian sandboxes live at https://<name>-sandbox-<n>.atlassian.net.
    if not re.search(r"-sandbox(-\d+)?\.atlassian\.net/?$", url):
        pytest.fail(f"refusing: Confluence cloud {cloud_id} is not an Atlassian sandbox site ({url or 'unknown'})")


def test_confluence_sandbox_statuses_map_to_exclude_and_purge():
    from app.connectors.confluence import get_page_status
    from app.services.confluence_sync_service import _page_gone_checker
    from app.services.source_lifecycle import EXCLUDE

    token, cloud_id = _need("SANDBOX_CONFLUENCE_TOKEN", "SANDBOX_CONFLUENCE_CLOUD_ID")
    _confluence_guard(token, cloud_id)
    check = _page_gone_checker(token, cloud_id)
    expected = {
        "SANDBOX_CONFLUENCE_LIVE_PAGE_ID": (("current",), False),
        "SANDBOX_CONFLUENCE_ARCHIVED_PAGE_ID": (("archived",), EXCLUDE),
        "SANDBOX_CONFLUENCE_TRASHED_PAGE_ID": (("trashed",), EXCLUDE),
        "SANDBOX_CONFLUENCE_PURGED_PAGE_ID": ((None, "deleted"), True),
    }
    ran = 0
    for var, (statuses, verdict) in expected.items():
        page_id = _env(var)
        if not page_id:
            continue
        ran += 1
        assert get_page_status(token, cloud_id, page_id) in statuses, var
        assert check(f"confluence:page:{page_id}") == verdict, var
    if not ran:
        pytest.skip("REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS: no SANDBOX_CONFLUENCE_*_PAGE_ID set")


# ------------------------------------------------------------------ HubSpot


def _hubspot_guard(token: str) -> None:
    with httpx.Client(timeout=30) as http:
        resp = http.get("https://api.hubapi.com/account-info/v3/details", headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    account_type = str(resp.json().get("accountType") or "")
    if account_type not in {"SANDBOX", "DEVELOPER_TEST"}:
        pytest.fail(f"refusing: HubSpot account type {account_type or 'unknown'} is not a sandbox/test account")


def test_hubspot_sandbox_archived_is_not_deleted():
    from app.connectors.hubspot import crm_object_state
    from app.services.hubspot_knowledge_sync_service import _record_gone_checker
    from app.services.source_lifecycle import EXCLUDE

    (token,) = _need("SANDBOX_HUBSPOT_TOKEN")
    _hubspot_guard(token)
    check = _record_gone_checker(token)
    expected = {
        "SANDBOX_HUBSPOT_LIVE_NOTE_ID": ("present", False),
        "SANDBOX_HUBSPOT_ARCHIVED_NOTE_ID": ("archived", EXCLUDE),
        "SANDBOX_HUBSPOT_DELETED_NOTE_ID": ("deleted", True),
    }
    ran = 0
    for var, (state, verdict) in expected.items():
        note_id = _env(var)
        if not note_id:
            continue
        ran += 1
        assert crm_object_state(token, "notes", note_id) == state, var
        assert check(f"hubspot:note:{note_id}") == verdict, var
    if not ran:
        pytest.skip("REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS: no SANDBOX_HUBSPOT_*_NOTE_ID set")


# ------------------------------------------------------------------ Zendesk


def _zendesk_guard(subdomain: str) -> None:
    # Zendesk exposes no "is sandbox" flag to an API token; the subdomain must say so.
    if "sandbox" not in subdomain.lower():
        pytest.fail(f"refusing: Zendesk subdomain {subdomain!r} does not identify a sandbox")


def test_zendesk_sandbox_soft_deleted_ticket_is_excluded_not_purged():
    from app.connectors.zendesk import ZendeskAPIError
    from app.services.source_lifecycle import EXCLUDE
    from app.services.zendesk_knowledge_sync_service import (
        _ticket_gone_checker,
        zendesk_request,
    )

    subdomain, email, api_token = _need("SANDBOX_ZENDESK_SUBDOMAIN", "SANDBOX_ZENDESK_EMAIL", "SANDBOX_ZENDESK_API_TOKEN")
    _zendesk_guard(subdomain)
    # No database client: a 404 can only ever read as EXCLUDE here (never purge).
    check = _ticket_gone_checker(subdomain, email, api_token)
    ran = 0
    live = _env("SANDBOX_ZENDESK_LIVE_TICKET_ID")
    if live:
        ran += 1
        assert check(f"zendesk:ticket:{live}") is False
    soft = _env("SANDBOX_ZENDESK_SOFT_DELETED_TICKET_ID")
    if soft:
        ran += 1
        with pytest.raises(ZendeskAPIError) as err:
            zendesk_request(subdomain, email, api_token, "GET", f"/tickets/{soft}.json")
        assert err.value.status_code == 404
        listing = zendesk_request(subdomain, email, api_token, "GET", "/deleted_tickets.json", params={"per_page": 100})
        assert soft in {str(t.get("id")) for t in listing.get("deleted_tickets") or []}
        assert check(f"zendesk:ticket:{soft}") == EXCLUDE
    if not ran:
        pytest.skip("REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS: no SANDBOX_ZENDESK_*_TICKET_ID set")


# ------------------------------------------------------------------ Notion


def _notion_guard(token: str) -> None:
    from app.connectors.notion import api_request

    me = api_request("GET", "/users/me", token)
    workspace = str(((me.get("bot") or {}).get("workspace_name")) or "")
    if "sandbox" not in workspace.lower():
        pytest.fail(f"refusing: Notion workspace {workspace or 'unknown'!r} is not named as a sandbox")


def test_notion_sandbox_trash_is_excluded_and_only_404_purges():
    from app.services.notion_sync_service import _page_gone_checker
    from app.services.source_lifecycle import EXCLUDE

    (token,) = _need("SANDBOX_NOTION_TOKEN")
    _notion_guard(token)
    check = _page_gone_checker(token)
    expected = {
        "SANDBOX_NOTION_LIVE_PAGE_ID": False,
        "SANDBOX_NOTION_TRASHED_PAGE_ID": EXCLUDE,
        "SANDBOX_NOTION_DELETED_PAGE_ID": True,
    }
    ran = 0
    for var, verdict in expected.items():
        page_id = _env(var)
        if not page_id:
            continue
        ran += 1
        assert check(f"notion:page:{page_id}") == verdict, var
    if not ran:
        pytest.skip("REQUIRES OWNER-PROVIDED SANDBOX CREDENTIALS: no SANDBOX_NOTION_*_PAGE_ID set")
