"""G1 — Compile scoped Intelligence context for Cognitive Runtime (intelligence_hub)."""
from __future__ import annotations

import re

from app.schemas.intelligence_projection import AssistantVisualization, IntelligenceSnapshot


def _mentions_agents(question: str) -> bool:
    q = question.lower()
    return bool(re.search(r"\bagent(s)?\b", q)) or "currently active" in q


def _mentions_predictions(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in ("predict", "attention", "risk", "warning", "oauth"))


def _mentions_learning(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in ("learn", "learned", "pattern", "insight"))


def compile_intelligence_context_for_query(
    snapshot: IntelligenceSnapshot,
    question: str,
) -> tuple[str, AssistantVisualization | None]:
    """Return markdown context block + optional visualization intent for the query."""
    sections: list[str] = [
        "CANONICAL INTELLIGENCE STATE (authoritative for this org; do not contradict):",
        f"Generated: {snapshot.generatedAt} | Window: {snapshot.timeWindowHours}h",
    ]
    visualization: AssistantVisualization | None = None

    if _mentions_agents(question):
        active = [a for a in snapshot.agents if a.isConfiguredActive]
        running = [a for a in snapshot.agents if a.isCurrentlyRunning]
        sections.append("CONFIGURED ACTIVE AGENTS (roster status permits work):")
        if not active:
            sections.append("- None configured active in canonical roster.")
        else:
            for agent in active:
                run_note = " [currently running]" if agent.isCurrentlyRunning else ""
                sections.append(
                    f"- {agent.businessLabel} ({agent.department or 'General'}) — "
                    f"status={agent.configuredStatus}{run_note}"
                )
        sections.append(
            f"Counts: configuredActive={len(active)}, currentlyRunning={len(running)}, "
            f"concurrentSwarmRuns={snapshot.metrics.execution.get('concurrentSwarmRuns', 0)}"
        )
        sections.append(
            "IMPORTANT: 'configured active' ≠ 'currently running'. "
            "Answer using this canonical roster — do NOT say agent status is unavailable."
        )
        visualization = AssistantVisualization(
            lens="acts",
            highlightNodeIds=[f"agent:{a.id}" for a in active],
            dimNodeIds=[
                f"agent:{a.id}" for a in snapshot.agents if not a.isConfiguredActive
            ],
            focusNodeIds=[f"agent:{a.id}" for a in active[:8]],
            timeWindowHours=snapshot.timeWindowHours,
        )

    elif _mentions_predictions(question):
        preds = snapshot.predictions[:8]
        sections.append("ACTIVE PREDICTIONS (deduplicated):")
        if not preds:
            sections.append("- No scoped predictions in canonical state.")
        else:
            for p in preds:
                conf = f"{round(p.confidence * 100)}%" if p.confidence is not None else "unknown"
                sections.append(f"- {p.businessStatement} (confidence={conf}, dept={p.department or '—'})")
        visualization = AssistantVisualization(
            lens="predicts",
            highlightNodeIds=[f"prediction:{p.id}" for p in preds],
            focusNodeIds=[f"prediction:{p.id}" for p in preds[:4]],
            timeWindowHours=snapshot.timeWindowHours,
        )

    elif _mentions_learning(question):
        sections.append("RECENT BUSINESS LEARNING (not platform telemetry):")
        if not snapshot.learnings:
            sections.append("- No validated business learning insights yet in canonical state.")
        else:
            for insight in snapshot.learnings[:5]:
                sections.append(f"- {insight.businessStatement}")
        visualization = AssistantVisualization(lens="learns", timeWindowHours=snapshot.timeWindowHours)

    else:
        sections.append("Summary metrics:")
        m = snapshot.metrics
        sections.append(
            f"Entities={m.knowledge.get('knownEntities')}, "
            f"ActivePredictions={m.predictions.get('activePredictions')}, "
            f"ConfiguredActiveAgents={m.execution.get('configuredActiveAgents')}, "
            f"CurrentlyRunningAgents={m.execution.get('currentlyRunningAgents')}"
        )

    return "\n".join(sections), visualization


def _is_running_agent_status_question(question: str) -> bool:
    q = question.lower()
    patterns = (
        r"what agents?\s+(are\s+)?(currently\s+)?running",
        r"which agents?\s+(are\s+)?(currently\s+)?running",
        r"agents?\s+(that are\s+)?(currently\s+)?running",
        r"running agents?",
    )
    return any(re.search(p, q) for p in patterns)


def _is_active_agent_status_question(question: str) -> bool:
    q = question.lower()
    if _is_running_agent_status_question(q):
        return False
    patterns = (
        r"what agents?\s+(are\s+)?(currently\s+)?active",
        r"which agents?\s+(are\s+)?(currently\s+)?active",
        r"agents?\s+(that are\s+)?(currently\s+)?active",
        r"active agents?",
    )
    return any(re.search(p, q) for p in patterns) or (
        "currently active" in q and bool(re.search(r"\bagent", q))
    )


def active_agent_trust_answer(snapshot: IntelligenceSnapshot) -> str:
    """Deterministic summary for regression / fast-path answers."""
    active = [a for a in snapshot.agents if a.isConfiguredActive]
    if not active:
        return "No agents are configured active in your organization right now."
    names = ", ".join(a.businessLabel for a in active[:8])
    extra = len(active) - 8
    suffix = f" and {extra} more" if extra > 0 else ""
    depts = sorted({a.department for a in active if a.department})
    dept_note = f" across {len(depts)} department{'s' if len(depts) != 1 else ''}" if depts else ""
    return (
        f"{len(active)} agent{'s are' if len(active) != 1 else ' is'} configured active{dept_note}: "
        f"{names}{suffix}."
    )


