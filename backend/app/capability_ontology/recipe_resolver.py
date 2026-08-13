"""Resolve capability-referenced department recipes to vendor-specific workflow steps."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.capability_ontology.recipes import DepartmentRecipe, RecipeStepSpec, get_recipe
from app.capability_ontology.resolver import CapabilityResolution, resolve_capability


@dataclass(frozen=True)
class ResolvedRecipeStep:
    step_id: str
    name: str
    step_type: str
    capability_id: str | None
    resolved_action: str | None
    resolved_vendor: str | None
    ambiguous: bool
    resolution: CapabilityResolution | None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.step_id,
            "name": self.name,
            "type": self.step_type,
            "capabilityId": self.capability_id,
            "resolvedAction": self.resolved_action,
            "resolvedVendor": self.resolved_vendor,
            "ambiguous": self.ambiguous,
        }
        if self.resolution is not None:
            payload["resolution"] = {
                "reason": self.resolution.reason,
                "method": self.resolution.resolution_method,
                "candidates": list(self.resolution.candidates),
            }
        return payload


@dataclass(frozen=True)
class ResolvedRecipe:
    recipe_id: str
    name: str
    department: str
    status: str
    steps: tuple[ResolvedRecipeStep, ...]
    ambiguous_steps: tuple[str, ...]
    unresolved_steps: tuple[str, ...]

    @property
    def fully_resolved(self) -> bool:
        return self.status == "fully_resolved"

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipeId": self.recipe_id,
            "name": self.name,
            "department": self.department,
            "status": self.status,
            "ambiguousSteps": list(self.ambiguous_steps),
            "unresolvedSteps": list(self.unresolved_steps),
            "steps": [step.to_dict() for step in self.steps],
        }


def _resolve_step(
    step: RecipeStepSpec,
    *,
    connected_integrations: list[str] | None,
    query: str,
    classification: dict[str, Any] | None,
    preferred_vendor: str | None,
) -> ResolvedRecipeStep:
    if step.step_type != "invoke_tool" or not step.capability_id:
        return ResolvedRecipeStep(
            step_id=step.step_id,
            name=step.name,
            step_type=step.step_type,
            capability_id=step.capability_id,
            resolved_action=None,
            resolved_vendor=None,
            ambiguous=False,
            resolution=None,
        )

    args = {"preferred_vendor": preferred_vendor} if preferred_vendor else None
    resolution = resolve_capability(
        step.capability_id,
        connected_integrations=connected_integrations,
        query=query,
        classification=classification,
        args=args,
    )
    return ResolvedRecipeStep(
        step_id=step.step_id,
        name=step.name,
        step_type=step.step_type,
        capability_id=step.capability_id,
        resolved_action=resolution.resolved_action,
        resolved_vendor=resolution.resolved_vendor,
        ambiguous=resolution.ambiguous,
        resolution=resolution,
    )


def resolve_recipe(
    recipe_id: str,
    *,
    connected_integrations: list[str] | None,
    query: str = "",
    classification: dict[str, Any] | None = None,
    preferred_vendor: str | None = None,
) -> ResolvedRecipe | None:
    recipe = get_recipe(recipe_id)
    if not recipe:
        return None

    resolved_steps = tuple(
        _resolve_step(
            step,
            connected_integrations=connected_integrations,
            query=query,
            classification=classification,
            preferred_vendor=preferred_vendor,
        )
        for step in recipe.steps
    )

    invoke_steps = [s for s in resolved_steps if s.step_type == "invoke_tool" and s.capability_id]
    ambiguous = tuple(s.step_id for s in invoke_steps if s.ambiguous)
    unresolved = tuple(
        s.step_id
        for s in invoke_steps
        if not s.ambiguous and not s.resolved_action
    )

    if ambiguous:
        status = "ambiguous"
    elif unresolved:
        status = "partial"
    else:
        status = "fully_resolved"

    return ResolvedRecipe(
        recipe_id=recipe.recipe_id,
        name=recipe.name,
        department=recipe.department,
        status=status,
        steps=resolved_steps,
        ambiguous_steps=ambiguous,
        unresolved_steps=unresolved,
    )


def resolve_recipe_for_org(
    recipe: DepartmentRecipe,
    *,
    connected_integrations: list[str] | None,
    query: str = "",
    classification: dict[str, Any] | None = None,
    preferred_vendor: str | None = None,
) -> ResolvedRecipe:
    resolved = resolve_recipe(
        recipe.recipe_id,
        connected_integrations=connected_integrations,
        query=query,
        classification=classification,
        preferred_vendor=preferred_vendor,
    )
    assert resolved is not None
    return resolved
