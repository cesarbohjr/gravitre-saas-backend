"""Checks that isolated E2E cannot silently point at production or an empty DB."""
import importlib.util
from pathlib import Path
from urllib.error import HTTPError

import pytest


MODULE = Path(__file__).resolve().parents[2] / "scripts" / "check-isolated-acceptance-db.py"
spec = importlib.util.spec_from_file_location("isolated_acceptance_db", MODULE)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_refuses_every_other_supabase_project_before_network():
    calls = []

    def request(*args, **kwargs):
        calls.append(args)
        return FakeResponse()

    with pytest.raises(ValueError, match="non-acceptance"):
        checker.check_schema("https://some-production-project.supabase.co", "secret", open_request=request)
    assert calls == []


def test_requires_all_billing_schema_tables():
    requested = []

    def request(req, **kwargs):
        requested.append(req.full_url)
        if "/org_billing?" in req.full_url:
            raise HTTPError(req.full_url, 404, "missing", {}, None)
        return FakeResponse()

    with pytest.raises(RuntimeError, match="org_billing"):
        checker.check_schema(checker.ACCEPTANCE_URL, "test-only", open_request=request)
    assert len(requested) == len(checker.REQUIRED_TABLES)


def test_read_only_table_probe_does_not_fetch_rows_or_write():
    requests = []

    def request(req, **kwargs):
        requests.append(req)
        return FakeResponse()

    assert checker.check_schema(checker.ACCEPTANCE_URL, "test-only", open_request=request) == checker.REQUIRED_TABLES
    assert all(req.get_method() == "GET" and "limit=0" in req.full_url for req in requests)
    assert all(req.headers["Authorization"].startswith("Bearer ") for req in requests)