def running_agent_trust_answer(snapshot: IntelligenceSnapshot) -> str:
    """Deterministic answer for currently-running swarm agents."""
    running = [a for a in snapshot.agents if a.isCurrentlyRunning]
    configured = sum(1 for a in snapshot.agents if a.isConfiguredActive)
    if not running:
        if configured:
            return (
                f"No agents are currently running. {configured} agent"
                f"{'s are' if configured != 1 else ' is'} configured active but idle in swarm execution."
            )
        return "No agents are currently running."
    names = ", ".join(a.businessLabel for a in running[:8])
    extra = len(running) - 8
    suffix = f" and {extra} more" if extra > 0 else ""
    return (
        f"{len(running)} agent{'s are' if len(running) != 1 else ' is'} currently running: "
        f"{names}{suffix}."
    )


def _is_predictions_attention_question(question: str) -> bool:
    q = question.lower()
    if not _mentions_predictions(question):
        return False
    return any(
        phrase in q
        for phrase in (
            "need attention",
            "needs attention",
            "watch",
            "priority",
            "what predictions",
            "which predictions",
        )
    )


def _is_learning_recent_question(question: str) -> bool:
    q = question.lower()
    return _mentions_learning(question) and any(
        phrase in q for phrase in ("recent", "recently", "what has", "what have", "learned")
    )


def _is_current_activity_question(question: str) -> bool:
    q = question.lower()
    return any(
        phrase in q
        for phrase in (
            "doing right now",
            "doing now",
            "happening now",
            "what is gravitre doing",
            "what's gravitre doing",
        )
    )


def prediction_trust_answer(snapshot: IntelligenceSnapshot) -> str:
    """Deterministic answer for prediction attention queries."""
    preds = snapshot.predictions
    if not preds:
        return "No active predictions in canonical intelligence state right now."
    needing_evidence = [
        p for p in preds if "UNSCOPED_PREDICTION" in p.qualityFlags or not p.evidence
    ]
    high_priority = [p for p in preds if (p.confidence or 0) >= 0.65]
    focus = needing_evidence or high_priority or preds
    statements = [p.businessStatement for p in focus[:6]]
    joined = "; ".join(statements)
    extra = len(focus) - len(statements)
    suffix = f" (+{extra} more)" if extra > 0 else ""
    metric_count = snapshot.metrics.predictions.get("activePredictions", len(preds))
    return (
        f"{metric_count} deduped prediction{'s' if metric_count != 1 else ''} in canonical state. "
        f"Top items needing attention: {joined}{suffix}."
    )


def learning_trust_answer(snapshot: IntelligenceSnapshot) -> str:
    """Deterministic answer for recent business learning queries."""
    if not snapshot.learnings:
        return (
            "No validated business learning insights in canonical intelligence state yet. "
            "Platform telemetry and model readiness are not business learning."
        )
    statements = [insight.businessStatement for insight in snapshot.learnings[:5]]
    joined = "; ".join(statements)
    count = snapshot.metrics.learning.get("recentLearnings", len(snapshot.learnings))
    return (
        f"{count} recent business learning insight{'s' if count != 1 else ''}: {joined}."
    )


def current_activity_trust_answer(snapshot: IntelligenceSnapshot) -> str:
    """Distinguish configured-active agents from currently-running execution."""
    configured = [a for a in snapshot.agents if a.isConfiguredActive]
    running = [a for a in snapshot.agents if a.isCurrentlyRunning]
    exec_metrics = snapshot.metrics.execution
    running_workflows = int(exec_metrics.get("runningWorkflows") or 0)
    swarm_runs = int(exec_metrics.get("concurrentSwarmRuns") or 0)
    parts: list[str] = []
    if running:
        names = ", ".join(a.businessLabel for a in running[:4])
        parts.append(
            f"{len(running)} agent{'s' if len(running) != 1 else ''} currently running ({names})"
        )
    else:
        parts.append("No agents are currently running in swarm execution")
    if configured:
        parts.append(
            f"{len(configured)} agent{'s' if len(configured) != 1 else ''} configured active"
        )
    if running_workflows:
        parts.append(f"{running_workflows} workflow{'s' if running_workflows != 1 else ''} executing")
    if swarm_runs:
        parts.append(f"{swarm_runs} concurrent swarm run{'s' if swarm_runs != 1 else ''}")
    return ". ".join(parts) + "."


# Permanent regression guard — prod once returned these while map showed active agents.
FORBIDDEN_UNAVAILABLE_AGENT_PHRASES: tuple[str, ...] = (
    "don't have the active-agent list",
    "don't have the current agent status",
    "agent status is unavailable",
    "need to fetch the current agent statuses",
    "i don't have the active-agent list yet",
)


def resolve_intelligence_hub_deterministic_answer(
    snapshot: IntelligenceSnapshot,
    question: str,
) -> str | None:
    """Return a canonical answer for intelligence_hub trust queries."""
    if _is_running_agent_status_question(question):
        return running_agent_trust_answer(snapshot)
    if _is_active_agent_status_question(question):
        return active_agent_trust_answer(snapshot)
    if _is_predictions_attention_question(question):
        return prediction_trust_answer(snapshot)
    if _is_learning_recent_question(question):
        return learning_trust_answer(snapshot)
    if _is_current_activity_question(question):
        return current_activity_trust_answer(snapshot)
    return None
