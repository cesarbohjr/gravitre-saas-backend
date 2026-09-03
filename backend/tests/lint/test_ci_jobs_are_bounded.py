"""Every CI job carries a time ceiling, and no step waits on a live server.

Written after the Integration Smoke Test pinned `main` for 40+ minutes. Two
independent mistakes combined:

* the readiness-failure branch called ``wait $SERVER_PID`` on a process that,
  by definition of reaching that branch, was still starting -- so the shell
  blocked forever instead of reporting a legible failure;
* no job in the workflow had ``timeout-minutes``, so nothing bounded it.

The reason it went unnoticed for a month is worth stating, because it is this
program's Class C failure again: the job ``needs: [web, backend]``, backend was
red from 2026-08-06, so the job was **skipped** on all 40 runs. It never
reported a failure because it never ran. Fixing pytest is what exposed it.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[3] / ".github" / "workflows"


def _workflow_files() -> list[Path]:
    files = sorted(p for p in WORKFLOWS.glob("*.yml"))
    assert files, f"no workflows found under {WORKFLOWS} -- this guard is blind"
    return files


def _jobs(path: Path) -> dict[str, dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    jobs = doc.get("jobs") or {}
    return {name: spec for name, spec in jobs.items() if isinstance(spec, dict)}


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_every_job_has_a_time_ceiling(path: Path) -> None:
    unbounded = [
        name
        for name, spec in _jobs(path).items()
        # `uses:` jobs inherit the called workflow's own bounds.
        if "uses" not in spec and not spec.get("timeout-minutes")
    ]
    assert not unbounded, (
        f"{path.name}: jobs without timeout-minutes: {unbounded}. "
        "An unbounded job can hang indefinitely and pin the branch tip."
    )


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_no_step_waits_on_a_background_server(path: Path) -> None:
    """``wait`` on a still-running server is the hang, not a symptom of it.

    Matched on the source text rather than parsed shell: the point is to stop the
    idiom being reintroduced anywhere in a run block, and a substring check
    cannot be fooled by quoting.
    """
    for name, spec in _jobs(path).items():
        for step in spec.get("steps") or []:
            run = str((step or {}).get("run") or "")
            if "SERVER_PID" not in run:
                continue
            assert "wait $SERVER_PID" not in run, (
                f"{path.name}:{name} waits on SERVER_PID. If the server is slow "
                "rather than dead, this blocks until the job timeout. Print the "
                "captured log and exit instead."
            )
