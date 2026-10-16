"""The deploy gate accepts an older SHA only when backend runtime is identical."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_backend_deploy_revision import verify_revision


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def test_backend_revision_requires_runtime_equivalence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git("init", "-q")
    _git("config", "user.name", "Revision Test")
    _git("config", "user.email", "revision@example.invalid")
    runtime = tmp_path / "backend" / "app" / "example.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("ready = True\n")
    _git("add", ".")
    _git("commit", "-qm", "initial")
    first = _git("rev-parse", "HEAD")
    assert verify_revision(first, first) == (True, "exact_commit")

    docs = tmp_path / "docs" / "note.md"
    docs.parent.mkdir()
    docs.write_text("updated\n")
    _git("add", ".")
    _git("commit", "-qm", "documentation")
    docs_sha = _git("rev-parse", "HEAD")
    assert verify_revision(first, docs_sha) == (True, "runtime_equivalent_ancestor")
    assert verify_revision(docs_sha, first) == (False, "not_target_ancestor")

    runtime.write_text("ready = False\n")
    _git("add", ".")
    _git("commit", "-qm", "backend change")
    runtime_sha = _git("rev-parse", "HEAD")
    assert verify_revision(first, runtime_sha) == (False, "backend_runtime_changed")
    assert verify_revision("not-a-sha", runtime_sha) == (False, "unresolvable_revision")
