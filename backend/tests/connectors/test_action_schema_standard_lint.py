"""CI lint — connector action schema standard (F8 / G.2)."""
from __future__ import annotations

from app.connectors.action_catalog.action_id_aliases import ACTION_ID_ALIASES
from app.connectors.action_catalog.registry import all_catalog_action_specs

_WHEN_WHY = ("use when", "use this", "prefer when", "for when", "when you need")
_PLACEHOLDER = ("todo", "tbd", "placeholder", "fixme")
_HIGH_RISK = frozenset({"apollo", "hubspot", "slack", "github", "clickup", "salesforce"})


def test_all_descriptions_have_when_why_cue():
    specs = list(all_catalog_action_specs())
    missing = [
        s.id
        for s in specs
        if not any(cue in (s.description or "").lower() for cue in _WHEN_WHY)
    ]
    assert not missing, f"missing when/why on {len(missing)} actions e.g. {missing[:10]}"


def test_no_placeholder_or_empty_descriptions():
    specs = list(all_catalog_action_specs())
    bad = []
    for s in specs:
        d = (s.description or "").strip()
        if not d or any(p in d.lower() for p in _PLACEHOLDER):
            bad.append(s.id)
    assert not bad, bad[:20]


def test_writes_are_marked_destructive():
    specs = list(all_catalog_action_specs())
    unmarked = [s.id for s in specs if s.kind == "write" and not s.destructive]
    assert not unmarked, unmarked


def test_high_risk_vendors_expose_mcp_hints():
    specs = [s for s in all_catalog_action_specs() if s.id.split(".", 1)[0] in _HIGH_RISK]
    assert specs
    for s in specs[:5]:
        payload = s.to_dict(vendor=s.id.split(".", 1)[0], implemented=True)
        assert "readOnlyHint" in payload
        assert "destructiveHint" in payload
        assert payload["destructiveHint"] is bool(s.destructive)
        assert payload["readOnlyHint"] == (s.kind == "read" and not s.destructive)


def test_legacy_short_ids_have_canonical_aliases():
    short = [
        s.id
        for s in all_catalog_action_specs()
        if len(s.id.split(".")) < 3
    ]
    # Every remaining short id must be listed for migration tracking.
    missing_alias = [i for i in short if i not in ACTION_ID_ALIASES]
    assert not missing_alias, (
        "Add ACTION_ID_ALIASES entries for short ids: " + ", ".join(missing_alias[:20])
    )
