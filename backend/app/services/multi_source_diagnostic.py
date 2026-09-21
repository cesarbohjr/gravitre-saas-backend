"""2.0-G multi-source diagnostic — hypothesis/evidence plan steps, no invented cause."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.capability_ontology.recipe_resolver import resolve_recipe
from app.services.execution_plan_service import ExecutionPlan, ExecutionObservation, ExecutionStep

_WHY = re.compile(r"\bwhy\b", re.I)
_CAUSAL = re.compile(
    r"(?is)\b(what caused|what caused it|causal|because of|driven by|due to)\b"
)
_PIPELINE = re.compile(r"\b(pipeline|deals?|crm)\b", re.I)
_AR = re.compile(r"\b(receivable|invoice|who owes|overdue|AR)\b", re.I)
_SUPPORT = re.compile(r"\b(tickets?|support queue|zendesk|issue trends?)\b", re.I)
_CROSS = re.compile(
    r"(?is)\b(deals?|pipeline|crm).{0,80}\b(tickets?|support|zendesk)\b|"
    r"\b(tickets?|support|zendesk).{0,80}\b(deals?|pipeline|crm)\b"
)

_DIAGNOSTICS: tuple[tuple[str, str, str], ...] = (
    ("sales.pipeline.health", "crm.deals.read", "Why the pipeline moved"),
    ("finance.receivables.overdue", "finance.invoices.read", "Why receivables look overdue"),
    ("support.issue_trends", "support.tickets.read", "Why support volume changed"),
)

INSUFFICIENT_EVIDENCE = (
    "I don't have enough live system evidence to explain that. "
    "I won't guess a cause from knowledge or the model."
)


def match_diagnostic_recipe(message: str) -> str | None:
    text = message or ""
    if _CROSS.search(text):
        return "sales.pipeline.health"
    if not _WHY.search(text) and not _CAUSAL.search(text):
        return None
    if _PIPELINE.search(text) and (_WHY.search(text) or _CAUSAL.search(text)):
        return "sales.pipeline.health"
    if _AR.search(text) and (_WHY.search(text) or _CAUSAL.search(text)):
        return "finance.receivables.overdue"
    if _SUPPORT.search(text) and (_WHY.search(text) or _CAUSAL.search(text)):
        return "support.issue_trends"
    return None


def build_multi_source_diagnostic_plan(
    message: str,
    *,
    connected_integrations: list[str] | None,
    turn_id: str | None = None,
    conversation_id: str | None = None,
) -> ExecutionPlan | None:
    recipe_id = match_diagnostic_recipe(message)
    if not recipe_id:
        return None
    connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
    resolved = resolve_recipe(recipe_id, connected_integrations=connected, query=message)
    evidence_steps: list[ExecutionStep] = []
    if resolved is not None:
        for step in resolved.steps:
            if step.step_type != "invoke_tool" or step.optional:
                continue
            if not step.resolved_action:
                continue
            evidence_steps.append(
                ExecutionStep(
                    step_id=f"evidence_{step.step_id}",
                    title=step.name,
                    kind="evidence",
                    connector_id=step.resolved_vendor,
                    capability_id=step.capability_id,
                    action_key=step.resolved_action,
                    meta={"role": "evidence", "recipe_id": recipe_id},
                )
            )
    if recipe_id == "sales.pipeline.health" and "google_analytics" in connected:
        evidence_steps.append(
            ExecutionStep(
                step_id="evidence_traffic",
                title="Read website traffic as a demand check",
                kind="evidence",
                connector_id="google_analytics",
                capability_id="analytics.traffic_overview",
                action_key="google_analytics.reports.run",
                meta={"role": "evidence", "optional": True},
            )
        )
    if _CROSS.search(message or "") and "zendesk" in connected:
        if not any(str(s.connector_id or "") == "zendesk" for s in evidence_steps):
            evidence_steps.append(
                ExecutionStep(
                    step_id="evidence_support_tickets",
                    title="Read support tickets for the same customers",
                    kind="evidence",
                    connector_id="zendesk",
                    capability_id="support.issue_trends",
                    action_key="zendesk.tickets.list",
                    meta={"role": "evidence", "recipe_id": "support.issue_trends"},
                )
            )

    label = next((row[2] for row in _DIAGNOSTICS if row[0] == recipe_id), "Diagnostic")
    steps = [
        ExecutionStep(
            step_id="hypothesis_primary",
            title=f"{label}: volume, conversion, or coverage",
            kind="hypothesis",
            capability_id=recipe_id,
            meta={"role": "hypothesis"},
        ),
        *evidence_steps,
        ExecutionStep(
            step_id="compose_diagnostic",
            title="Conclude from evidence or declare insufficient",
            kind="compose",
            capability_id=recipe_id,
            meta={"insufficient_if_no_evidence": True},
        ),
    ]
    plan = ExecutionPlan(
        plan_id=str(uuid4()),
        summary=label,
        objective=str(message or "")[:240],
        steps=steps,
        source="multi_source_diagnostic",
        capability_id=recipe_id,
        execution_strategy="PARALLEL",
        turn_id=turn_id,
        conversation_id=conversation_id,
    )
    from app.services.reasoning_evidence_pipeline import apply_join_and_labels_to_plan

    return apply_join_and_labels_to_plan(plan)


def conclude_diagnostic(
    plan: ExecutionPlan,
    observations: list[ExecutionObservation] | list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Honest conclusion: observed facts only; never invent a causal story."""
    evidence_ids = {s.step_id for s in plan.steps if s.kind == "evidence"}
    live: list[str] = []
    for raw in observations or []:
        if isinstance(raw, ExecutionObservation):
            step_id = raw.step_id
            success = raw.success
            summary = raw.summary
        elif isinstance(raw, dict):
            step_id = str(raw.get("step_id") or "")
            success = bool(raw.get("success"))
            summary = str(raw.get("summary") or "")
        else:
            continue
        if step_id in evidence_ids and success:
            live.append(summary.strip() or step_id)
    from app.services.reasoning_evidence_pipeline import label_claim

    if not live:
        return {
            "sufficient": False,
            "status": "insufficient_evidence",
            "message": INSUFFICIENT_EVIDENCE,
            "observed": [],
            "labels": [
                {"text": INSUFFICIENT_EVIDENCE, "label": label_claim(insufficient_evidence=True)},
            ],
        }
    observed = "; ".join(live[:5])
    fact = f"Live reads returned: {observed}."
    inference = "That is not a causal explanation of why the metric moved."
    return {
        "sufficient": True,
        "status": "observed_only",
        "message": f"{fact} {inference}",
        "observed": live,
        "labels": [
            {"text": fact, "label": label_claim(live_observation=True)},
            {"text": inference, "label": label_claim(live_observation=True, causal=True)},
        ],
    }
