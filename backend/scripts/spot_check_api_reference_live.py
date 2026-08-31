"""Phase 2: call real actions against real vendors and watch where they land.

The api_reference map is a claim about what URL each action sends. This checks
the claim the only way that settles it — by invoking the action through the
normal invoke_tool path against a live connector and reading the request off the
wire, then matching the observed method+path against what the map recorded.

Requests are NOT stubbed. httpx's transport is wrapped so every outbound request
is recorded and then forwarded to the real vendor. A row only passes if the real
vendor was really contacted at the recorded endpoint.

Read-only actions only: this proves routing, and there is no reason to create
vendor records to do it.

Matching rules
  * the observed URL's path must match the recorded path after {placeholders}
    are turned into a single path segment wildcard
  * a recorded query discriminator (?type=...) must be present in the observed
    query, since for those vendors the query is what selects the endpoint
  * the observed base URL is reported but not required to match, because base
    URLs are per-tenant for several of these vendors (Jira cloud id, Workday
    tenant, HubSpot regions)
  * requests issued by invoke_tool's connector-availability pre-flight are
    excluded by call origin, not by host — see PREFLIGHT_MODULES

Run: python scripts/spot_check_api_reference_live.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

for _p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if not _p.is_file():
        continue
    for _enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            for _k, _v in (dotenv_values(_p, encoding=_enc) or {}).items():
                if _v:
                    os.environ.setdefault(_k, _v)
            break
        except UnicodeDecodeError:
            continue

import logging  # noqa: E402

import httpx  # noqa: E402

logging.disable(logging.WARNING)

from app.config import get_settings  # noqa: E402
from app.connectors.action_catalog.api_reference_map import api_reference_entry  # noqa: E402
from app.services.tool_service import invoke_tool  # noqa: E402
from app.services.tool_types import ToolContext  # noqa: E402
from supabase import create_client  # noqa: E402

MAIN_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
SMOKE_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
VENDOR_PACING_SEC = 6.0

# (action, org_id, params). Params are minimal and read-only. Ids that must be
# real are resolved at runtime by an earlier row in the same vendor.
SAMPLE: list[tuple[str, str, dict[str, Any]]] = [
    ("hubspot.contacts.list", MAIN_ORG, {"limit": 1}),
    (
        "hubspot.contacts.search",
        MAIN_ORG,
        {
            "limit": 1,
            "filter_groups": [
                {
                    "filters": [
                        {"propertyName": "email", "operator": "HAS_PROPERTY"}
                    ]
                }
            ],
        },
    ),
    ("hubspot.deals.list", MAIN_ORG, {"limit": 1}),
    ("hubspot.owners.list", MAIN_ORG, {"limit": 1}),
    ("hubspot.pipelines.list", MAIN_ORG, {}),
    ("hubspot.contacts.get", MAIN_ORG, {"contact_id": "@hubspot_contact_id"}),
    ("hubspot.deals.get", MAIN_ORG, {"deal_id": "@hubspot_deal_id"}),
    ("apollo.lists.list", MAIN_ORG, {}),
    ("apollo.contacts.search", MAIN_ORG, {"query": "test", "limit": 1}),
    ("apollo.organizations.search", MAIN_ORG, {"query": "acme", "limit": 1}),
    ("apollo.people.search", MAIN_ORG, {"query": "engineer", "limit": 1}),
    ("gmail.labels.list", MAIN_ORG, {}),
    ("gmail.messages.list", MAIN_ORG, {"limit": 1}),
    ("google_ads.accounts.list", MAIN_ORG, {}),
    ("google_ads.campaigns.list", MAIN_ORG, {"limit": 1}),
    ("google_analytics.properties.list", MAIN_ORG, {}),
    ("google_search_console.sites.list", MAIN_ORG, {}),
    ("microsoft365.teams.list", MAIN_ORG, {}),
    ("microsoft365.sharepoint.sites.list", MAIN_ORG, {}),
    ("microsoft365.mail.messages.list", MAIN_ORG, {"limit": 1}),
    ("pipedrive.deals.list", MAIN_ORG, {"limit": 1}),
    ("pipedrive.pipelines.list", MAIN_ORG, {}),
    ("pipedrive.organizations.list", MAIN_ORG, {"limit": 1}),
    ("pipedrive.deals.get", MAIN_ORG, {"deal_id": "@pipedrive_deal_id"}),
]

# Filled from an earlier row's response so id-bearing endpoints get a real id.
RESOLVED: dict[str, str] = {}
ID_SOURCES = {
    "hubspot.contacts.list": "hubspot_contact_id",
    "hubspot.deals.list": "hubspot_deal_id",
    "pipedrive.deals.list": "pipedrive_deal_id",
}


def first_id(data: Any, depth: int = 0) -> str | None:
    """First 'id' found in a normalized result, wherever the vendor put it."""
    if depth > 4:
        return None
    if isinstance(data, dict):
        value = data.get("id")
        if isinstance(value, (str, int)) and str(value):
            return str(value)
        for nested in data.values():
            found = first_id(nested, depth + 1)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = first_id(item, depth + 1)
            if found:
                return found
    return None

OBSERVED: list[dict[str, Any]] = []

# Gravitre's own control plane. Connector lookups and token reads travel the
# same httpx stack as vendor calls, so they must be excluded by host or every
# row would "observe" a Supabase request.
INFRA_HOST_MARKERS = ("supabase.co", "supabase.in", "railway.app", "localhost", "127.0.0.1")


ACTIVE_ROW: dict[str, str] = {"action": "-"}

# invoke_tool evaluates connector availability before dispatching, and that
# evaluation live-probes other vendors' credentials: Apollo's profile endpoint
# plus two Apollo discovery searches, HubSpot token introspection, and so on.
# That traffic is real and outbound, so host and OAuth filters do not remove it.
# It has to be excluded by origin instead, and the reason is not cosmetic:
# Apollo's discovery probe calls POST /mixed_people/api_search, which is exactly
# the endpoint apollo.people.search records. Counting pre-flight traffic would
# let that row "pass" without the action ever having run.
PREFLIGHT_MODULES = (
    "connector_availability_service",
    "connector_snapshot_cache",
    "connection_health",
    "apollo_discovery_capability",
)


def _is_preflight() -> bool:
    for frame in traceback.extract_stack():
        name = Path(frame.filename).stem
        if name in PREFLIGHT_MODULES:
            return True
    return False


def _record(request, response, started: float) -> None:
    OBSERVED.append(
        {
            "method": request.method,
            "url": str(request.url),
            "host": request.url.host,
            "path": request.url.path,
            "query": request.url.query.decode() if request.url.query else "",
            "status": response.status_code,
            "started": started,
            "ms": round((time.monotonic() - started) * 1000),
            # Which row was executing, and on which thread. A request recorded
            # under one action but issued for another is how a neighbouring
            # vendor's traffic could otherwise satisfy a match.
            "row": ACTIVE_ROW["action"],
            "thread": threading.current_thread().name,
            "preflight": _is_preflight(),
        }
    )


_real_sync = httpx.HTTPTransport.handle_request
_real_async = httpx.AsyncHTTPTransport.handle_async_request


def _recording_sync(self, request):  # type: ignore[no-untyped-def]
    started = time.monotonic()
    response = _real_sync(self, request)
    _record(request, response, started)
    return response


async def _recording_async(self, request):  # type: ignore[no-untyped-def]
    started = time.monotonic()
    response = await _real_async(self, request)
    _record(request, response, started)
    return response


# Both are needed: connector modules are split between sync httpx.Client and
# async httpx.AsyncClient, and the first run of this script silently observed
# nothing for every async vendor.
httpx.HTTPTransport.handle_request = _recording_sync  # type: ignore[method-assign]
httpx.AsyncHTTPTransport.handle_async_request = _recording_async  # type: ignore[method-assign]


def path_pattern(path: str) -> re.Pattern[str]:
    """Recorded path -> regex, anchored at the END of the observed path only.

    api_reference records the path relative to the vendor's API base, so Apollo's
    ``GET /labels`` really goes out as ``/api/v1/labels`` and Gmail's
    ``/users/{user_id}/labels`` as ``/gmail/v1/users/me/labels``. Anchoring at
    the start would fail every vendor whose base URL carries a version prefix.
    Each {placeholder} consumes exactly one path segment.
    """
    parts = re.split(r"(\{[^}]+\})", path)
    out: list[str] = []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            out.append(r"[^/]+")
        else:
            out.append(re.escape(part))
    body = "".join(out)
    if body.startswith(re.escape("/")):
        body = body[len(re.escape("/")) :]
    return re.compile(r"(?:^|/)" + body + "$")


def split_reference(reference: str) -> tuple[str, str, str]:
    method, _, rest = reference.partition(" ")
    path, _, query = rest.partition("?")
    return method.strip(), path.strip(), query.strip()


def match(reference: str, calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    method, path, query = split_reference(reference)
    pattern = path_pattern(path)
    for call in calls:
        if call["method"].upper() != method.upper():
            continue
        if not pattern.search(call["path"]):
            continue
        if query and query not in (call["query"] or ""):
            continue
        return call
    return None


# --negative-control substitutes a deliberately wrong endpoint for these actions.
# Without it, "everything matched" could equally mean the matcher never says no.
# Each wrong value is plausible — a neighbouring object, a wrong verb, a wrong
# version — because a matcher that only rejects nonsense is not much of a check.
NEGATIVE_CONTROL: dict[str, str] = {
    "hubspot.contacts.list": "GET /crm/v3/objects/companies",
    "hubspot.contacts.search": "GET /crm/v3/objects/contacts/search",
    "apollo.lists.list": "GET /lists",
    "gmail.labels.list": "GET /users/{user_id}/drafts",
    "google_ads.campaigns.list": "POST /v24/customers/{cid}/googleAds:search",
    "pipedrive.deals.list": "GET /deals/{deal_id}",
}


def main() -> int:
    negative = "--negative-control" in sys.argv
    # --only a,b,c narrows the run to named actions. Used when re-checking a
    # specific failure without paying for the whole sample again.
    only: set[str] = set()
    for arg in sys.argv[1:]:
        if arg.startswith("--only="):
            only = {a.strip() for a in arg.split("=", 1)[1].split(",") if a.strip()}
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    rows: list[dict[str, Any]] = []
    last_vendor: str | None = None
    for action, org_id, raw_params in SAMPLE:
        if only and action not in only:
            continue
        entry = api_reference_entry(action)
        if entry is None or not entry.get("api_reference"):
            rows.append({"action": action, "result": "NO_REFERENCE"})
            continue
        reference = entry["api_reference"]
        if negative:
            if action not in NEGATIVE_CONTROL:
                continue
            reference = NEGATIVE_CONTROL[action]

        params: dict[str, Any] = {}
        unresolved: list[str] = []
        for key, value in raw_params.items():
            if isinstance(value, str) and value.startswith("@"):
                resolved = RESOLVED.get(value[1:])
                if resolved is None:
                    unresolved.append(value[1:])
                    continue
                params[key] = resolved
            else:
                params[key] = value
        if unresolved:
            # Sending the literal "@placeholder" would produce a real request to
            # a nonsense id and a misleading result. Skip and say why.
            rows.append(
                {
                    "action": action,
                    "recorded_api_reference": reference,
                    "result": "SKIPPED_NO_ID",
                    "detail": f"no live id available for {unresolved}",
                }
            )
            print(f"SKIP     {action:42s} no live id for {unresolved}")
            continue

        # Per-tool rate limits are real and will refuse a call before it reaches
        # the vendor, which reads as "no request observed". Space out repeated
        # calls to the same vendor so the limiter is not what we are measuring.
        vendor = action.split(".", 1)[0]
        if vendor == last_vendor:
            time.sleep(VENDOR_PACING_SEC)
        last_vendor = vendor

        OBSERVED.clear()
        ACTIVE_ROW["action"] = action
        invoke_started = time.monotonic()
        ctx = ToolContext(
            settings=settings,
            client=client,
            org_id=org_id,
            actor_id="api-reference-spot-check",
            environment_name="production",
        )
        def attempt() -> tuple[Any, bool, str | None]:
            try:
                res = invoke_tool(ctx, action, params)
                ok = bool(getattr(res, "success", False))
                err = None
                if not ok:
                    err = " ".join(
                        str(part)
                        for part in (
                            getattr(res, "error_code", None),
                            getattr(res, "error_message", None),
                        )
                        if part
                    ) or "action returned success=False with no error detail"
                return res, ok, err
            except Exception as exc:  # noqa: BLE001
                return None, False, f"{type(exc).__name__}: {exc}"

        result, success, error = attempt()

        # WinError 10035 / ConnectionTerminated: the local socket layer gave up
        # before the request left the machine, so nothing is observed and the row
        # would read as "never reached its endpoint". That is a property of this
        # runner, not of the endpoint, so retry once and say that it was retried.
        retried = False
        if error and any(
            marker in error for marker in ("10035", "ConnectionTerminated", "ConnectError")
        ):
            time.sleep(3.0)
            OBSERVED.clear()
            invoke_started = time.monotonic()
            retried = True
            result, success, error = attempt()

        # Background connector health checks run on their own loop and land in
        # the same recorder, so restrict to requests that began after this
        # invocation did. Without this a neighbouring vendor's traffic could
        # satisfy a match it had nothing to do with.
        vendor_calls = [
            c
            for c in OBSERVED
            if c["started"] >= invoke_started
            and not c["preflight"]
            and not any(m in (c["host"] or "") for m in INFRA_HOST_MARKERS)
            and "oauth" not in c["url"].lower()
            and not c["path"].lower().endswith("/token")
        ]
        preflight_calls = [c for c in OBSERVED if c["preflight"]]
        hit = match(reference, vendor_calls)

        if hit:
            outcome = "MATCH"
        elif not vendor_calls:
            outcome = "NO_REQUEST"
        else:
            outcome = "MISMATCH"

        row = {
            "action": action,
            "org_id": org_id,
            "recorded_api_reference": reference,
            "provenance": entry.get("provenance"),
            "result": outcome,
            "action_success": success,
            "error": error,
            "retried_after_local_socket_error": retried,
            "matched_request": (
                {"method": hit["method"], "url": hit["url"], "status": hit["status"]}
                if hit
                else None
            ),
            "all_vendor_requests": [
                {
                    "method": c["method"],
                    "url": c["url"],
                    "status": c["status"],
                    "recorded_under_row": c["row"],
                    "thread": c["thread"],
                }
                for c in vendor_calls
            ],
            "preflight_requests_excluded": [
                {"method": c["method"], "url": c["url"]} for c in preflight_calls
            ],
        }
        rows.append(row)

        flag = {"MATCH": "MATCH   ", "MISMATCH": "MISMATCH", "NO_REQUEST": "NOREQ   "}.get(
            outcome, outcome
        )
        print(f"{flag} {action:42s} {reference}")
        if hit:
            print(f"          -> {hit['method']} {hit['url']}  [{hit['status']}]")
        else:
            for c in vendor_calls[:4]:
                print(
                    f"          ?  {c['method']} {c['url']}  [{c['status']}]"
                    f"  (row={c['row']} thread={c['thread']})"
                )
            if error:
                print(f"          !  {error}")
        if outcome == "MATCH" and not success and error:
            # Routing is proven even when the vendor rejects the call; say so
            # rather than letting a green row imply the action worked.
            print(f"          (endpoint correct; action failed: {error})")

        # Feed real ids forward so id-bearing endpoints run against a record
        # that actually exists, rather than proving routing with a 404.
        if success and action in ID_SOURCES:
            found = first_id(getattr(result, "data", None))
            if found:
                RESOLVED[ID_SOURCES[action]] = found

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["result"]] = counts.get(row["result"], 0) + 1

    out = {
        "started_at": datetime.now(UTC).isoformat(),
        "sample_size": len(rows),
        "vendors": sorted({r["action"].split(".", 1)[0] for r in rows}),
        "counts": counts,
        "rows": rows,
    }
    out["mode"] = "negative_control" if negative else "live"
    if only:
        # A subset run must not overwrite the full-sample artifact; a partial
        # file that looks like the canonical one is how a 24-row proof quietly
        # becomes a 2-row proof.
        out["subset_of_sample"] = sorted(only)
        name = "api-reference-spotcheck-subset.json"
    else:
        name = (
            "api-reference-spotcheck-negative.json"
            if negative
            else "api-reference-spotcheck-live.json"
        )
    dest = REPO / "docs" / "delivery" / name
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print()
    for label, count in sorted(counts.items()):
        print(f"{label:12s} {count}")
    print(f"\nwrote {dest}")

    if negative:
        leaked = [r["action"] for r in rows if r["result"] == "MATCH"]
        if leaked:
            print(f"\nNEGATIVE CONTROL FAILED — wrong endpoints still matched: {leaked}")
            return 1
        print("\nnegative control passed: every deliberately wrong endpoint was rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
