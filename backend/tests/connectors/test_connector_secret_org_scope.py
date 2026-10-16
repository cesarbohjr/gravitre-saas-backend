"""The service-role secret reader must never cross the caller's tenant scope."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.connectors.crypto import encrypt_secret
from app.connectors.repository import get_decrypted_secret, get_decrypted_secrets_bulk
from app.connectors.platform import read_masked_api_key
from tests.routers.test_connectors_list_secrets_batch import _Client, _KEY


def _settings():
    return SimpleNamespace(connector_secrets_encryption_key=_KEY, encryption_key="")


def _client():
    return _Client({"connector_secrets": [
        {"org_id": "org-a", "connector_id": "conn-a", "key_name": "api_key",
         "encrypted_value": encrypt_secret("a-secret", _KEY)},
        {"org_id": "org-b", "connector_id": "conn-b", "key_name": "api_key",
         "encrypted_value": encrypt_secret("b-secret", _KEY)},
    ]})


def test_single_secret_cannot_be_selected_by_foreign_connector_id():
    client = _client()
    assert get_decrypted_secret(client, "conn-a", "api_key", _settings(), org_id="org-a") == "a-secret"
    assert get_decrypted_secret(client, "conn-b", "api_key", _settings(), org_id="org-a") is None


def test_bulk_secret_reader_filters_mixed_org_ids():
    assert get_decrypted_secrets_bulk(
        _client(), ["conn-a", "conn-b", "missing"], "api_key", _settings(), org_id="org-a",
    ) == {"conn-a": "a-secret", "conn-b": None, "missing": None}


def test_absent_scope_never_queries_or_decrypts():
    client = _client()
    assert get_decrypted_secret(client, "conn-a", "api_key", _settings(), org_id="") is None
    assert get_decrypted_secrets_bulk(client, ["conn-a"], "api_key", _settings(), org_id="") == {"conn-a": None}
    assert client.executions == []
    with pytest.raises(TypeError):
        get_decrypted_secret(client, "conn-a", "api_key", _settings())


def test_masked_legacy_or_preloaded_keys_still_require_matching_row_scope():
    client = _client()
    assert read_masked_api_key(
        client, "conn-b", {"id": "conn-b", "org_id": "org-b"}, _settings(),
        org_id="org-a", preloaded_secret="b-secret",
    ) is None
    assert client.executions == []


def test_every_app_secret_and_oauth_reader_passes_explicit_scope():
    root = Path(__file__).resolve().parents[2] / "app"
    names = {"get_decrypted_secret", "get_decrypted_secrets_bulk", "load_oauth_tokens",
             "load_linkedin_access_token", "read_masked_api_key", "masked_api_key_for_response"}
    missing = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
                if not any(keyword.arg == "org_id" for keyword in node.keywords):
                    missing.append(f"{path.relative_to(root)}:{node.lineno}")
    assert missing == []
