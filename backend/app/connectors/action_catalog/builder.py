"""Build vendor catalog specs from compact definitions."""
from __future__ import annotations

from app.connectors.action_catalog.models import (
    ActionKind,
    ActionSpec,
    ActionTier,
    DemoWorkflowSpec,
    VendorCatalogSpec,
    WorkflowStepSpec,
)


def _scope(vendor: str, suffix: str) -> tuple[str, ...]:
    return (f"{vendor}:{suffix}", f"{vendor}:*")


def action(
    vendor: str,
    suffix: str,
    name: str,
    *,
    tier: ActionTier,
    kind: ActionKind,
    scope_suffix: str,
    description: str | None = None,
    api_reference: str | None = None,
    idempotent: bool = False,
    destructive: bool = False,
    requires_approval: bool = False,
) -> ActionSpec:
    desc = description or f"{name} via {vendor} API"
    return ActionSpec(
        id=f"{vendor}.{suffix}",
        name=name,
        description=desc,
        tier=tier,
        kind=kind,
        scopes=_scope(vendor, scope_suffix),
        api_reference=api_reference,
        idempotent=idempotent,
        destructive=destructive,
        requires_approval=requires_approval,
    )


def _wf_step_read(vendor: str, suffix: str, name: str) -> WorkflowStepSpec:
    return WorkflowStepSpec(
        id=f"read_{suffix.replace('.', '_')}",
        name=name,
        type="invoke_tool",
        action=f"{vendor}.{suffix}",
    )


def _wf_step_write(vendor: str, suffix: str, name: str) -> WorkflowStepSpec:
    return WorkflowStepSpec(
        id=f"write_{suffix.replace('.', '_')}",
        name=name,
        type="invoke_tool",
        action=f"{vendor}.{suffix}",
    )


def standard_demo_workflows(
    vendor: str,
    display: str,
    *,
    read_primary: str,
    read_secondary: str | None = None,
    write_primary: str,
    advanced_primary: str,
    department: str,
) -> tuple[DemoWorkflowSpec, ...]:
    """Four real-world workflow patterns per connector."""
    read2 = read_secondary or read_primary
    return (
        DemoWorkflowSpec(
            id=f"{vendor}-inbound-triage",
            name=f"{display} inbound triage",
            description=f"New event → read {read_primary.split('.', 1)[-1]} → notify team in Slack.",
            department=department,
            steps=(
                WorkflowStepSpec(id="trigger", name="Inbound event", type="trigger"),
                _wf_step_read(vendor, read_primary, f"Read {display} record"),
                WorkflowStepSpec(
                    id="notify_slack",
                    name="Notify Slack channel",
                    type="invoke_tool",
                    action="slack.post_message",
                ),
            ),
            risk_level="low",
        ),
        DemoWorkflowSpec(
            id=f"{vendor}-qualify-update",
            name=f"{display} qualify and update",
            description=f"Agent reviews record → writes {write_primary.split('.', 1)[-1]}.",
            department=department,
            steps=(
                WorkflowStepSpec(id="trigger", name="Record selected", type="trigger"),
                _wf_step_read(vendor, read_primary, "Load record context"),
                WorkflowStepSpec(
                    id="agent_review",
                    name="Agent qualification",
                    type="agent",
                    description=f"Review {display} data and decide next action.",
                ),
                _wf_step_write(vendor, write_primary, "Apply update"),
            ),
            risk_level="medium",
            requires_approval=True,
        ),
        DemoWorkflowSpec(
            id=f"{vendor}-scheduled-digest",
            name=f"{display} weekly digest",
            description=f"Scheduled list via {read2.split('.', 1)[-1]} → summary to Slack.",
            department=department,
            steps=(
                WorkflowStepSpec(id="schedule", name="Weekly schedule", type="trigger"),
                _wf_step_read(vendor, read2, "List recent records"),
                WorkflowStepSpec(
                    id="digest_slack",
                    name="Post digest",
                    type="invoke_tool",
                    action="slack.post_message",
                ),
            ),
            risk_level="low",
        ),
        DemoWorkflowSpec(
            id=f"{vendor}-advanced-flow",
            name=f"{display} advanced orchestration",
            description=f"Multi-step flow using {advanced_primary.split('.', 1)[-1]}.",
            department=department,
            steps=(
                WorkflowStepSpec(id="trigger", name="Workflow start", type="trigger"),
                _wf_step_read(vendor, read_primary, "Fetch source record"),
                _wf_step_write(vendor, advanced_primary, "Run advanced action"),
                WorkflowStepSpec(
                    id="complete_notify",
                    name="Completion notice",
                    type="invoke_tool",
                    action="slack.post_message",
                ),
            ),
            risk_level="high",
            requires_approval=True,
            success_criteria=("Action completes without API error", "Audit trail captured"),
        ),
    )


def build_vendor(
    vendor: str,
    display: str,
    category: str,
    api_docs_url: str,
    *,
    shipped: bool = False,
    department: str = "operations",
    v1: tuple[ActionSpec, ...],
    v2: tuple[ActionSpec, ...],
    v3: tuple[ActionSpec, ...],
) -> VendorCatalogSpec:
    read_primary = v1[0].id.split(".", 1)[-1]
    read_secondary = v1[1].id.split(".", 1)[-1] if len(v1) > 1 else read_primary
    write_primary = v2[0].id.split(".", 1)[-1]
    advanced_primary = v3[0].id.split(".", 1)[-1]
    return VendorCatalogSpec(
        vendor=vendor,
        display_name=display,
        category=category,
        api_docs_url=api_docs_url,
        shipped=shipped,
        v1=v1,
        v2=v2,
        v3=v3,
        demo_workflows=standard_demo_workflows(
            vendor,
            display,
            read_primary=read_primary,
            read_secondary=read_secondary,
            write_primary=write_primary,
            advanced_primary=advanced_primary,
            department=department,
        ),
    )
