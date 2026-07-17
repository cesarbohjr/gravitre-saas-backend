"""Human-like working memory profile — LTM / STM / scratchpad adapter.

Composes existing ConversationMemoryEngine, task_state, and connector session
state into one profile for IntelligenceOrchestrator. Does not persist new tables.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WorkingMemoryProfile:
    """Structured working memory for a single assistant turn."""

    long_term: dict[str, Any] = field(default_factory=dict)
    short_term: dict[str, Any] = field(default_factory=dict)
    scratchpad: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def prompt_section(self, *, max_chars: int = 2400) -> str:
        parts: list[str] = []
        company = self.long_term.get("company_profile") or {}
        user = self.long_term.get("user_profile") or {}
        if company or user:
            bits = []
            if company.get("summary"):
                bits.append(f"Company: {company['summary']}")
            if user.get("preferences"):
                prefs = user["preferences"]
                if isinstance(prefs, list):
                    bits.append("Preferences: " + "; ".join(str(p) for p in prefs[:6]))
                elif prefs:
                    bits.append(f"Preferences: {prefs}")
            if bits:
                parts.append("## Long-term memory\n" + "\n".join(bits))

        objective = self.short_term.get("current_objective")
        workflow = self.short_term.get("current_workflow")
        task = self.short_term.get("current_task")
        stm_bits = [b for b in (objective, workflow, task) if b]
        if stm_bits:
            parts.append("## Short-term memory\n" + "\n".join(f"- {b}" for b in stm_bits))

        notes = self.scratchpad.get("interim_notes") or []
        entities = self.scratchpad.get("active_entities") or []
        if notes or entities:
            lines = []
            if entities:
                lines.append("Active entities: " + ", ".join(str(e) for e in entities[:12]))
            for note in notes[:8]:
                lines.append(f"- {note}")
            parts.append("## Scratchpad\n" + "\n".join(lines))

        text = "\n\n".join(parts).strip()
        if len(text) > max_chars:
            return text[: max_chars - 1].rstrip() + "…"
        return text


def build_working_memory_profile(
    *,
    conversation_memory: dict[str, Any] | None,
    task_state: dict[str, Any] | None,
    session_state: dict[str, Any] | None = None,
    org_context_block: str = "",
    query: str = "",
) -> WorkingMemoryProfile:
    """Assemble LTM/STM/scratchpad from existing turn artifacts (fail-open)."""
    memory = conversation_memory or {}
    task = task_state or {}
    session = session_state or {}

    prefs = memory.get("preferences") or memory.get("relevant", {}).get("preferences") or []
    if not isinstance(prefs, list):
        prefs = [prefs] if prefs else []

    long_term = {
        "company_profile": {
            "summary": (org_context_block or "")[:500].strip() or None,
        },
        "user_profile": {
            "preferences": prefs[:8],
            "rejections": list(memory.get("rejections") or memory.get("relevant", {}).get("rejections") or [])[:6],
        },
        "department_profile": {
            "key": memory.get("department") or task.get("department"),
        },
    }

    plan = task.get("current_plan") or {}
    short_term = {
        "current_objective": (
            (plan.get("objective") if isinstance(plan, dict) else None)
            or task.get("objective")
            or (query[:240] if query else None)
        ),
        "current_workflow": task.get("workflow_id") or task.get("active_workflow"),
        "current_task": task.get("pending_task") or task.get("clarified_params"),
        "completed_steps": list(task.get("completed_steps") or [])[:12],
        "pending_steps": list(task.get("pending_steps") or [])[:12],
    }

    interim = list(session.get("step_outputs") or [])
    note_texts: list[str] = []
    if isinstance(session.get("session_summary"), str) and session["session_summary"].strip():
        note_texts.append(session["session_summary"].strip()[:400])
    for row in interim[:6]:
        if isinstance(row, dict):
            note_texts.append(str(row.get("summary") or row.get("action") or row)[:200])
        else:
            note_texts.append(str(row)[:200])

    scratchpad = {
        "active_entities": list(session.get("active_entities") or task.get("active_entities") or [])[:20],
        "interim_notes": note_texts,
        "temporary_reasoning": list(task.get("scratchpad") or [])[:8],
    }

    return WorkingMemoryProfile(
        long_term=long_term,
        short_term=short_term,
        scratchpad=scratchpad,
    )
