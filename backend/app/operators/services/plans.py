from __future__ import annotations

from app.operator_module.services.action_plans import build_action_plan


def _merge_permissions(base: list[str], requires_admin: bool, approval_roles: list[str]) -> list[str]:
    permissions = set(base or [])
    if requires_admin:
        permissions.add("admin")
    for role in approval_roles:
        if role:
            permissions.add(role)
    return sorted(permissions)


def apply_operator_guardrails(plan: dict, operator: dict) -> dict:
    requires_admin = bool(operator.get("requires_admin"))
    requires_approval = bool(operator.get("requires_approval"))
    approval_roles = list(operator.get("approval_roles") or [])

    for step in plan.get("steps", []):
        explanation = step.get("explanation") or {}
        explanation["admin_required"] = bool(explanation.get("admin_required")) or requires_admin
        explanation["approval_required"] = bool(explanation.get("approval_required")) or requires_approval
        explanation["confirmation_required"] = bool(explanation.get("confirmation_required")) or bool(
            explanation.get("executable")
        )
        explanation["permissions_required"] = _merge_permissions(
            explanation.get("permissions_required") or [],
            explanation["admin_required"],
            approval_roles if explanation["approval_required"] else [],
        )
        step["explanation"] = explanation

    guardrails = plan.get("guardrails") or {}
    if requires_admin:
        guardrails.setdefault("admin_restrictions", []).append("Admin required for operator actions")
    if requires_approval:
        guardrails.setdefault("approval_requirements", []).append("Operator actions require approval")
    guardrails.setdefault(
        "execution_restrictions",
        [],
    )
    if "No auto-execution. Confirmation required for any action." not in guardrails["execution_restrictions"]:
        guardrails["execution_restrictions"].append("No auto-execution. Confirmation required for any action.")
    plan["guardrails"] = guardrails
    return plan


def build_operator_action_plan(
    client,
    settings,
    operator: dict,
    org_id: str,
    environment: str,
    primary_context: dict,
    related_contexts: list[dict],
    operator_goal: str | None,
) -> dict:
    plan = build_action_plan(
        client=client,
        settings=settings,
        org_id=org_id,
        environment=environment,
        primary_context=primary_context,
        related_contexts=related_contexts,
        operator_goal=operator_goal,
    )
    return apply_operator_guardrails(plan, operator)
