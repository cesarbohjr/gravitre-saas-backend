"""P0 autonomous goal -> executable workflow compiler: bounded sales reference slice.

This is not a second workflow runner. It emits the exact canvas graph and
workflow definition consumed by Gravitre's existing builder/runtime. Running
and persisting the compiled plan must use the existing tenant-scoped workflow
routers, approval enforcement, durable execution, and outcome finalizer.

Initial scope deliberately read-only: no invented capabilities, no inferred
write approval, no fabricated diagnosis or revenue forecast.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.services.connector_execution_matrix import (
    ConnectorActionMatrixEntry,
    build_connector_execution_matrix,
)
from app.workflows.builder_sync import _node_to_step
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.graph_model import build_execution_graph, validate_execution_graph
from app.workflows.schema import validate_definition

_SALES_OBJECTIVES = (
    "increase sales", "grow sales", "increase revenue", "grow revenue",
    "improve sales", "boost sales", "more sales", "sales growth",
)
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
        }


def _sales_intent(goal: str) -> bool:
    text = " ".join(str(goal or "").lower().strip().split())
    return any(phrase in text for phrase in _SALES_OBJECTIVES)


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
) -> GoalPlan:
    """Build a validated **read-only** sales diagnostics graph.

    The action catalog is global implementation evidence; connections are
    supplied by the authenticated tenant resolver and MUST NOT be inferred
    from the model's prompt. A missing connection produces a blocked plan,
    not a deceptive executable graph or silent fallback to all tools.
    """
    if not _sales_intent(goal):
        raise GoalCompilationBlocked("unsupported_goal: sales-growth slice only")
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
            config.update({"limit": 25})
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


async def compile_sales_growth_for_org(
    *,
    org_id: str,
    goal: str,
    settings: Any,
    installed_plays: Iterable[dict[str, Any]] = (),
    environment_name: str | None = None,
) -> GoalPlan:
    """Resolve the actual tenant's connectors and agent policy before compiling.

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
