"""Audit instruments must pass a real actor, or they write nothing at all.

write_audit_event skips the audit_events insert entirely when actor_id is not a
UUID (app/workflows/audit.py) — it logs a warning and returns, because
audit_events.actor_id is uuid NOT NULL and FKs auth.users.

`actor_id=None` therefore produces an instrument that looks correct, never
raises, and silently records nothing. Three separate instruments in
agent_intelligence.py were written that way during the dormant-model-call audit,
and all three read zero events in production. Two of those zeroes were initially
read as "this code path is never reached" — the opposite of the truth, and very
nearly the basis for retiring live code.

This guard makes that specific mistake impossible to repeat quietly.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _audit_calls_with_literal_none_actor() -> list[str]:
    offenders: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (
                fn.id
                if isinstance(fn, ast.Name)
                else fn.attr
                if isinstance(fn, ast.Attribute)
                else ""
            )
            if name != "write_audit_event":
                continue
            for kw in node.keywords:
                if kw.arg != "actor_id":
                    continue
                if isinstance(kw.value, ast.Constant) and kw.value.value is None:
                    action = next(
                        (
                            k.value.value
                            for k in node.keywords
                            if k.arg == "action" and isinstance(k.value, ast.Constant)
                        ),
                        "<dynamic>",
                    )
                    rel = path.relative_to(APP.parent).as_posix()
                    offenders.append(f"{rel}:{node.lineno} action={action}")
    return offenders


# Empty, and it should stay that way. The two original entries were the
# connector-health events this guard found on the day it was written; they now
# resolve a real actor via resolve_connector_audit_actor (connector.created_by,
# falling back to the org owner/admin) and skip loudly rather than silently when
# neither exists. This list may only SHRINK — a new entry means a fresh silent
# instrument shipped, and needs a real actor rather than an exemption.
KNOWN_NONE_ACTOR: set[str] = set()


def test_no_audit_event_is_written_with_a_none_actor() -> None:
    offenders = [o for o in _audit_calls_with_literal_none_actor() if o not in KNOWN_NONE_ACTOR]
    assert not offenders, (
        "write_audit_event(actor_id=None) silently skips the audit_events insert, "
        "so these instruments record nothing while appearing to work. Pass a real "
        "user/actor UUID:\n  " + "\n  ".join(offenders)
    )


def test_known_list_does_not_rot() -> None:
    """A stale entry means someone fixed a site; the list must shrink, not linger."""
    current = set(_audit_calls_with_literal_none_actor())
    stale = sorted(KNOWN_NONE_ACTOR - current)
    assert not stale, (
        "These are no longer passing actor_id=None but are still listed as known. "
        "Remove them so the baseline cannot hide a regression:\n  " + "\n  ".join(stale)
    )


def test_guard_detects_a_none_actor_when_one_exists(tmp_path: Path) -> None:
    """The guard must actually fire — a scanner that never matches is not a guard."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "write_audit_event(client, org_id=o, actor_id=None, action='x.y',\n"
        "                  resource_type='conversation', resource_id=r)\n",
        encoding="utf-8",
    )
    tree = ast.parse(sample.read_text(encoding="utf-8"))
    found = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", "") == "write_audit_event"
        and any(
            k.arg == "actor_id"
            and isinstance(k.value, ast.Constant)
            and k.value.value is None
            for k in n.keywords
        )
    ]
    assert len(found) == 1
