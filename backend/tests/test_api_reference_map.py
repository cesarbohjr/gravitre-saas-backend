"""Keep the action→endpoint map complete, honest, and in sync with the catalog.

The map exists so a future vendor-contract drift scan has something real to diff
against. Three ways it could quietly stop being useful, each covered here:

  * an action is added to the catalog and never mapped (drift scan skips it)
  * an endpoint is served without its provenance (a name-inferred route gets
    treated as if it had been read out of vendor-confirmed code)
  * a "no vendor endpoint" action gets a plausible-looking URL instead of the
    honest reason it has none
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from app.connectors.action_catalog.api_reference_map import (
    SOURCE_VERIFIED_PROVENANCE,
    api_reference_entry,
)
from app.connectors.action_catalog.registry import get_vendor_catalog

DATA = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "connectors"
    / "action_catalog"
    / "data"
    / "api_reference_map.json"
)

NO_ENDPOINT_KINDS = {"local", "smtp", "browser_agent", "unregistered"}
REST_REFERENCE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) \S")


_CATALOG_SNAPSHOT = """
import json
from app.connectors.action_catalog.registry import get_vendor_catalog

keys = []
for vendor, spec in get_vendor_catalog().items():
    for action in spec.all_actions():
        tool = action.id
        if not tool.startswith(vendor + "."):
            tool = vendor + "." + tool
        keys.append(tool)
print(json.dumps(sorted(set(keys))))
"""


@lru_cache(maxsize=1)
def _catalog_tool_keys() -> tuple[str, ...]:
    """The shipped catalog, read in a clean process.

    Other tests register fixture vendors (``mcp_partner`` and friends) into the
    shared registry, so reading it in-process makes coverage depend on which
    tests ran first. A subprocess sees only what actually ships.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _CATALOG_SNAPSHOT],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    return tuple(json.loads(proc.stdout.strip().splitlines()[-1]))


@pytest.fixture(scope="module")
def payload() -> dict:
    assert DATA.exists(), "run scripts/build_api_reference_map.py"
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_every_catalog_action_is_mapped(payload: dict) -> None:
    mapped = set(payload["actions"])
    missing = sorted(set(_catalog_tool_keys()) - mapped)
    assert not missing, f"{len(missing)} catalog actions have no api_reference: {missing[:20]}"


def test_map_has_no_entries_for_actions_that_left_the_catalog(payload: dict) -> None:
    stale = sorted(set(payload["actions"]) - set(_catalog_tool_keys()))
    assert not stale, f"map references actions no longer in the catalog: {stale[:20]}"


def test_every_entry_carries_provenance(payload: dict) -> None:
    missing = [a for a, e in payload["actions"].items() if not e.get("provenance")]
    assert not missing, f"entries served without provenance: {missing[:20]}"


def test_endpoints_that_exist_look_like_endpoints(payload: dict) -> None:
    bad: list[str] = []
    for action, entry in payload["actions"].items():
        ref = entry.get("api_reference")
        if ref is None:
            continue
        if entry.get("style") == "graphql":
            continue
        if not REST_REFERENCE.match(ref):
            bad.append(f"{action}: {ref!r}")
    assert not bad, f"malformed api_reference values: {bad[:20]}"


def test_actions_without_an_endpoint_explain_why(payload: dict) -> None:
    """The honesty requirement: no endpoint is fine, silence is not."""
    unexplained = [
        action
        for action, entry in payload["actions"].items()
        if not entry.get("api_reference") and not entry.get("note")
    ]
    assert not unexplained, (
        "actions with no endpoint and no stated reason: " f"{unexplained[:20]}"
    )


def test_name_inferred_routes_are_not_labelled_source_verified(payload: dict) -> None:
    """name_inferred is what we send, but nothing checked it against the vendor.

    If this ever slipped into the source-verified set, a drift scan would report
    agreement it never established.
    """
    assert "name_inferred" not in SOURCE_VERIFIED_PROVENANCE
    inferred = [
        a for a, e in payload["actions"].items() if e.get("provenance") == "name_inferred"
    ]
    assert inferred, "expected the generic catalog_http executor to still be in use"
    for action in inferred:
        assert not api_reference_entry(action).get("vendor_validated", False)


def test_source_verified_entries_cite_a_file_and_line(payload: dict) -> None:
    missing: list[str] = []
    for action, entry in payload["actions"].items():
        if entry.get("provenance") not in SOURCE_VERIFIED_PROVENANCE:
            continue
        source = entry.get("source") or ""
        if not source:
            missing.append(action)
    assert not missing, f"source-verified entries with no citation: {missing[:20]}"


def test_catalog_serves_the_mapped_endpoint() -> None:
    """to_dict must actually surface it; the map is useless if nothing reads it."""
    shipped = set(_catalog_tool_keys())
    served = 0
    for vendor, spec in get_vendor_catalog().items():
        for action in spec.all_actions():
            data = action.to_dict(vendor=vendor, implemented=True)
            if data["tool"] not in shipped:
                continue  # fixture vendor registered by another test
            entry = api_reference_entry(data["tool"])
            assert entry is not None, data["tool"]
            assert data["apiReference"] == entry.get("api_reference")
            assert data["apiReferenceProvenance"] == entry.get("provenance")
            served += 1
    assert served > 700


def test_no_unresolved_source_expressions_leak_into_paths(payload: dict) -> None:
    """A placeholder must name a value, not a fragment of our own source.

    ``/{_graph_user_root(user_id)}/messages`` is the extractor admitting it could
    not resolve the root. Shipping that would give a drift scan a path no vendor
    has ever served. Cases like it belong in the overrides file with the real
    path and a note.
    """
    leaked = [
        f"{action}: {entry['api_reference']}"
        for action, entry in payload["actions"].items()
        if entry.get("api_reference")
        and re.search(r"\{[^}]*\(", entry["api_reference"])
        and entry.get("provenance") != "manual_verified"
    ]
    assert not leaked, f"unresolved source expressions in paths: {leaked}"


def test_vendor_contract_urls_are_absolute(payload: dict) -> None:
    for action, entry in payload["actions"].items():
        url = entry.get("vendor_contract")
        if url:
            assert url.startswith("https://"), f"{action}: {url}"
