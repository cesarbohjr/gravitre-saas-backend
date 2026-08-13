"""Department recipes defined in capability terms — vendor resolution is runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

RecipeStepType = Literal["trigger", "invoke_tool", "agent", "approval"]


@dataclass(frozen=True)
class RecipeStepSpec:
    step_id: str
    name: str
    step_type: RecipeStepType
    capability_id: str | None = None


@dataclass(frozen=True)
class DepartmentRecipe:
    recipe_id: str
    name: str
    description: str
    department: str
    steps: tuple[RecipeStepSpec, ...]
    risk_level: str = "medium"
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipeId": self.recipe_id,
            "name": self.name,
            "description": self.description,
            "department": self.department,
            "riskLevel": self.risk_level,
            "requiresApproval": self.requires_approval,
            "steps": [
                {
                    "id": step.step_id,
                    "name": step.name,
                    "type": step.step_type,
                    **({"capabilityId": step.capability_id} if step.capability_id else {}),
                }
                for step in self.steps
            ],
        }


DEPARTMENT_RECIPES: dict[str, DepartmentRecipe] = {
    "sales.new-lead-enrichment": DepartmentRecipe(
        recipe_id="sales.new-lead-enrichment",
        name="New lead enrichment",
        description=(
            "Search CRM for the lead, pull supporting documents, create or update the record, "
            "and notify the team — resolved per connected CRM and chat stack."
        ),
        department="sales",
        steps=(
            RecipeStepSpec("trigger", "Lead selected", "trigger"),
            RecipeStepSpec("search_crm", "Search CRM contact", "invoke_tool", "crm.contact.search"),
            RecipeStepSpec("search_docs", "Search supporting documents", "invoke_tool", "document.search"),
            RecipeStepSpec("qualify", "Agent enrichment review", "agent"),
            RecipeStepSpec("write_crm", "Create or update CRM record", "invoke_tool", "crm.contact.create"),
            RecipeStepSpec("notify", "Notify team channel", "invoke_tool", "messaging.channel.post"),
        ),
        risk_level="medium",
        requires_approval=True,
    ),
    "hr.employee-onboarding": DepartmentRecipe(
        recipe_id="hr.employee-onboarding",
        name="Employee onboarding kickoff",
        description=(
            "Locate onboarding documents, send welcome email, schedule kickoff, "
            "and post to the team channel — resolved per connected mail/calendar/chat stack."
        ),
        department="operations",
        steps=(
            RecipeStepSpec("trigger", "New hire event", "trigger"),
            RecipeStepSpec("docs", "Find onboarding documents", "invoke_tool", "document.search"),
            RecipeStepSpec("welcome_email", "Send welcome email", "invoke_tool", "email.send"),
            RecipeStepSpec("kickoff", "Schedule kickoff meeting", "invoke_tool", "calendar.event.create"),
            RecipeStepSpec("notify", "Announce in team channel", "invoke_tool", "messaging.channel.post"),
        ),
        risk_level="medium",
        requires_approval=True,
    ),
    "sales.inbound-triage": DepartmentRecipe(
        recipe_id="sales.inbound-triage",
        name="Inbound lead triage",
        description="Look up the inbound contact in CRM and notify the sales channel.",
        department="sales",
        steps=(
            RecipeStepSpec("trigger", "Inbound lead event", "trigger"),
            RecipeStepSpec("lookup", "Look up CRM contact", "invoke_tool", "crm.contact.search"),
            RecipeStepSpec("notify", "Notify sales channel", "invoke_tool", "messaging.channel.post"),
        ),
        risk_level="low",
        requires_approval=False,
    ),
}


def get_recipe(recipe_id: str) -> DepartmentRecipe | None:
    return DEPARTMENT_RECIPES.get(str(recipe_id or "").strip().lower())


def list_recipes(*, department: str | None = None) -> list[DepartmentRecipe]:
    items = list(DEPARTMENT_RECIPES.values())
    if department:
        dept = department.strip().lower()
        items = [r for r in items if r.department == dept]
    return sorted(items, key=lambda r: r.recipe_id)
