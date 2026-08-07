"""Design-time workflow binding validation (typed-contract floor).

Validates ``param_sources`` / ``from_step`` / ``$`` aliases at save and install.
Broken or ambiguous bindings fail with named error codes — never silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.workflows.schema import WorkflowValidationError

# Runtime-injected execute params (not install variables, not step outputs).
KNOWN_RUNTIME_ALIASES = frozenset(
    {
        "hubspot_connector_id",
        "hubspotConnectorId",
        "apollo_connector_id",
        "clay_connector_id",
        "connector_id",
    }
)

# Declared producer output keys for invoke_tool actions (enrichment + common list sync).
# Expand as packs declare more contracts; unknown path → binding.path_unknown.
ACTION_OUTPUT_KEYS: dict[str, frozenset[str]] = {
    "apollo.lists.list": frozenset({"lists", "result_url", "summary", "success", "invoke_action", "integration", "outcome_effect"}),
    "apollo.contacts.search": frozenset(
        {
            "contacts",
            "contact_count",
            "contact_label_ids",
            "entity_ids",
            "contact_ids",
            "primary_contact_id",
            "primary_email",
            "hubspot_contact_properties",
            "records",
            "clay_records",
            "enriched_records",
            "record_count",
            "result_url",
            "summary",
            "success",
            "invoke_action",
            "integration",
            "outcome_effect",
        }
    ),
    "apollo.people.search": frozenset(
        {
            "people",
            "contacts",
            "entity_ids",
            "contact_ids",
            "primary_contact_id",
            "primary_email",
            "hubspot_contact_properties",
            "records",
            "clay_records",
            "enriched_records",
            "record_count",
            "result_url",
            "summary",
            "success",
            "invoke_action",
            "integration",
            "outcome_effect",
        }
    ),
    "apollo.lists.add": frozenset(
        {"added_count", "label_names", "entity_ids", "result_url", "summary", "success", "invoke_action", "integration", "outcome_effect"}
    ),
    "clay.leads.push": frozenset(
        {
            "webhook",
            "table_id",
            "records_sent",
            "records",
            "clay_records",
            "enriched_records",
            "record_count",
            "enterprise_api_available",
            "summary",
            "success",
            "invoke_action",
            "integration",
            "outcome_effect",
        }
    ),
    "clay.workflows.output.get": frozenset(
        {
            "outputs",
            "source",
            "note",
            "records",
            "clay_records",
            "enriched_records",
            "record_count",
            "summary",
            "success",
            "invoke_action",
            "integration",
            "outcome_effect",
        }
    ),
    "clay.crm.sync": frozenset(
        {
            "synced",
            "errors",
            "crm",
            "crm_connector_id",
            "contact_ids",
            "primary_contact_id",
            "contact_id",
            "added_count",
            "summary",
            "success",
            "invoke_action",
            "integration",
            "outcome_effect",
        }
    ),
    "hubspot.lists.add_contact": frozenset(
        {"list_id", "contact_id", "added", "summary", "success", "invoke_action", "integration", "outcome_effect", "result_url", "external_url"}
    ),
}

# Actions without a declared allowlist still pass path checks (unknown producer schema).
# Only actions in ACTION_OUTPUT_KEYS enforce path_unknown.


@dataclass
class BindingError:
    code: str
    message: str
    step_id: str | None = None
    param: str | None = None

    def as_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.step_id:
            row["stepId"] = self.step_id
        if self.param:
            row["param"] = self.param
        return row


@dataclass
class BindingValidationResult:
    errors: list[BindingError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_invalid(self) -> None:
        if self.ok:
            return
        codes = [e.code for e in self.errors]
        summary = "; ".join(f"{e.code}: {e.message}" for e in self.errors[:5])
        if len(self.errors) > 5:
            summary += f" (+{len(self.errors) - 5} more)"
        raise WorkflowValidationError(summary, errors=codes)


def _step_action(step: dict[str, Any]) -> str:
    config = step.get("config") if isinstance(step.get("config"), dict) else {}
    return str(config.get("action") or config.get("tool_action") or "").strip()


def _build_upstream_sets(
    steps: list[dict[str, Any]],
    edges: list[dict[str, Any]] | None,
) -> dict[str, set[str]]:
    """Map step_id → set of ancestor step ids that may bind as from_step producers."""
    step_ids = [str(s["id"]) for s in steps if isinstance(s, dict) and s.get("id")]
    id_set = set(step_ids)
    upstream: dict[str, set[str]] = {sid: set() for sid in step_ids}

    normalized_edges: list[tuple[str, str]] = []
    for edge in edges or []:
        if not isinstance(edge, dict):
            continue
        src = str(
            edge.get("from_node_id")
            or edge.get("fromNodeId")
            or edge.get("from")
            or edge.get("source")
            or ""
        ).strip()
        dst = str(
            edge.get("to_node_id")
            or edge.get("toNodeId")
            or edge.get("to")
            or edge.get("target")
            or ""
        ).strip()
        if src in id_set and dst in id_set:
            normalized_edges.append((src, dst))

    if normalized_edges:
        preds: dict[str, set[str]] = {sid: set() for sid in step_ids}
        for src, dst in normalized_edges:
            preds[dst].add(src)
        # Transitive closure of predecessors.
        for sid in step_ids:
            seen: set[str] = set()
            stack = list(preds.get(sid) or [])
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(preds.get(cur) or [])
            upstream[sid] = seen
        return upstream

    # No edges → sequential step order (marketplace definitions).
    for index, sid in enumerate(step_ids):
        upstream[sid] = set(step_ids[:index])
    return upstream


def _registered_actions() -> set[str]:
    try:
        from app.services.tool_service import list_registered_actions

        return set(list_registered_actions())
    except Exception:  # noqa: BLE001
        return set()


def _validate_from_step_spec(
    *,
    step_id: str,
    param: str,
    spec: dict[str, Any],
    step_ids: set[str],
    upstream: dict[str, set[str]],
    steps_by_id: dict[str, dict[str, Any]],
    errors: list[BindingError],
) -> None:
    producer_id = str(spec.get("from_step") or "").strip()
    if not producer_id:
        errors.append(
            BindingError(
                code="binding.ambiguous",
                message=f"step {step_id!r} param {param!r} has empty from_step",
                step_id=step_id,
                param=param,
            )
        )
        return
    if producer_id not in step_ids:
        errors.append(
            BindingError(
                code="binding.from_step_unknown",
                message=f"step {step_id!r} param {param!r} from_step {producer_id!r} does not exist",
                step_id=step_id,
                param=param,
            )
        )
        return
    if producer_id == step_id:
        errors.append(
            BindingError(
                code="binding.ambiguous",
                message=f"step {step_id!r} param {param!r} cannot bind from itself",
                step_id=step_id,
                param=param,
            )
        )
        return
    if producer_id not in (upstream.get(step_id) or set()):
        errors.append(
            BindingError(
                code="binding.from_step_not_upstream",
                message=(
                    f"step {step_id!r} param {param!r} from_step {producer_id!r} "
                    "is not upstream of this step"
                ),
                step_id=step_id,
                param=param,
            )
        )
        return

    path = spec.get("path")
    if path is None:
        return
    if not isinstance(path, list) or not path:
        errors.append(
            BindingError(
                code="binding.path_empty",
                message=f"step {step_id!r} param {param!r} from_step path must be a non-empty array",
                step_id=step_id,
                param=param,
            )
        )
        return
    if not all(isinstance(p, str) and p.strip() for p in path):
        errors.append(
            BindingError(
                code="binding.path_empty",
                message=f"step {step_id!r} param {param!r} from_step path entries must be non-empty strings",
                step_id=step_id,
                param=param,
            )
        )
        return

    producer = steps_by_id.get(producer_id) or {}
    producer_action = _step_action(producer)
    allow = ACTION_OUTPUT_KEYS.get(producer_action)
    if allow is not None:
        root = str(path[0])
        if root not in allow:
            errors.append(
                BindingError(
                    code="binding.path_unknown",
                    message=(
                        f"step {step_id!r} param {param!r} path {root!r} is not a declared "
                        f"output of {producer_action or producer_id!r}"
                    ),
                    step_id=step_id,
                    param=param,
                )
            )


def _validate_dollar(
    *,
    step_id: str,
    param: str,
    alias: str,
    declared_params: set[str],
    errors: list[BindingError],
) -> None:
    name = alias[1:].strip() if alias.startswith("$") else alias.strip()
    if not name:
        errors.append(
            BindingError(
                code="binding.dollar_unresolved",
                message=f"step {step_id!r} param {param!r} has empty $ alias",
                step_id=step_id,
                param=param,
            )
        )
        return
    if name in declared_params or name in KNOWN_RUNTIME_ALIASES:
        return
    errors.append(
        BindingError(
            code="binding.dollar_unresolved",
            message=(
                f"step {step_id!r} param {param!r} references unresolved run/install "
                f"parameter ${name}"
            ),
            step_id=step_id,
            param=param,
        )
    )


def _iter_binding_specs(config: dict[str, Any]) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for key in ("param_sources", "paramSources"):
        sources = config.get(key)
        if isinstance(sources, dict):
            for param, spec in sources.items():
                out.append((str(param), spec))
    if "message_from_step" in config:
        out.append(("message", config.get("message_from_step")))
    return out


def validate_bindings(
    definition: dict[str, Any],
    *,
    declared_parameters: set[str] | None = None,
    registered_actions: set[str] | None = None,
) -> BindingValidationResult:
    """Validate step bindings. Does not mutate definition."""
    errors: list[BindingError] = []
    steps_raw = definition.get("steps") if isinstance(definition.get("steps"), list) else []
    steps = [s for s in steps_raw if isinstance(s, dict) and s.get("id")]
    if not steps:
        return BindingValidationResult(errors=errors)

    step_ids = {str(s["id"]) for s in steps}
    steps_by_id = {str(s["id"]): s for s in steps}
    graph = definition.get("graph") if isinstance(definition.get("graph"), dict) else {}
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else definition.get("edges")
    if not isinstance(edges, list):
        edges = []
    graph_nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    # Builder saves always embed definition.graph. Empty edges with multiple steps
    # means canvas wiring was dropped (Phase 0 failure mode) — do NOT silently
    # treat that as sequential marketplace order.
    if (
        len(steps) > 1
        and isinstance(graph, dict)
        and ("edges" in graph or graph_nodes)
        and not edges
    ):
        errors.append(
            BindingError(
                code="binding.canvas_graph_disconnected",
                message=(
                    f"definition.graph has {len(graph_nodes) or len(steps)} nodes but zero "
                    "edges — connections appear missing from the persisted graph "
                    "(not a sequential marketplace definition)"
                ),
            )
        )
    upstream = _build_upstream_sets(steps, edges)

    declared = set(declared_parameters or ())
    actions = registered_actions if registered_actions is not None else _registered_actions()

    for step in steps:
        step_id = str(step["id"])
        step_type = str(step.get("type") or "")
        config = step.get("config") if isinstance(step.get("config"), dict) else {}

        if step_type == "invoke_tool" or config.get("action") or config.get("tool_action"):
            action = _step_action(step)
            if not action:
                errors.append(
                    BindingError(
                        code="binding.action_unknown",
                        message=f"step {step_id!r} invoke_tool is missing config.action",
                        step_id=step_id,
                    )
                )
            elif actions and action not in actions:
                errors.append(
                    BindingError(
                        code="binding.action_unknown",
                        message=f"step {step_id!r} action {action!r} is not in the tool catalog",
                        step_id=step_id,
                    )
                )

        for param, spec in _iter_binding_specs(config):
            if isinstance(spec, dict) and ("from_step" in spec or "fromStep" in spec):
                normalized = dict(spec)
                if "fromStep" in normalized and "from_step" not in normalized:
                    normalized["from_step"] = normalized["fromStep"]
                _validate_from_step_spec(
                    step_id=step_id,
                    param=param,
                    spec=normalized,
                    step_ids=step_ids,
                    upstream=upstream,
                    steps_by_id=steps_by_id,
                    errors=errors,
                )
            elif isinstance(spec, str) and spec.startswith("$"):
                _validate_dollar(
                    step_id=step_id,
                    param=param,
                    alias=spec,
                    declared_params=declared,
                    errors=errors,
                )
            # Literals (str/number/bool/list/dict without from_step) are allowed.

    return BindingValidationResult(errors=errors)


def assert_bindings_valid(
    definition: dict[str, Any],
    *,
    declared_parameters: set[str] | None = None,
    registered_actions: set[str] | None = None,
) -> None:
    """Raise WorkflowValidationError with named codes when bindings are invalid."""
    validate_bindings(
        definition,
        declared_parameters=declared_parameters,
        registered_actions=registered_actions,
    ).raise_if_invalid()
