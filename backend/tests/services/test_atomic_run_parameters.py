"""Atomic repository mutations fail closed without a database acknowledgement."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.workflows import repository


@pytest.mark.parametrize("response", [None, [], [{"partial": True}], "invalid", {}, {"approval": False}])
def test_malformed_rpc_acknowledgement_never_replaces_parameters(monkeypatch, response):
    client = Mock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=response)
    mirror = Mock()
    monkeypatch.setattr(repository, "mirror_legacy_run_to_contract", mirror)
    with pytest.raises(RuntimeError, match="not acknowledged"):
        repository.merge_run_parameters(client, "run", {"approval": True})
    client.table.assert_not_called()
    mirror.assert_not_called()


def test_missing_atomic_rpc_never_falls_back_to_read_replace(monkeypatch):
    client = Mock()
    client.rpc.return_value.execute.side_effect = RuntimeError("RPC unavailable")
    mirror = Mock()
    monkeypatch.setattr(repository, "mirror_legacy_run_to_contract", mirror)
    with pytest.raises(RuntimeError, match="RPC unavailable"):
        repository.merge_run_parameters(client, "run", {"receipt": True})
    client.table.assert_not_called()
    mirror.assert_not_called()
