"""No live providers: deterministic acceptance tests of historical pagination and matching."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app.services.intelligence_history_pipeline import Source, ingest_history, match_observations


class Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters = db, table, {}
    def select(self, *_):
        return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def limit(self, *_):
        return self
    def execute(self):
        return SimpleNamespace(data=[
            deepcopy(row) for row in self.db.tables[self.table].values()
            if all(row.get(k) == v for k, v in self.filters.items())
        ])
    def upsert(self, records, on_conflict=None):
        expected = {
            "intelligence_entity_matches": "org_id,identity_kind,identity_hash",
            "intelligence_history_records": "org_id,connector_id,object_type,external_id",
            "intelligence_history_checkpoints": "org_id,connector_id,object_type",
        }
        assert on_conflict == expected[self.table]
        for row in records if isinstance(records, list) else [records]:
            key = tuple(row[k] for k in on_conflict.split(","))
            self.db.tables[self.table][key] = deepcopy(row)
        return self


class Db:
    def __init__(self):
        self.tables = {"intelligence_history_checkpoints": {},
                       "intelligence_history_records": {}, "intelligence_entity_matches": {}}
    def table(self, name):
        return Query(self, name)


class Adapter:
    def __init__(self):
        self.calls = []
    def fetch_page(self, object_type, cursor, limit):
        self.calls.append(dict(cursor))
        if not cursor:
            return {"records": [{"id": "c1", "email": "A@Example.com"}],
                    "next_cursor": {"after": "c1"}}
        return {"records": [{"id": "c2", "email": "b@example.com"}],
                "next_cursor": None}


def test_historical_sync_resumes_and_upsert_is_idempotent():
    db, adapter = Db(), Adapter()
    src = Source("org-1", "connector-a", "hubspot", "contact")
    first = ingest_history(db, src, adapter, max_pages=1)
    assert first["requires_more_pages"] is True
    second = ingest_history(db, src, adapter)
    assert second["complete"] is True
    assert adapter.calls == [{}, {"after": "c1"}]
    assert len(db.tables["intelligence_history_records"]) == 2
    assert next(iter(db.tables["intelligence_history_records"].values()))["normalized_identity"]["email"] == "a@example.com"


def test_provider_failure_preserves_last_successful_checkpoint():
    db = Db()
    src = Source("org-1", "connector-a", "hubspot", "contact")
    ingest_history(db, src, Adapter(), max_pages=1)
    checkpoint = deepcopy(next(iter(db.tables["intelligence_history_checkpoints"].values())))
    class Broken:
        def fetch_page(self, *_):
            raise RuntimeError("offline simulated provider outage")
    with pytest.raises(RuntimeError):
        ingest_history(db, src, Broken())
    assert next(iter(db.tables["intelligence_history_checkpoints"].values())) == checkpoint


def test_cross_provider_identity_matching_never_leaks_tenants():
    rows = [
        {"org_id": "a", "connector_id": "hubspot-a", "object_type": "contact",
         "external_id": "1", "normalized_identity": {"email": "a@example.com"}},
        {"org_id": "a", "connector_id": "zendesk-a", "object_type": "contact",
         "external_id": "2", "normalized_identity": {"email": "a@example.com"}},
        {"org_id": "b", "connector_id": "zendesk-b", "object_type": "contact",
         "external_id": "3", "normalized_identity": {"email": "a@example.com"}},
    ]
    matches = match_observations(rows, org_id="a")
    assert len(matches) == 1
    assert matches[0]["match_status"] == "verified_key"
    assert len(matches[0]["record_references"]) == 2
    assert all(ref["connector_id"] != "zendesk-b" for ref in matches[0]["record_references"])
    assert match_observations(rows, org_id="b") == []


def test_shared_domain_is_candidate_not_automatic_merge():
    rows = [
        {"org_id": "a", "connector_id": "crm", "object_type": "company", "external_id": "1",
         "normalized_identity": {"domain": "example.com"}},
        {"org_id": "a", "connector_id": "support", "object_type": "company", "external_id": "2",
         "normalized_identity": {"domain": "example.com"}},
    ]
    matches = match_observations(rows, org_id="a")
    assert len(matches) == 1
    assert matches[0]["match_status"] == "candidate"


def test_unknown_provider_and_unbounded_pages_rejected():
    with pytest.raises(ValueError):
        ingest_history(Db(), Source("a", "b", "unknown", "contact"), Adapter())
    with pytest.raises(ValueError):
        ingest_history(Db(), Source("a", "b", "hubspot", "contact"), Adapter(), page_size=1000)


def test_authorized_batch_only_syncs_scoped_active_connectors():
    from app.services.intelligence_history_pipeline import run_authorized_history_batch
    db = Db()
    allowed = {"id": "connector-a", "org_id": "a", "status": "active", "type": "hubspot", "config": {"history_sync_enabled": True}, "verified_read_capabilities": ["contacts.read"]}
    foreign = {"id": "connector-b", "org_id": "b", "status": "active", "type": "hubspot"}
    inactive = {"id": "connector-c", "org_id": "a", "status": "disabled", "type": "hubspot"}
    adapter = Adapter()
    def permitted(connector, object_type):
        return connector["id"] == "connector-a" and object_type == "contact"
    result = run_authorized_history_batch(
        db, "a", [allowed, foreign, inactive],
        {"connector-a": adapter, "connector-b": Adapter(),
         "connector-c": Adapter()}, permitted,
    )
    assert len(result["receipts"]) == 1
    assert result["receipts"][0]["complete"] is True
    assert len(db.tables["intelligence_history_records"]) == 2
    assert all(row["org_id"] == "a" for row in db.tables["intelligence_history_records"].values())


def test_missing_read_permission_causes_no_provider_calls():
    from app.services.intelligence_history_pipeline import run_authorized_history_batch
    adapter = Adapter()
    result = run_authorized_history_batch(
        Db(), "a",
        [{"id": "connector-a", "org_id": "a", "status": "active", "type": "hubspot"}],
        {"connector-a": adapter}, lambda *_: False,
    )
    assert adapter.calls == []
    assert result["receipts"] == []


def test_two_provider_offline_history_e2e_yields_persisted_verified_match():
    from app.services.intelligence_history_pipeline import run_authorized_history_batch
    class SinglePage:
        def __init__(self, external):
            self.external = external
        def fetch_page(self, object_type, cursor, limit):
            return {"records": [{"id": self.external, "email": "person@example.com"}],
                    "next_cursor": None}
    db = Db()
    connectors = [
        {"id": "hubspot-1", "org_id": "tenant-a", "status": "active", "type": "hubspot", "config": {"history_sync_enabled": True}, "verified_read_capabilities": ["contacts.read"]},
        {"id": "zendesk-1", "org_id": "tenant-a", "status": "active", "type": "zendesk", "config": {"history_sync_enabled": True}, "verified_read_capabilities": ["contacts.read"]},
    ]
    receipt = run_authorized_history_batch(
        db, "tenant-a", connectors,
        {"hubspot-1": SinglePage("h-1"), "zendesk-1": SinglePage("z-1")},
        lambda connector, object_type: object_type == "contact",
    )
    assert receipt["match_groups"] == 1
    assert len(db.tables["intelligence_history_records"]) == 2
    matches = list(db.tables["intelligence_entity_matches"].values())
    assert len(matches) == 1
    assert matches[0]["match_status"] == "verified_key"
    assert {ref["connector_id"] for ref in matches[0]["record_references"]} == {"hubspot-1", "zendesk-1"}
