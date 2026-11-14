"""Bounded sales diagnostic recipe for the EXISTING workflow builder and runtime.

This is not a second workflow runner. It emits the exact canvas graph and
workflow definition consumed by Gravitre's existing builder/runtime. Running
and persisting the compiled plan must use the existing tenant-scoped workflow
routers, approval enforcement, durable execution, and outcome finalizer.

Initial scope deliberately read-only: no invented capabilities, no inferred
write approval, no fabricated diagnosis or revenue forecast.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

from app.services.connector_execution_matrix import (
    ConnectorActionMatrixEntry,
    build_connector_execution_matrix,
)
from app.workflows.builder_sync import _node_to_step
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.graph_model import build_execution_graph, validate_execution_graph
from app.workflows.schema import validate_definition

# Read the registered action catalog. Never synthesize an action identifier.
_READ_PRIORITIES = (
    ("hubspot", ("deal", "search"), "Inspect sales pipeline"),
    ("hubspot", ("contact", "search"), "Inspect lead coverage"),
    ("salesforce", ("opportunit",), "Inspect CRM opportunities"),
    ("pipedrive", ("deal",), "Inspect pipeline"),
    ("google_analytics", ("report",), "Inspect acquisition and conversion"),
)
_MAX_STEPS = 3
# Only actions with verified parameter bindings may be dispatched by this
# reference compiler. All other cataloged actions remain future candidates.
_BOUND_READ_ACTIONS = frozenset({
    "hubspot.deals.search",
    "hubspot.contacts.search",
})


class GoalCompilationBlocked(ValueError):
    """A plan cannot be compiled without executable, scoped read evidence."""


@dataclass(frozen=True)
class GoalPlan:
    objective: str
    goal_text: str
    department: str
    status: str
    graph: dict[str, Any]
    workflow_definition: dict[str, Any]
    capabilities: tuple[str, ...]
    missing_connections: tuple[str, ...]
    selected_play: str | None
    selected_workflow_id: str | None
    agent_persona: str | None
    required_external_approval: bool
    observation_status: str
    diagnostic_evidence: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "goal_text": self.goal_text,
            "department": self.department,
            "status": self.status,
            "graph": self.graph,
            "workflow_definition": self.workflow_definition,
            "capabilities": list(self.capabilities),
            "missing_connections": list(self.missing_connections),
            "selected_play": self.selected_play,
            "selected_workflow_id": self.selected_workflow_id,
            "agent_persona": self.agent_persona,
            "required_external_approval": self.required_external_approval,
            "observation_status": self.observation_status,
            "diagnostic_evidence": self.diagnostic_evidence,
        }


def _pick_reads(
    entries: Iterable[ConnectorActionMatrixEntry],
    connected: set[str],
) -> tuple[list[ConnectorActionMatrixEntry], set[str]]:
    eligible = [
        e for e in entries
        if e.connector_id.lower() in connected
        and e.kind == "read"
        and e.action_key in _BOUND_READ_ACTIONS
        and e.chat_executable
        and e.invoke_tool_handler
        and e.implementation_status == "executable"
    ]
    used: set[str] = set()
    picks: list[ConnectorActionMatrixEntry] = []
    for vendor, terms, _purpose in _READ_PRIORITIES:
        match = next((
            entry for entry in eligible
            if entry.connector_id.lower() == vendor
            and any(term in entry.action_key.lower() for term in terms)
            and entry.action_key not in used
        ), None)
        if match is not None:
            picks.append(match)
            used.add(match.action_key)
        if len(picks) >= _MAX_STEPS:
            break
    return picks, used


def compile_sales_growth_goal(
    *,
    goal: str,
    connected_integrations: Iterable[str],
    action_entries: Iterable[ConnectorActionMatrixEntry] | None = None,
    installed_plays: Iterable[dict[str, Any]] = (),
    agent_selection: dict[str, Any] | None = None,
    recognized_objective: str | None = None,
) -> GoalPlan:
    """Build a validated **read-only** sales diagnostics graph.

    The action catalog is global implementation evidence; connections are
    supplied by the authenticated tenant resolver and MUST NOT be inferred
    from the model's prompt. A missing connection produces a blocked plan,
    not a deceptive executable graph or silent fallback to all tools.
    """
    # Semantic classification belongs to GoalService. This recipe never
    # attempts to infer intent using keywords or its own model.
    if recognized_objective != "increase_sales":
        raise GoalCompilationBlocked("sales_recipe_requires_verified_semantic_objective")
    connected = {str(c).strip().lower() for c in connected_integrations if str(c).strip()}
    catalog = tuple(action_entries if action_entries is not None else build_connector_execution_matrix())
    chosen, _ = _pick_reads(catalog, connected)
    known = {entry.connector_id.lower() for entry in catalog if entry.kind == "read"
             and entry.chat_executable and entry.invoke_tool_handler}
    missing = tuple(sorted({vendor for vendor, _, _ in _READ_PRIORITIES
                            if vendor in known and vendor not in connected}))
    if not chosen:
        # Never pretend a workflow is executable in a tenant with no read capability.
        raise GoalCompilationBlocked(
            "no_connected_executable_sales_read: connect and authorize a supported CRM/analytics source"
        )

    # Play selection is a hint only. An actual existing installation+workflow must
    # be supplied by the authorized tenant lookup. Never manufacture Play IDs.
    selected_play: str | None = None
    selected_workflow_id: str | None = None
    for play in installed_plays:
        if (play.get("status") == "ready" and play.get("department") == "sales"
                and play.get("play_key") and play.get("workflow_id")
                and play.get("installed") is True):
            selected_play = str(play["play_key"])
            selected_workflow_id = str(play["workflow_id"])
            break

    nodes: list[dict[str, Any]] = [{
        "id": "sales-goal-source", "node_type": "source",
        "name": "Sales growth objective",
        "position": {"x": 0, "y": 80},
        "config": {"goal": "increase_sales"},
    }]
    edges: list[dict[str, Any]] = []
    previous = "sales-goal-source"
    for idx, action in enumerate(chosen, start=1):
        node_id = f"sales-evidence-{idx}"
        # Contact search supports list_all in the existing chat tool adapter.
        # Other provider actions need typed input binding before live dispatch;
        # avoid fabricating an apparently ready query for an unknown schema.
        config = {"action": action.action_key}
        if action.action_key == "hubspot.contacts.search":
            config.update({"list_all": True, "limit": 10})
        elif action.action_key == "hubspot.deals.search":
            # Ask the actual HubSpot adapter for a bounded paginated census.
            # More than 250 deals produces truncated coverage, not a false KPI.
            config.update({"max_records": 250})
        nodes.append({
            "id": node_id, "node_type": "connector",
            "name": action.display_name,
            "position": {"x": idx * 280, "y": 80},
            "config": config,
            "metadata": {
                "purpose": "read_only_diagnostic",
                "evidence_source": action.connector_id,
            },
        })
        edges.append({"from_node_id": previous, "to_node_id": node_id})
        previous = node_id

    graph_model = build_execution_graph(nodes, edges)
    validate_execution_graph(graph_model)
    steps = [_node_to_step(n, graph_model.nodes_by_id, edges) for n in nodes[1:]]
    if any(step is None or step.get("type") != "invoke_tool" for step in steps):
        raise GoalCompilationBlocked("non_executable_canvas_node")
    definition = validate_definition({
        "schema_version": SCHEMA_VERSION,
        "steps": steps,
    })
    persona = (agent_selection or {}).get("persona_key")
    return GoalPlan(
        objective="increase_sales",
        goal_text=goal.strip(),
        department="sales",
        status="READ_DIAGNOSTIC_READY",
        graph={"nodes": nodes, "edges": edges},
        workflow_definition=definition,
        capabilities=tuple(a.action_key for a in chosen),
        missing_connections=missing,
        selected_play=selected_play,
        selected_workflow_id=selected_workflow_id,
        agent_persona=str(persona) if persona else None,
        required_external_approval=False,  # reads only; does NOT authorize future writes
        observation_status="NOT_RUN",
    )


def verified_sales_observations(
    plan: GoalPlan,
    *,
    completed_steps: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Produce execution *status*, not an invented diagnosis or forecast.

    Evidence is accepted only from completed persisted workflow steps matching
    the compiled action identities. Provider contents are not interpreted here.
    """
    actual = {str(step.get("step_id") or step.get("id")): step
              for step in completed_steps}
    matched: list[dict[str, Any]] = []
    for step in plan.workflow_definition["steps"]:
        observation = actual.get(step["id"])
        if observation is None or observation.get("status") != "completed":
            return {"status": "INCOMPLETE", "verified_actions": matched,
                    "business_outcome": "NOT_MEASURED"}
        output = observation.get("output_snapshot")
        if not isinstance(output, dict) or not output:
            return {"status": "UNVERIFIED", "verified_actions": matched,
                    "business_outcome": "NOT_MEASURED"}
        matched.append({"step_id": step["id"], "action": step["config"]["action"],
                        "status": "completed", "observed": True})
    return {"status": "DIAGNOSTIC_READS_OBSERVED", "verified_actions": matched,
            "business_outcome": "NOT_MEASURED"}



