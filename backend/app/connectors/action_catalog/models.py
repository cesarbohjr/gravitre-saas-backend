"""Connector action + demo workflow catalog models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented

ActionTier = Literal["v1", "v2", "v3", "v4"]
ActionKind = Literal["read", "write", "advanced"]


@dataclass(frozen=True)
class WorkflowFieldSpec:
    """Chat workflow validation field for connector actions."""

    label: str
    arg_keys: tuple[str, ...]
    sensitive: bool = False
    inferrable: bool = True
    validator: str | None = None


@dataclass(frozen=True)
class ActionWorkflowSchema:
    """Declarative required/optional fields for chat plan validation."""

    intent_label: str
    known_defaults: tuple[tuple[str, str], ...] = ()
    required_fields: tuple[WorkflowFieldSpec, ...] = ()
    optional_fields: tuple[WorkflowFieldSpec, ...] = ()


@dataclass(frozen=True)
class ActionSpec:
    """Declarative connector tool action mapped to invoke_tool keys."""

    id: str
    name: str
    description: str
    tier: ActionTier
    kind: ActionKind
    scopes: tuple[str, ...]
    api_reference: str | None = None
    idempotent: bool = False
    destructive: bool = False
    requires_approval: bool = False
    input_schema: dict[str, Any] | None = None
    workflow_schema: ActionWorkflowSchema | None = None
    # BusinessOutcome Diff/Undo — real catalog property (None = irreversible / no diff).
    compensating_action: str | None = None
    supports_diff: bool | None = None

    @property
    def tool(self) -> str:
        return self.id

    def to_dict(self, *, vendor: str, implemented: bool) -> dict[str, Any]:
        from app.connectors.action_catalog.action_parameters import resolve_action_schema

        tool_key = self.id if "." in self.id and self.id.split(".", 1)[0] == vendor else (
            self.id if self.id.startswith(f"{vendor}.") else f"{vendor}.{self.id}"
        )
        suffix = tool_key.split(".", 1)[-1] if "." in tool_key else tool_key
        schema = resolve_action_schema(
            tool_key,
            kind=self.kind,
            suffix=suffix,
            description=self.description,
            explicit_schema=self.input_schema,
        )
        payload: dict[str, Any] = {
            "id": self.id.split(".", 1)[-1] if self.id.startswith(f"{vendor}.") else self.id,
            "tool": tool_key,
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "kind": self.kind,
            "scopes": list(self.scopes),
            "apiReference": self.api_reference,
            "idempotent": self.idempotent,
            "destructive": self.destructive,
            "requiresApproval": self.requires_approval,
            "implemented": implemented,
            "inputSchema": schema,
            "compensatingAction": self.compensating_action,
            "supportsDiff": self.supports_diff,
        }
        return payload


@dataclass(frozen=True)
class WorkflowStepSpec:
    id: str
    name: str
    type: str
    action: str | None = None
    description: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
        }
        if self.description:
            payload["description"] = self.description
        if self.action:
            payload["action"] = self.action
        if self.config:
            payload["config"] = self.config
        return payload


@dataclass(frozen=True)
class DemoWorkflowSpec:
    id: str
    name: str
    description: str
    department: str
    steps: tuple[WorkflowStepSpec, ...]
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_approval: bool = False
    success_criteria: tuple[str, ...] = ()

    def to_dict(self, *, vendor: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "vendor": vendor,
            "name": self.name,
            "description": self.description,
            "department": self.department,
            "riskLevel": self.risk_level,
            "requiresApproval": self.requires_approval,
            "successCriteria": list(self.success_criteria),
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class VendorCatalogSpec:
    vendor: str
    display_name: str
    category: str
    api_docs_url: str
    v1: tuple[ActionSpec, ...]
    v2: tuple[ActionSpec, ...]
    v3: tuple[ActionSpec, ...]
    demo_workflows: tuple[DemoWorkflowSpec, ...]
    shipped: bool = False
    v4: tuple[ActionSpec, ...] = field(default_factory=tuple)

    def all_actions(self) -> tuple[ActionSpec, ...]:
        return self.v1 + self.v2 + self.v3 + self.v4

    def to_dict(self, *, implemented_tools: set[str]) -> dict[str, Any]:
        def _tool_key(action: ActionSpec) -> str:
            if "." in action.id and action.id.split(".", 1)[0] == self.vendor:
                return action.id
            return f"{self.vendor}.{action.id}"

        def _serialize(actions: tuple[ActionSpec, ...]) -> list[dict[str, Any]]:
            return [
                action.to_dict(
                    vendor=self.vendor,
                    implemented=catalog_tool_is_implemented(_tool_key(action), implemented_tools),
                )
                for action in actions
            ]

        v1_list = _serialize(self.v1)
        v2_list = _serialize(self.v2)
        v3_list = _serialize(self.v3)
        v4_list = _serialize(self.v4)
        read_tools = [a["tool"] for a in v1_list]
        tiers: dict[str, Any] = {
            "v1": {"label": "Read", "description": "List, get, and search — safe read-only API operations.", "actions": v1_list},
            "v2": {"label": "Write", "description": "Create and update records — mutating operations, often approval-gated.", "actions": v2_list},
            "v3": {"label": "Advanced", "description": "Search, batch, enroll, transition — orchestration and cross-object flows.", "actions": v3_list},
        }
        if v4_list:
            tiers["v4"] = {
                "label": "Orchestration",
                "description": "Cross-object search, pipelines, and destructive orchestration — approval recommended.",
                "actions": v4_list,
            }
        return {
            "vendor": self.vendor,
            "displayName": self.display_name,
            "category": self.category,
            "apiDocsUrl": self.api_docs_url,
            "shipped": self.shipped,
            "tiers": tiers,
            "readTools": read_tools,
            "demoWorkflows": [wf.to_dict(vendor=self.vendor) for wf in self.demo_workflows],
        }
