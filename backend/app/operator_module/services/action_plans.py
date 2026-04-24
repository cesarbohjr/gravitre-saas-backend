from __future__ import annotations

from uuid import uuid4

from supabase import Client

from app.config import Settings
from app.connectors.repository import get_connector
from app.rag.ingest import get_source
from app.workflows.policy import PolicyResolutionError, resolve_policy
from app.workflows.repository import get_run_with_steps, get_workflow_def


def _permissions(admin_required: bool, approval_required: bool) -> list[str]:
    permissions = ["member"]
    if admin_required:
        permissions = ["admin"]
    if approval_required:
        permissions.append("approver")
    return permissions


def _step(
    step_id: str,
    title: str,
    description: str,
    step_type: str,
    environment: str,
    data_used: list[str],
    approval_required: bool,
    admin_required: bool,
    executable: bool,
    draft_only: bool,
    confirmation_required: bool,
    linked_entity: dict | None = None,
    dependencies: list[str] | None = None,
) -> dict:
    return {
        "id": step_id,
        "title": title,
        "description": description,
        "step_type": step_type,
        "linked_entity": linked_entity,
        "dependencies": dependencies or [],
        "explanation": {
            "data_used": data_used,
            "environment": environment,
            "permissions_required": _permissions(admin_required, approval_required),
            "approval_required": approval_required,
            "admin_required": admin_required,
            "executable": executable,
            "draft_only": draft_only,
            "confirmation_required": confirmation_required,
        },
    }


