"""Dump real executor source for a few actions, to design the endpoint extractor."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.tool_service import _TOOL_REGISTRY

TARGETS = [
    "apollo.people.search",
    "asana.tasks.create",
    "clickup.tasks.create",
    "intercom.contacts.create",
    "hubspot.contacts.create",
    "slack.post_message",
    "monday.items.create",
    "netsuite.customers.create",
]

for action in TARGETS:
    fn = _TOOL_REGISTRY.get(action)
    print("=" * 78)
    if fn is None:
        print(action, "NOT REGISTERED")
        continue
    print(action, "|", fn.__module__, "|", fn.__qualname__)
    try:
        print(inspect.getsource(fn)[:1600])
    except Exception as exc:  # pragma: no cover - diagnostic
        print("ERR", exc)
