"""Host-side privacy and bounded process transport checks; no SDK dependency."""
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

HERE = Path(__file__).resolve().parents[3] / "scripts/memory_benchmark"
sys.path.insert(0, str(HERE))
from sdk_client import Mem0Engine, EngineUnavailable


def test_child_environment_does_not_inherit_provider_credentials(tmp_path, monkeypatch):
    import sdk_client
    captured = {}
    process = SimpleNamespace(stdout=io.StringIO(), stdin=io.StringIO(), poll=lambda: 0)
    def spawn(*args, **kwargs):
        captured.update(kwargs)
        return process
    monkeypatch.setenv("OPENAI_API_KEY", "PRIVATE_OPENAI")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "PRIVATE_SUPABASE")
    monkeypatch.setenv("ALL_PROXY", "socks5://synthetic-proxy:1080")
    monkeypatch.setattr(sdk_client.subprocess, "Popen", spawn)
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32)
    manifest = json.loads((HERE / "engine_source.json").read_text())
    monkeypatch.setattr(engine, "_receive", lambda: {"ready": True, "version": manifest["version"], "files": manifest["files"]})
    engine._start()
    try:
        assert "PRIVATE" not in json.dumps(captured["env"])
        assert captured["env"]["ALL_PROXY"] == "socks5://synthetic-proxy:1080"
        assert captured["env"]["MEM0_TELEMETRY"] == "false"
    finally:
        engine._abort()


def test_worker_deadline_kills_process(tmp_path):
    read_fd, write_fd = os.pipe()
    killed = []
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32, timeout=0.01)
    stream = os.fdopen(read_fd)
    engine.process = SimpleNamespace(stdout=stream, kill=lambda: killed.append(True))
    try:
        with pytest.raises(EngineUnavailable, match="deadline"):
            engine._receive()
        assert killed == [True]
    finally:
        stream.close()
        os.close(write_fd)


def test_search_rejects_oversized_child_response(tmp_path, monkeypatch):
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32)
    monkeypatch.setattr(engine, "call", lambda *a, **kw: {"ok": True, "refs": ["x"] * 9})
    with pytest.raises(EngineUnavailable, match="identities"):
        engine.search(engine.scope("org", "user", "agent"), "synthetic")


def test_namespace_covers_tenant_subject_and_agent(tmp_path):
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32)
    scope = engine.scope("org", "user", "agent")
    for other in (("foreign", "user", "agent"), ("org", "foreign", "agent"), ("org", "user", "foreign")):
        assert engine.scope(*other) != scope
        assert engine.ref(engine.scope(*other), "same-id") != engine.ref(scope, "same-id")


def test_cross_scope_child_bindings_do_not_cross_host_boundary(tmp_path, monkeypatch):
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32)
    own = engine.scope("org-a", "user", "agent")
    other = engine.scope("org-b", "user", "agent")
    foreign_ref = engine.ref(other, "foreign")
    own_ref = engine.ref(own, "own")
    monkeypatch.setattr(engine, "call", lambda *a, **kw: {"ok": True, "refs": [foreign_ref, own_ref, own_ref]})
    assert engine.search(own, "synthetic") == ["own"]


def test_unexpected_sdk_source_is_rejected_and_process_closed(tmp_path, monkeypatch):
    import sdk_client
    process = SimpleNamespace(stdout=io.StringIO(), stdin=io.StringIO(), poll=lambda: 0)
    monkeypatch.setattr(sdk_client.subprocess, "Popen", lambda *a, **kw: process)
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32)
    monkeypatch.setattr(engine, "_receive", lambda: {"ready": True, "version": "wrong", "files": {}})
    with pytest.raises(EngineUnavailable, match="source verification"):
        engine._start()
    assert engine.process is None and process.stdout.closed and process.stdin.closed


def test_oversized_command_is_rejected_before_process_construction(tmp_path):
    engine = Mem0Engine(Path(sys.executable), tmp_path, namespace_key=b"x" * 32)
    with pytest.raises(ValueError, match="Bounded"):
        engine.call("upsert", engine.scope("org", "user", "agent"), text="x" * 100001)
    assert engine.process is None and engine.commands == 0
