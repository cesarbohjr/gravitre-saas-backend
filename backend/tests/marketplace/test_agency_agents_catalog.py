"""Offline regression contracts for the Agency Agents staging catalog."""
import json
from pathlib import Path

import pytest

from app.marketplace.agency_agents_catalog import (
    load_agency_inventory, preview_marketplace_candidates,
    approved_marketplace_candidates,
)


def test_complete_division_inventory():
    data = load_agency_inventory()
    assert len(data["divisions"]) == 18
    assert len(data["agents"]) == 283
    assert {a["division"] for a in data["agents"]} == set(data["divisions"])
    assert all(a["publication_status"] == "draft_unapproved" for a in data["agents"])


def test_marketplace_previews_are_not_published():
    data = load_agency_inventory()
    previews = preview_marketplace_candidates()
    assert len(previews) == sum(a["proposed_disposition"] == "marketplace_agent" for a in data["agents"])
    assert all(a.config["publication_status"] == "draft_unapproved" for a in previews)
    assert all(a.config["source_revision"] == data["source_commit"] for a in previews)


def test_approval_is_fail_closed():
    with pytest.raises(PermissionError):
        approved_marketplace_candidates()


@pytest.mark.parametrize("mutation", [
    lambda x: x["agents"][0].update(slug=x["agents"][1]["slug"]),
    lambda x: x["agents"][0].update(publication_status="published"),
    lambda x: x["agents"][0].update(source_url="https://evil.example/agent.md"),
    lambda x: x["agents"][0].update(division="not-a-division"),
    lambda x: x.update(source_commit="main"),
])
def test_invalid_catalog_fails_closed(tmp_path: Path, mutation):
    data = load_agency_inventory()
    mutation(data)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_agency_inventory(path)
