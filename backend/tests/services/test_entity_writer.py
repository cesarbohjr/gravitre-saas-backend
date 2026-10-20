"""Phase 2E entity writer: provider id first, exact evidence next, proposals, never name-only."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import entity_writer as ew
from app.services.ingestion_interlock import LIFECYCLE_PREREQUISITES
from app.services.source_governance import SETTINGS_KEY

LIFECYCLE_ON = dict(LIFECYCLE_PREREQUISITES)
# Configuration is what these tests vary; runtime lifecycle evidence is present
# (healthy relay in this process). Runtime-state cases: test_lifecycle_runtime.py.
pytestmark = pytest.mark.usefixtures("lifecycle_runtime_ready")

ORG = "11111111-1111-4111-8111-111111111111"
ON = SimpleNamespace(entity_writer_enabled=True, **LIFECYCLE_ON)


class _Q:
    def __init__(self, db: _DB, table: str) -> None:
        self.db, self.t, self.f, self.op, self.row, self.kw = db, table, [], "select", None, {}

    def select(self, *_a):
        return self

    def eq(self, k, v):
        self.f.append(lambda r, k=k, v=v: r.get(k) == v)
        return self

    def in_(self, k, vals):
        self.f.append(lambda r, k=k, vals=list(vals): r.get(k) in vals)
        return self

    def contains(self, k, items):
        def match(r, k=k, items=items):
            have = r.get(k) or []
            return all(any(all(h.get(a) == b for a, b in it.items()) for h in have) for it in items)

        self.f.append(match)
        return self

    def limit(self, _n):
        return self

    def upsert(self, row, on_conflict="", ignore_duplicates=False):
        self.op, self.row, self.kw = "upsert", dict(row), {"keys": on_conflict.split(","), "ignore": ignore_duplicates}
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.t, [])
        if self.op == "upsert":
            keys = self.kw["keys"]
            hit = next((r for r in rows if all(r.get(k) == self.row.get(k) for k in keys)), None)
            if hit is not None:
                if not self.kw["ignore"]:
                    hit.update(self.row)
                return SimpleNamespace(data=[hit] if not self.kw["ignore"] else [])
            new = {"id": str(uuid.uuid4()), **self.row}
            rows.append(new)
            return SimpleNamespace(data=[new])
        return SimpleNamespace(data=[r for r in rows if all(f(r) for f in self.f)])


class _DB:
    def __init__(self, *, opted_in: bool = True, connectors: list[str] | None = None) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "organizations": [
                {
                    "id": ORG,
                    "settings": {
                        SETTINGS_KEY: {"customerContext": {"enabled": opted_in, "connectors": connectors or []}}
                    },
                }
            ]
        }

    def table(self, name):
        return _Q(self, name)

    def entities(self):
        return self.tables.get("org_business_entities", [])

    def bindings(self):
        return self.tables.get("org_business_entity_bindings", [])


@pytest.fixture(autouse=True)
def _no_alias_store(monkeypatch):
    monkeypatch.setattr("app.services.business_entity_fabric.upsert_resolution", lambda *a, **k: False)


def _company(rid: str, host: str = "acme.com", name: str = "Acme", system: str = "hubspot") -> ew.ProviderRecord:
    return ew.ProviderRecord(system=system, resource_type="company", resource_id=rid, display_name=name, host=host)


def test_off_by_default_and_without_opt_in():
    db = _DB()
    assert ew.write_provider_records(db, SimpleNamespace(), org_id=ORG, records=[_company("1")]).as_dict()["created"] == 0
    db = _DB(opted_in=False)
    assert ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1")]).created == 0
    db = _DB(connectors=["zendesk"])
    assert ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1")]).created == 0
    assert db.entities() == []


def test_creates_under_deterministic_key_then_recognises_provider_id():
    db = _DB()
    first = ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1", host="https://www.Acme.com/")])
    assert first.created == 1
    assert [e["canonical_key"] for e in db.entities()] == ["company:host:acme.com"]
    again = ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1")])
    assert again.already_bound == 1 and len(db.entities()) == 1


def test_second_system_with_same_host_joins_existing_entity():
    db = _DB()
    ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1")])
    res = ew.write_provider_records(
        db,
        ON,
        org_id=ORG,
        records=[ew.ProviderRecord("salesforce", "account", "sf-7", "Acme Inc", "company", host="acme.com")],
    )
    assert res.joined == 1
    assert len(db.entities()) == 1
    assert sorted(b["system"] for b in db.bindings()) == ["hubspot", "salesforce"]
    assert len({b["entity_id"] for b in db.bindings()}) == 1


def test_two_records_from_one_system_with_one_host_become_a_proposal():
    db = _DB()
    ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1")])
    res = ew.write_provider_records(db, ON, org_id=ORG, records=[_company("2", name="Acme EU")])
    assert res.proposed == 1 and res.joined == 0
    prop = db.tables[ew.PROPOSALS_TABLE][0]
    assert prop["reason"] == "same_system_already_bound" and prop["resource_id"] == "2"
    assert len(db.bindings()) == 1


def test_multiple_candidates_become_a_proposal():
    db = _DB()
    for key in ("company:host:acme.com", "legacy:acme"):
        db.tables.setdefault("org_business_entities", []).append(
            {
                "id": str(uuid.uuid4()),
                "org_id": ORG,
                "canonical_key": key,
                "kind": "company",
                "display_name": "Acme",
                "confidence": 0.9,
                "evidence": [{"kind": "host", "value": "acme.com", "source": "x"}],
            }
        )
    res = ew.write_provider_records(db, ON, org_id=ORG, records=[_company("5", system="salesforce")])
    assert res.proposed == 1
    assert sorted(db.tables[ew.PROPOSALS_TABLE][0]["candidate_keys"]) == ["company:host:acme.com", "legacy:acme"]
    # The same record again does not open a second proposal.
    ew.write_provider_records(db, ON, org_id=ORG, records=[_company("5", system="salesforce")])
    assert len(db.tables[ew.PROPOSALS_TABLE]) == 1


def test_providers_without_revoke_are_never_filed():
    # Zendesk, Intercom, Notion, Microsoft 365 have no provider revoke wired: even when
    # every flag is on and the org opted in, their records do not reach the entity store.
    db = _DB()
    records = [
        ew.ProviderRecord(system, "organization", f"{system}-1", "Acme", "company", host="acme.com")
        for system in ("zendesk", "intercom", "notion", "microsoft365", "quickbooks")
    ]
    res = ew.write_provider_records(db, ON, org_id=ORG, records=records)
    assert (res.created, res.joined, res.proposed) == (0, 0, 0)
    assert db.entities() == [] and db.bindings() == []
    # The same company from HubSpot (revoke wired) is filed.
    assert ew.write_provider_records(db, ON, org_id=ORG, records=[_company("1")]).created == 1


def test_name_only_records_are_never_written():
    db = _DB()
    res = ew.write_provider_records(db, ON, org_id=ORG, records=[_company("9", host="", name="Acme")])
    assert res.skipped_no_evidence == 1 and db.entities() == []


def test_people_join_on_exact_email_only():
    db = _DB()
    alice = ew.ProviderRecord("hubspot", "contact", "c1", "Alice", "person", email="Alice@Acme.com")
    namesake = ew.ProviderRecord("salesforce", "contact", "u1", "Alice", "person", email="alice@other.com")
    same = ew.ProviderRecord("salesforce", "contact", "u2", "A. Smith", "person", email="alice@acme.com")
    res = ew.write_provider_records(db, ON, org_id=ORG, records=[alice, namesake, same])
    assert (res.created, res.joined) == (2, 1)
    keys = sorted(e["canonical_key"] for e in db.entities())
    assert keys == ["person:email:alice@acme.com", "person:email:alice@other.com"]


def test_one_bad_record_does_not_stop_the_batch(monkeypatch):
    db = _DB()
    real = ew._write_one

    def flaky(client, org_id, record, result):
        if record.resource_id == "bad":
            raise RuntimeError("boom")
        return real(client, org_id, record, result)

    monkeypatch.setattr(ew, "_write_one", flaky)
    res = ew.write_provider_records(
        db, ON, org_id=ORG, records=[_company("bad"), _company("ok", host="globex.com", name="Globex")]
    )
    assert res.failed == 1 and res.created == 1


def test_hubspot_company_records_mapping():
    recs = ew.hubspot_company_records(
        {"results": [{"id": "11", "properties": {"name": "Acme", "domain": "acme.com"}}, {"properties": {}}]}
    )
    assert recs == [ew.ProviderRecord("hubspot", "company", "11", "Acme", "company", host="acme.com")]


def test_hubspot_sync_feed_off_by_default():
    from app.services.hubspot_knowledge_sync_service import _write_company_entities

    assert _write_company_entities(object(), SimpleNamespace(), org_id=ORG, token="t") == {"skipped": "disabled"}