def build_action_plan(
    client: Client,
    settings: Settings,
    org_id: str,
    environment: str,
    primary_context: dict,
    related_contexts: list[dict] | None,
    operator_goal: str | None,
) -> dict:
    context_type = primary_context.get("type")
    context_id = primary_context.get("id")
    steps: list[dict] = []
    guardrail_approvals: list[str] = []
    guardrail_admin: list[str] = []
    guardrail_exec: list[str] = []
    plan_title = "Action Plan"
    plan_summary = operator_goal or "Operator-guided plan based on active context."

    if context_type == "run":
        run = get_run_with_steps(client, org_id, context_id, environment_name=environment)
        if not run:
            raise ValueError("Run not found")
        approval_required = bool((run or {}).get("required_approvals") or 0)
        if approval_required:
            guardrail_approvals.append("Approval required for workflow execution")
        steps = [
            _step(
                "step-1",
                "Review run details",
                "Inspect the run summary, steps, and failure metadata.",
                "review_run",
                environment,
                ["run.summary", "run.steps"],
                approval_required=False,
                admin_required=False,
                executable=False,
                draft_only=True,
                confirmation_required=False,
                linked_entity={"type": "run", "id": context_id},
            ),
            _step(
                "step-2",
                "Inspect related integration",
                "Review integration health and recent failures before retrying.",
                "inspect_connector",
                environment,
                ["run.steps", "connector.summary"],
                approval_required=False,
                admin_required=True,
                executable=False,
                draft_only=True,
                confirmation_required=False,
            ),
            _step(
                "step-3",
                "Prepare controlled retry",
                "Draft a retry proposal and confirm approvals before execution.",
                "prepare_retry",
                environment,
                ["run.summary", "policy.approvals"],
                approval_required=approval_required,
                admin_required=True,
                executable=True,
                draft_only=False,
                confirmation_required=True,
                dependencies=["step-1", "step-2"],
            ),
        ]
        guardrail_admin.append("Admin required for integration updates")
        guardrail_exec.append("Execution requires explicit confirmation")

    elif context_type == "workflow":
        workflow = get_workflow_def(client, org_id, context_id)
        if not workflow:
            raise ValueError("Workflow not found")
        approval_required = False
        try:
            required_approvals, _ = resolve_policy(client, org_id, context_id, "execute")
            approval_required = required_approvals > 0
        except PolicyResolutionError:
            approval_required = False
        if approval_required:
            guardrail_approvals.append("Approval required for workflow execution")
        steps = [
            _step(
                "step-1",
                "Review workflow definition",
                "Validate the active workflow version and recent changes.",
                "review_workflow",
                environment,
                ["workflow.summary", "workflow.active_version"],
                approval_required=False,
                admin_required=False,
                executable=False,
                draft_only=True,
                confirmation_required=False,
                linked_entity={"type": "workflow", "id": context_id},
            ),
            _step(
                "step-2",
                "Draft workflow update",
                "Create a draft version to address identified issues.",
                "draft_workflow",
                environment,
                ["workflow.versions", "policy.guardrails"],
                approval_required=False,
                admin_required=True,
                executable=False,
                draft_only=True,
                confirmation_required=False,
            ),
            _step(
                "step-3",
                "Prepare execution plan",
                "Queue an execution request with approvals as required.",
                "prepare_execute",
                environment,
                ["policy.approvals", "workflow.active_version"],
                approval_required=approval_required,
                admin_required=True,
                executable=True,
                draft_only=False,
                confirmation_required=True,
                dependencies=["step-1"],
            ),
        ]
        guardrail_admin.append("Admin required for workflow version changes")
        guardrail_exec.append("Execution requires explicit confirmation")

    elif context_type == "connector":
        connector = get_connector(client, org_id, context_id, environment_name=environment)
        if not connector:
            raise ValueError("Integration not found")
        connector_type = (connector or {}).get("type") or "connector"
        steps = [
            _step(
                "step-1",
                "Review integration health",
                "Inspect status and recent error trends for this integration.",
                "review_connector",
                environment,
                ["connector.summary"],
                approval_required=False,
                admin_required=False,
                executable=False,
                draft_only=True,
                confirmation_required=False,
                linked_entity={"type": "connector", "id": context_id},
            ),
            _step(
                "step-2",
                "Draft integration adjustment",
                "Prepare a safe configuration update without execution.",
                "draft_connector_update",
                environment,
                [f"connector.{connector_type}", "policy.guardrails"],
                approval_required=False,
                admin_required=True,
                executable=False,
                draft_only=True,
                confirmation_required=False,
            ),
        ]
        guardrail_admin.append("Admin required for integration edits")

    elif context_type == "source":
        source = get_source(client, org_id, context_id, environment_name=environment)
        if not source:
            raise ValueError("Source not found")
        source_title = (source or {}).get("title") or "source"
        steps = [
            _step(
                "step-1",
                "Review source freshness",
                f"Check ingestion status for {source_title}.",
                "review_source",
                environment,
                ["source.summary", "ingest.jobs"],
                approval_required=False,
                admin_required=False,
                executable=False,
                draft_only=True,
                confirmation_required=False,
                linked_entity={"type": "source", "id": context_id},
            ),
            _step(
                "step-2",
                "Draft re-ingest request",
                "Prepare a controlled ingest job with confirmation.",
                "draft_ingest",
                environment,
                ["source.summary", "policy.guardrails"],
                approval_required=False,
                admin_required=True,
                executable=True,
                draft_only=False,
                confirmation_required=True,
            ),
        ]
        guardrail_admin.append("Admin required for ingest changes")
        guardrail_exec.append("Execution requires explicit confirmation")

    if not guardrail_approvals:
        guardrail_approvals.append("Approval requirements depend on policy")
    if not guardrail_admin:
        guardrail_admin.append("Admin restrictions enforced per role")
    if not guardrail_exec:
        guardrail_exec.append("No auto-execution. Confirmation required for any action.")

    return {
        "plan_id": str(uuid4()),
        "title": plan_title,
        "summary": plan_summary,
        "steps": steps,
        "guardrails": {
            "environment": environment,
            "approval_requirements": guardrail_approvals,
            "admin_restrictions": guardrail_admin,
            "execution_restrictions": guardrail_exec,
        },
    }
