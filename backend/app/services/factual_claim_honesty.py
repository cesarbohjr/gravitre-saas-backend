"""Hard honesty gates for factual claims that require a specific tool result.

If the user asks for run history / recent-run counts and the tools that actually
ran did not return workflow_runs data, the answer must refuse that claim — not
invent a number from agent_status, org-context limits, or moderate-confidence framing.
"""
from __future__ import annotations

import re
from typing import Any

RUN_HISTORY_QUESTION = re.compile(
    r"\b("
    r"workflow\s+runs?|"
    r"runs?\s+have\s+been\s+(ran|run)|"
    r"workflows?\s+have\s+been\s+(ran|run)|"
    r"recent\s+runs?|"
    r"how\s+many\s+runs?|"
    r"execution\s+history|"
    r"run\s+history|"
    r"what\s+workflows\s+have\s+been"
    r")\b",
    re.I,
)

# Numeric / zero claims about recent runs that must be tool-backed.
RUN_COUNT_CLAIM = re.compile(
    r"\b("
    r"\d+\s+recent\s+runs?\b|"
    r"recent\s+runs?\s+(are|is|were|recorded|record)\b|"
    r"0\s+recent\s+runs?\b|"
    r"no\s+recent\s+runs?\b|"
    r"\d+\s+workflows?\s+are\s+configured\b"  # often paired with fabricated run counts from snapshot limits
    r")",
    re.I,
)

WORKFLOW_RUNS_TOOL_NAMES = frozenset(
    {
        "assistant_workflow_runs",
        "workflow_runs",
        "getWorkflowRuns",
        "assistant_analytics",
        "analytics",
        "getAnalytics",
    }
)

RUN_HISTORY_REFUSAL = (
    "I don't have that information — workflow run history was not retrieved for this answer. "
    "I can't report a recent-run count without the workflow runs tool. "
    "Ask again and I'll fetch run history directly (or switch out of Fast mode if needed)."
)

RUN_HISTORY_EXPLANATION_GAP = (
    "Run-history counts were not retrieved. Live tools used for this turn did not include "
    "workflow run data, so no numeric run claim is warranted."
)


def is_run_history_question(query: str) -> bool:
    return bool(RUN_HISTORY_QUESTION.search((query or "").strip()))


def _tool_name(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    return str(
        entry.get("toolName")
        or entry.get("tool_name")
        or entry.get("name")
        or entry.get("tool")
        or entry.get("action")
        or ""
    ).strip()


def _tool_payload(entry: dict[str, Any]) -> dict[str, Any]:
    for key in ("result", "output", "observation", "data"):
        value = entry.get(key)
        if isinstance(value, dict):
            # Nested {success, tool, result: {...}}
            inner = value.get("result")
            if isinstance(inner, dict):
                return inner
            return value
    return entry


def tool_results_include_workflow_runs(
    tool_results: list[dict[str, Any]] | None = None,
    *,
    react_result: Any | None = None,
) -> bool:
    """True when a successful workflow_runs (or analytics) tool result is present."""
    rows: list[dict[str, Any]] = []
    if tool_results:
        rows.extend([r for r in tool_results if isinstance(r, dict)])
    if react_result is not None:
        calls = getattr(react_result, "tool_calls", None)
        if isinstance(calls, list):
            rows.extend([c for c in calls if isinstance(c, dict)])
        as_dict = react_result.to_dict() if hasattr(react_result, "to_dict") else None
        if isinstance(as_dict, dict):
            for key in ("tool_calls", "toolCalls", "trace"):
                block = as_dict.get(key)
                if isinstance(block, list):
                    rows.extend([c for c in block if isinstance(c, dict)])

    for row in rows:
        name = _tool_name(row)
        # Normalize registry / display names
        normalized = name.replace("assistant_", "")
        if name not in WORKFLOW_RUNS_TOOL_NAMES and normalized not in {
            "workflow_runs",
            "analytics",
            "getWorkflowRuns",
            "getAnalytics",
        }:
            # Also accept tool field inside observation
            payload_probe = _tool_payload(row)
            nested_tool = str(payload_probe.get("tool") or "")
            if nested_tool not in WORKFLOW_RUNS_TOOL_NAMES and nested_tool.replace(
                "assistant_", ""
            ) not in {"workflow_runs", "analytics"}:
                continue
        payload = _tool_payload(row)
        if payload.get("error"):
            continue
        if "runs" in payload or "total" in payload or "last7Days" in payload or "counts" in payload:
            return True
        # Explicit success wrapper
        if payload.get("success") is True and (
            isinstance(payload.get("runs"), list) or payload.get("total") is not None
        ):
            return True
    return False


def answer_claims_run_counts(answer: str) -> bool:
    text = (answer or "").strip()
    if not text:
        return False
    if RUN_COUNT_CLAIM.search(text):
        return True
    # Broader: "N recent runs are recorded"
    if re.search(r"\brecent\s+runs?\b", text, re.I) and re.search(r"\b\d+\b", text):
        return True
    return False


def apply_run_history_honesty_gate(
    answer: str,
    *,
    query: str,
    tool_results: list[dict[str, Any]] | None = None,
    react_result: Any | None = None,
) -> str:
    """Refuse fabricated run-count claims when workflow_runs was never retrieved.

    Harder than moderate-confidence framing: a number derived from an unrelated
    tool (e.g. agent_status) is never an acceptable answer to a run-history ask.
    """
    if not is_run_history_question(query):
        return answer
    if tool_results_include_workflow_runs(tool_results, react_result=react_result):
        return answer
    # Without the tool that actually returns run history, do not answer the claim.
    return RUN_HISTORY_REFUSAL


def explanation_for_missing_run_history(
    explanation: str,
    *,
    query: str,
    tool_results: list[dict[str, Any]] | None = None,
    react_result: Any | None = None,
) -> str:
    if not is_run_history_question(query):
        return explanation
    if tool_results_include_workflow_runs(tool_results, react_result=react_result):
        return explanation
    base = (explanation or "").strip()
    if RUN_HISTORY_EXPLANATION_GAP.lower() in base.lower():
        return base
    if base:
        return f"{base}\n\n{RUN_HISTORY_EXPLANATION_GAP}"
    return RUN_HISTORY_EXPLANATION_GAP


def should_escalate_fast_for_run_history(mode_key: str, query: str, tool_names: list[str]) -> bool:
    """Routing/tool-availability gap: FAST omits workflow_runs but run-history needs it."""
    if (mode_key or "").strip().lower() != "fast":
        return False
    if not is_run_history_question(query):
        return False
    names = {str(n).strip() for n in (tool_names or [])}
    return "workflow_runs" not in names