def diagnose_persisted_sales_reads(
    plan: GoalPlan,
    *,
    org_id: str,
    run_id: str,
    completed_steps: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Extract *bounded observations* from actual persisted HubSpot reads.

    Workflows already invoke tenant-authorized tools through InvokeToolHandler.
    This consumes their persisted step snapshots after execution; it does NOT
    dispatch provider calls, confer authorization, or infer revenue growth.
    Search pages without authoritative complete coverage cannot yield totals.
    """
    from datetime import datetime, timezone
    from app.services.goal_service import BusinessMetricEvidence

    if not org_id or not run_id:
        raise GoalCompilationBlocked("authenticated_org_and_persisted_run_required")
    expected = {
        step["id"]: str(step["config"]["action"])
        for step in plan.workflow_definition["steps"]
        if step.get("type") == "invoke_tool"
    }
    actual = list(completed_steps)
    # Reject duplicated step identities; otherwise a later forged row could
    # overwrite an earlier persisted record in a dict comprehension.
    step_ids = [str(step.get("step_id") or step.get("id") or "") for step in actual]
    if len(step_ids) != len(set(step_ids)):
        raise GoalCompilationBlocked("duplicate_persisted_step_identity")
    facts: list[dict[str, Any]] = []
    metrics: list[BusinessMetricEvidence] = []
    for step in actual:
        if step.get("org_id") != org_id or str(step.get("run_id")) != run_id:
            raise GoalCompilationBlocked("persisted_step_tenant_or_run_mismatch")
        step_id = str(step.get("step_id") or step.get("id") or "")
        action = expected.get(step_id)
        if not action:
            continue
        if step.get("status") != "completed":
            facts.append({"step_id": step_id, "status": "INCOMPLETE"})
            continue
        output = step.get("output_snapshot")
        if not isinstance(output, dict) or output.get("simulated") is True:
            facts.append({"step_id": step_id, "status": "UNVERIFIED"})
            continue
        # The registered action is the compiler authority; also confirm the
        # persisted provider-reported action matches if one is supplied.
        reported = str(output.get("action") or output.get("invoke_action") or action)
        if reported != action:
            facts.append({"step_id": step_id, "status": "ACTION_MISMATCH"})
            continue
        if output.get("success") is False:
            facts.append({"step_id": step_id, "status": "PROVIDER_ERROR"})
            continue
        if action != "hubspot.deals.search":
            facts.append({"step_id": step_id, "status": "UNSUPPORTED_METRIC_EXTRACTION"})
            continue
        payload = output.get("data") if isinstance(output.get("data"), dict) else output
        rows = payload.get("results")
        coverage = payload.get("coverage")
        # Only a documented *complete* paginated census may assert a total.
        # A default limited search is informative, but not a pipeline total.
        if not isinstance(rows, list) or not isinstance(coverage, dict) or coverage.get("complete") is not True:
            facts.append({"step_id": step_id, "status": "PARTIAL_READ_NO_TOTAL"})
            continue
        if coverage.get("returned") != len(rows) or any(not isinstance(row, dict) for row in rows):
            facts.append({"step_id": step_id, "status": "INVALID_PROVIDER_COVERAGE"})
            continue
        reported_total = coverage.get("total_reported")
        if type(reported_total) is not int or reported_total != len(rows):
            facts.append({"step_id": step_id, "status": "INCONSISTENT_PROVIDER_TOTAL"})
            continue
        completed_at = step.get("completed_at")
        try:
            observed_at = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            if observed_at.tzinfo is None:
                raise ValueError("naive")
        except (TypeError, ValueError):
            facts.append({"step_id": step_id, "status": "MISSING_PERSISTED_TIMESTAMP"})
            continue
        kind = "deals" if action == "hubspot.deals.search" else "contacts"
        metric = BusinessMetricEvidence(
            org_id=org_id, system="hubspot",
            source_record_id=f"{run_id}:{step_id}:{kind}:complete-census",
            metric_key=f"{kind}_record_count", unit="records",
            value=float(len(rows)), observed_at=observed_at.astimezone(timezone.utc),
        )
        metrics.append(metric)
        facts.append({
            "step_id": step_id,
            "status": "COMPLETE_CENSUS_OBSERVED",
            "metric_key": metric.metric_key,
            "value": len(rows),
            "source_record_id": metric.source_record_id,
        })
    # This is a compiler-friendly diagnosis payload, never a forecast or
    # an assertion that an opportunity caused measurable business impact.
    return {
        "status": "OBSERVATIONS_AVAILABLE" if metrics else "INSUFFICIENT_VERIFIED_EVIDENCE",
        "goal": plan.goal_text,
        "org_id": org_id,
        "run_id": run_id,
        "observations": [item.model_dump(mode="json") for item in metrics],
        "findings": facts,
        "hypotheses": [],
        "recommended_writes": [],
        "business_outcome": "NOT_MEASURED",
        "execution_status": "READ_DIAGNOSTIC_ONLY",
    }


def attach_persisted_sales_diagnosis(
    plan: GoalPlan,
    *,
    org_id: str,
    run_id: str,
    completed_steps: Iterable[dict[str, Any]],
) -> GoalPlan:
    """Return a new compiler input with verified *observations*, not effects.

    Preserve the same registered tools, workflow graph, approvals and version;
    a diagnostic cannot silently mutate or extend an executable plan.
    """
    diagnosis = diagnose_persisted_sales_reads(
        plan, org_id=org_id, run_id=run_id, completed_steps=completed_steps,
    )
    if diagnosis["goal"] != plan.goal_text or plan.objective != "increase_sales":
        raise GoalCompilationBlocked("diagnostic_plan_objective_mismatch")
    return replace(
        plan,
        observation_status=diagnosis["status"],
        diagnostic_evidence=diagnosis,
    )


def diagnose_authenticated_sales_run(
    *,
    client: Any,
    org_id: str,
    environment_name: str,
    run_id: str,
) -> dict[str, Any] | None:
    """Read-only, tenant/env-scoped sales diagnosis using persisted run truth.

    The run must already have been executed by the canonical workflow runtime.
    This function never calls a provider or changes goal, workflow or run state.
    A missing run/workflow returns None; invalid provenance fails closed.
    """
    from app.workflows.repository import get_run_with_steps, get_workflow_def

    if not org_id or not environment_name or not run_id:
        raise GoalCompilationBlocked("authenticated_org_environment_and_run_required")
    run = get_run_with_steps(client, org_id, run_id, environment_name)
    if run is None:
        return None
    if run.get("org_id") != org_id or run.get("environment") != environment_name:
        raise GoalCompilationBlocked("run_tenant_or_environment_mismatch")
    if run.get("run_type") != "execute" or run.get("status") != "completed":
        raise GoalCompilationBlocked("completed_canonical_execution_required")
    workflow_id = str(run.get("workflow_id") or "")
    if not workflow_id:
        raise GoalCompilationBlocked("persisted_workflow_identity_required")
    workflow = get_workflow_def(client, org_id, workflow_id)
    if workflow is None:
        return None
    if workflow.get("org_id") != org_id or workflow.get("name") != "Sales growth diagnostic":
        raise GoalCompilationBlocked("not_a_tenant_sales_diagnostic")
    # The canonical workflow contract mirrors nodes/edges but can omit the
    # original goal text. Read that immutable authoring metadata from the
    # tenant-owned workflow_defs row rather than making up an objective.
    authoring = (
        client.table("workflow_defs").select("id,org_id,name,goal")
        .eq("id", workflow_id).eq("org_id", org_id).limit(1).execute()
    )
    original = (authoring.data or [None])[0]
    if not isinstance(original, dict) or original.get("name") != workflow.get("name"):
        raise GoalCompilationBlocked("original_goal_metadata_required")
    goal = str(original.get("goal") or "").strip()
    snapshot = run.get("definition_snapshot")
    if not goal or not isinstance(snapshot, dict):
        raise GoalCompilationBlocked("immutable_sales_plan_snapshot_required")
    steps = snapshot.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 3:
        raise GoalCompilationBlocked("invalid_sales_plan_steps")
    allowed_actions = {"hubspot.deals.search", "hubspot.contacts.search"}
    if any(
        not isinstance(step, dict)
        or step.get("type") != "invoke_tool"
        or not isinstance(step.get("config"), dict)
        or step["config"].get("action") not in allowed_actions
        or not str(step.get("id") or "").strip()
        for step in steps
    ):
        raise GoalCompilationBlocked("unsupported_sales_plan_action")
    ids = [str(step["id"]) for step in steps]
    if len(set(ids)) != len(ids):
        raise GoalCompilationBlocked("duplicate_sales_plan_step")
    # A run's immutable definition is the only source for step identity:
    # a modified workflow draft must not retroactively redefine its actions.
    plan = GoalPlan(
        objective="increase_sales", goal_text=goal, department="sales",
        status="READ_DIAGNOSTIC_COMPLETED",
        graph={}, workflow_definition={"steps": steps},
        capabilities=tuple(str(step["config"]["action"]) for step in steps),
        missing_connections=(), selected_play=None, selected_workflow_id=workflow_id,
        agent_persona=None, required_external_approval=False,
        observation_status="NOT_ASSESSED",
    )
    persisted_steps = run.get("steps")
    if not isinstance(persisted_steps, list):
        raise GoalCompilationBlocked("persisted_steps_required")
    return {
        "workflowId": workflow_id,
        "environment": environment_name,
        "runStatus": "completed",
        "diagnosis": attach_persisted_sales_diagnosis(
            plan, org_id=org_id, run_id=run_id, completed_steps=persisted_steps,
        ).diagnostic_evidence,
    }


async def compile_sales_growth_for_org(
    *,
    org_id: str,
    goal: str,
    settings: Any,
    installed_plays: Iterable[dict[str, Any]] = (),
    environment_name: str | None = None,
    recognized_objective: str | None = None,
) -> GoalPlan:
    """Read existing tenant capability and agent policy before compiling.

    The caller must already have authenticated and authorized this org_id.
    This function never manufactures a Play installation, grants an agent role
    or calls a provider. Persist/execute only through existing workflow routes.
    """
    if not org_id or not org_id.strip():
        raise GoalCompilationBlocked("authenticated_org_required")
    from app.services.agent_selector import AgentSelector

    selector = AgentSelector(settings=settings)
    classification = {
        "department": "sales",
        "intent": "sales_task",
        "requires_action": True,
    }
    selected_agent = await selector.select(org_id, classification)
    connected = await selector._get_connected(org_id)
    # Discover only genuinely installed and workflow-bound tenant Plays.
    # This is an advisory candidate, not execution authorization.
    plays = tuple(installed_plays)
    if not plays and environment_name is not None:
        plays = tuple(discover_installed_sales_plays(
            org_id=org_id, settings=settings, environment_name=environment_name,
        ))
    return compile_sales_growth_goal(
        goal=goal, connected_integrations=connected,
        installed_plays=plays, agent_selection=selected_agent,
        recognized_objective=recognized_objective,
    )


def discover_installed_sales_plays(
    *, org_id: str, settings: Any, environment_name: str,
) -> list[dict[str, Any]]:
    """Read tenant-owned Play installations and existing workflow bindings.

    No catalog template is promoted to an executable Play without a genuine
    installation and a bound workflow in the same organization/environment.
    This does not override Play readiness checks at dispatch time.
    """
    from app.workflows.repository import get_supabase_client
    from app.plays.workflow_bindings import list_all_play_workflow_bindings

    if not org_id or not environment_name:
        return []
    client = get_supabase_client(settings)
    installations = (
        client.table("play_installations").select("play_key,status")
        .eq("org_id", org_id).eq("environment_name", environment_name)
        .execute().data or []
    )
    bindings = list_all_play_workflow_bindings(client, org_id)
    sales_keys = {
        "qualified-prospecting", "revenue-leak-hunter",
        "revenue-recovery", "marketing-performance",
    }
    candidates: list[dict[str, Any]] = []
    for installation in installations:
        key = str(installation.get("play_key") or "").lower()
        if key not in sales_keys or installation.get("status") != "ready":
            continue
        for binding in bindings.get(key, []):
            workflow_id = str(binding.get("workflowId") or "")
            if not workflow_id or binding.get("status") in {"archived", "deleted"}:
                continue
            candidates.append({
                "play_key": key, "workflow_id": workflow_id,
                "department": "sales", "status": "ready",
                "installed": True,
            })
            break
    return candidates
