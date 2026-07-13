"""Phase 1.5 unit tests — shared surfaces, not parallel stacks."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.intelligence_packs.shared import durable_cache, normalize, provenance, signals
from app.intelligence_packs.shared.mappers import (
    map_fred,
    map_nvd,
    map_world_bank,
    register_builtin_mappers_and_signals,
)
from app.intelligence_packs.shared.normalize import (
    normalize_source_result,
    registered_mappers,
)
from app.intelligence_packs.shared.pipeline import ensure_plumbing_registered, run_shared_ingestion
from app.intelligence_packs.shared.schemas import ok_result
from app.intelligence_packs.shared.signals import (
    evaluate_pack_signals,
    registered_signals,
)


@pytest.fixture(autouse=True)
def _bootstrap():
    ensure_plumbing_registered()
    register_builtin_mappers_and_signals()


def test_gate_a_single_shared_surfaces_exist():
    assert durable_cache.cache_get.__module__.endswith("durable_cache")
    assert durable_cache.cache_set.__module__.endswith("durable_cache")
    assert normalize.normalize_source_result.__module__.endswith("normalize")
    assert provenance.write_external_entity_with_provenance.__module__.endswith("provenance")
    assert signals.register_signal.__module__.endswith("signals")


def test_fred_and_nvd_are_registrations_not_copies():
    assert "fred" in registered_mappers()
    assert "nvd" in registered_mappers()
    assert "fred.macro_observation" in registered_signals()
    assert "nvd.cve_present" in registered_signals()
    # Same dispatcher function object for both
    fred_raw = ok_result(
        "fred",
        auth_mode="gravitree_managed",
        data=[{"date": "2024-01-01", "value": "100"}],
        provenance={"series_id": "GDP"},
    )
    nvd_raw = ok_result(
        "nvd",
        auth_mode="gravitree_managed",
        data={"vulnerabilities": [{"cve": {"id": "CVE-2024-21762", "descriptions": [{"value": "test"}]}}]},
        provenance={"cve": "CVE-2024-21762"},
    )
    fred_recs = normalize_source_result("fred", fred_raw)
    nvd_recs = normalize_source_result("nvd", nvd_raw)
    assert fred_recs[0]["entity_type"] == "macro_series"
    assert nvd_recs[0]["entity_type"] == "cve"
    assert evaluate_pack_signals(fred_recs[0])
    assert evaluate_pack_signals(nvd_recs[0])


def test_world_bank_third_source_is_mapper_registration_only():
    """Gate B: WB uses same dispatcher + registry; no parallel stack."""
    assert "world_bank" in registered_mappers()
    assert "world_bank.indicator_observation" in registered_signals()
    raw = ok_result(
        "world_bank",
        auth_mode="gravitree_managed",
        data=[{"date": "2023", "value": 1.0}],
        provenance={"country": "US", "indicator": "NY.GDP.MKTP.CD"},
    )
    # Must go through the ONE dispatcher
    recs = normalize_source_result("world_bank", raw)
    assert recs[0]["vendor"] == "world_bank"
    assert evaluate_pack_signals(recs[0])


def test_unregistered_vendor_raises():
    with pytest.raises(KeyError):
        normalize_source_result("not_a_real_vendor", ok_result("x", auth_mode="gravitree_managed", data={}))


def test_run_shared_ingestion_uses_shared_tables(monkeypatch):
    store: dict[str, list] = {
        "knowledge_pack_cache": [],
        "external_entities": [],
        "external_signals": [],
    }

    class FakeTable:
        def __init__(self, name: str):
            self.name = name
            self._filters: dict[str, str] = {}
            self._payload = None
            self._op = "select"

        def select(self, *_a, **_k):
            self._op = "select"
            return self

        def eq(self, k, v):
            self._filters[k] = v
            return self

        def limit(self, *_a, **_k):
            return self

        def insert(self, row):
            self._op = "insert"
            self._payload = row
            return self

        def update(self, row):
            self._op = "update"
            self._payload = row
            return self

        def execute(self):
            if self._op == "insert":
                store[self.name].append(dict(self._payload))
                return SimpleNamespace(data=[self._payload])
            if self._op == "update":
                for row in store[self.name]:
                    if all(str(row.get(k)) == str(v) for k, v in self._filters.items()):
                        row.update(self._payload)
                        return SimpleNamespace(data=[row])
                return SimpleNamespace(data=[])
            # select
            rows = store[self.name]
            matched = [
                r
                for r in rows
                if all(str(r.get(k)) == str(v) for k, v in self._filters.items())
            ]
            return SimpleNamespace(data=matched)

    client = MagicMock()
    client.table.side_effect = lambda name: FakeTable(name)

    raw = ok_result(
        "fred",
        auth_mode="gravitree_managed",
        data=[{"date": "2024-01-01", "value": "27.5"}],
        provenance={"series_id": "GDP", "source": "fred"},
    )
    result = run_shared_ingestion(
        client,
        org_id="org-1",
        vendor="fred",
        cache_key="series:GDP",
        raw=raw,
        ttl_seconds=60,
    )
    assert result["ok"] is True
    assert result["cache"]["id"]
    assert len(result["entities"]) == 1
    assert len(result["signals"]) == 1
    assert store["knowledge_pack_cache"]
    assert store["external_entities"]
    assert store["external_signals"]
    assert "durable_cache.cache_get" in result["shared_surfaces"]["cache_get"]


def test_mappers_produce_expected_shapes():
    fred = map_fred(
        ok_result("fred", auth_mode="gravitree_managed", data=[{"date": "2020", "value": "1"}], provenance={"series_id": "GDP"})
    )
    nvd = map_nvd(
        ok_result(
            "nvd",
            auth_mode="gravitree_managed",
            data={"vulnerabilities": [{"cve": {"id": "CVE-1", "descriptions": [{"value": "x"}]}}]},
            provenance={"cve": "CVE-1"},
        )
    )
    wb = map_world_bank(
        ok_result(
            "world_bank",
            auth_mode="gravitree_managed",
            data=[{"date": "2022", "value": 9}],
            provenance={"country": "US", "indicator": "NY.GDP.MKTP.CD"},
        )
    )
    assert fred[0]["external_id"] == "GDP"
    assert nvd[0]["external_id"] == "CVE-1"
    assert wb[0]["external_id"] == "US:NY.GDP.MKTP.CD"
