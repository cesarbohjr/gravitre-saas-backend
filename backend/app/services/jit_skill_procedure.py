"""3.0-E versioned procedures loaded JIT from recipes + tool knowledge.

Skills are procedures (owner, revision, tests) — not a second agent runtime.
They do not invoke tools, approve WRITEs, or mint a Cowork worker.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.capability_ontology.recipes import list_recipes
from app.knowledge_fabric.tool_knowledge import _TOOL_DOCS

SKILL_REVISION = "3.0-E.1"
PROCEDURE_OWNER_RECIPES = "capability_ontology.recipes"
PROCEDURE_OWNER_TOOL_KNOWLEDGE = "knowledge_fabric.tool_knowledge"
MAX_JIT_SKILLS = 3

_RECIPE_TESTS = (
    "tests/capability_ontology/test_capability_recipes.py",
    "tests/services/test_jit_tool_skills.py",
)
_TOOL_KNOWLEDGE_TESTS = (
    "tests/services/test_jit_tool_skills.py",
)


@dataclass(frozen=True)
class SkillProcedure:
    skill_id: str
    version: str
    owner: str
    last_verified: str
    tests: tuple[str, ...]
    title: str
    procedure: str
    source: Literal["recipe", "tool_knowledge"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "owner": self.owner,
            "last_verified": self.last_verified,
            "tests": list(self.tests),
            "title": self.title,
            "procedure": self.procedure,
            "source": self.source,
            "runtime": "procedure_only",
        }


def _tokens(text: str) -> set[str]:
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(part) >= 3}


def load_jit_procedures(
    *,
    query: str,
    capability_id: str | None = None,
    connected: list[str] | None = None,
    department: str | None = None,
    max_skills: int = MAX_JIT_SKILLS,
) -> list[SkillProcedure]:
    """JIT-load matching procedures. Empty query still returns capability/department hits."""
    cap = max(1, min(int(max_skills or MAX_JIT_SKILLS), 6))
    q_tokens = _tokens(query)
    cap_id = str(capability_id or "").strip().lower()
    dept = str(department or "").strip().lower()
    connected_set = {str(c).strip().lower() for c in (connected or []) if str(c).strip()}
    hits: list[tuple[int, SkillProcedure]] = []

    for recipe in list_recipes(department=dept or None):
        blob = " ".join(
            [
                recipe.recipe_id,
                recipe.name,
                recipe.description,
                recipe.department,
                " ".join(step.capability_id or "" for step in recipe.steps),
            ]
        ).lower()
        score = 0
        if cap_id and any(
            (step.capability_id or "").lower() == cap_id or cap_id in recipe.recipe_id
            for step in recipe.steps
        ):
            score += 5
        if dept and recipe.department == dept:
            score += 2
        score += sum(1 for tok in q_tokens if tok in blob)
        if score <= 0:
            continue
        steps = "; ".join(f"{step.step_id}:{step.name}" for step in recipe.steps[:6])
        hits.append(
            (
                score,
                SkillProcedure(
                    skill_id=f"recipe:{recipe.recipe_id}",
                    version=SKILL_REVISION,
                    owner=PROCEDURE_OWNER_RECIPES,
                    last_verified=SKILL_REVISION,
                    tests=_RECIPE_TESTS,
                    title=recipe.name,
                    procedure=f"{recipe.description} Steps: {steps}",
                    source="recipe",
                ),
            )
        )

    for vendor, docs in _TOOL_DOCS.items():
        if connected_set and vendor not in connected_set:
            continue
        for doc in docs[:1]:
            title = str(doc.get("title") or vendor)
            content = str(doc.get("content") or "")
            blob = f"{vendor} {title} {content}".lower()
            score = sum(1 for tok in q_tokens if tok in blob)
            if connected_set and vendor in connected_set:
                score += 1
            if score <= 0:
                continue
            hits.append(
                (
                    score,
                    SkillProcedure(
                        skill_id=f"tool_knowledge:{vendor}:{doc.get('external_id')}",
                        version=SKILL_REVISION,
                        owner=PROCEDURE_OWNER_TOOL_KNOWLEDGE,
                        last_verified=SKILL_REVISION,
                        tests=_TOOL_KNOWLEDGE_TESTS,
                        title=title,
                        procedure=content[:400],
                        source="tool_knowledge",
                    ),
                )
            )

    hits.sort(key=lambda row: (-row[0], row[1].skill_id))
    return [proc for _, proc in hits[:cap]]


def format_jit_skill_section(
    *,
    query: str,
    capability_id: str | None = None,
    connected: list[str] | None = None,
    department: str | None = None,
) -> str:
    skills = load_jit_procedures(
        query=query,
        capability_id=capability_id,
        connected=connected,
        department=department,
    )
    if not skills:
        return ""
    lines = [
        "<jit_procedures runtime=procedure_only>",
        "Versioned procedures (not an agent runtime). WRITEs still require react_write_gate.",
    ]
    for skill in skills:
        lines.append(
            f"- {skill.title} [{skill.skill_id} v{skill.version} owner={skill.owner}] "
            f"{skill.procedure[:220]}"
        )
    lines.append("</jit_procedures>")
    return "\n".join(lines)
