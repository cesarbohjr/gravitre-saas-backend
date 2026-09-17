"""Typed product-focus contract for canonical assistant chat.

This is an *input* to ContextCompiler / CognitiveTurnKernel — not a second
context system. Agent scope remains AssistantChatRequest.agent_id.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WorkspaceObjectType = Literal[
    "entity",
    "agent",
    "workflow",
    "run",
    "connector",
    "relationship",
    "department",
    "signal",
    "customer",
    "company",
    "contact",
    "product",
]

ALLOWED_OBJECT_TYPES: frozenset[str] = frozenset(
    (
        "entity",
        "agent",
        "workflow",
        "run",
        "connector",
        "relationship",
        "department",
        "signal",
        "customer",
        "company",
        "contact",
        "product",
    )
)

ENTITY_STORE_TYPES: frozenset[str] = frozenset(
    ("entity", "customer", "company", "contact", "product")
)

IDENTITY_ONLY_TYPES: frozenset[str] = frozenset(("department", "signal"))


class WorkspaceSelection(BaseModel):
    """Identity of the object the user is looking at. Label is not authority."""

    model_config = ConfigDict(extra="forbid")

    object_type: str = Field(..., min_length=1, max_length=64)
    object_id: str = Field(..., min_length=1, max_length=128)
    label: str | None = Field(default=None, max_length=200)

    @field_validator("object_type", "object_id", "label", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value


class WorkspaceFocus(BaseModel):
    """Per-turn UI focus. Optional. Missing is valid (plain Ask)."""

    model_config = ConfigDict(extra="forbid")

    surface: str | None = Field(default=None, max_length=64)
    route: str | None = Field(default=None, max_length=512)
    selection: WorkspaceSelection | None = None

    @field_validator("surface", "route", mode="before")
    @classmethod
    def _strip_opt(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value
