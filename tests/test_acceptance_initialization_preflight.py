"""Guardrails for preparing a remote acceptance baseline."""
import importlib.util
import io
import hashlib
from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = load("prepare_acceptance_baseline", "scripts/prepare_acceptance_baseline.py")
remote = load("check_acceptance_remote_readonly", "scripts/check_acceptance_remote_readonly.py")


def test_rejects_tampered_baseline(tmp_path):
    (tmp_path / "production-schema-baseline.sql").write_text("CREATE TABLE public.test (id int);")
    (tmp_path / "production-schema-baseline.sha256").write_text("0" * 64 + "  production-schema-baseline.sql\n")
    with pytest.raises(ValueError, match="SHA256"):
        baseline.prepare(tmp_path)


def test_remote_rejects_wrong_project_without_network():
    calls = []

    def request(*args, **kwargs):
        calls.append(1)

    with pytest.raises(ValueError, match="non-acceptance"):
        remote.inspect("production-project", "fake", open_request=request)
    assert not calls


def test_remote_refuses_nonempty_target():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def request(req, **kwargs):
        assert req.method == "POST"
        assert json.loads(req.data)["read_only"] is True
        return Response()

    old = remote.json.load
    try:
        remote.json.load = lambda _: [{"public_tables": 1, "recorded_migrations": 0}]
        with pytest.raises(ValueError, match="not empty"):
            remote.inspect(remote.ACCEPTANCE_PROJECT_REF, "fake", open_request=request)
    finally:
        remote.json.load = old
