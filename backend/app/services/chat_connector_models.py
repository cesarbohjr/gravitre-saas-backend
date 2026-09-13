"""Shared models and aliases for chat connector execution."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

LIST_CREATE_INTENT = re.compile(
    # Allow a short vendor/adj span: "create an Apollo contact list", "make a new list".
    # F3: also "set up" / "spin up" / desire forms ("I want a … segment named X").
    r"(?:"
    r"\b(?:create|new|add|make|build|start|(?:set|spin)\s+up)\s+(?:(?:a|an)\s+)?(?:[\w.-]+\s+){0,3}(?:contact\s+|static\s+)?(?:list|group|segment)\b"
    r"|"
    r"\b(?:i\s+)?(?:want|need)\s+(?:(?:a|an)\s+)?(?:[\w.-]+\s+){0,4}(?:contact\s+|static\s+)?(?:list|group|segment)\b"
    r")",
    re.I,
)

# Deprecated: use connector_semantic_registry.integration_aliases_dict() for new code.
from app.services.connector_semantic_registry import integration_aliases_dict

INTEGRATION_ALIASES: dict[str, tuple[str, ...]] = integration_aliases_dict()


@dataclass(frozen=True)
class ConnectorActionPlan:
    tool_name: str
    invoke_action: str
    integration: str
    kind: str
    label: str
    args: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    approval_reason: str | None = None
    destructive: bool = False
    inferred_fields: tuple[str, ...] = ()
    inference_sources: dict[str, str] = field(default_factory=dict)
