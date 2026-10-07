"""Outcome Pack registry: the one place department knowledge enters the runtime.

Every module under ``app.outcome_packs.manifests`` exports ``build()`` returning
``{"marketplace": {...}, "config": {...}}`` where ``config`` validates as
``OutcomePackAssetConfig``. Everything the platform derives from packs (the
metric catalog, Play definitions, verification recipes, dashboard templates,
governance and learning signals) is computed here, so adding a department never
needs new runtime code.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.safe_dict import safe_normalize_stored_dict
from app.marketplace.schemas import (
    OutcomeKpiConfig,
    OutcomePackAssetConfig,
    PlayAssetConfig,
    VerificationRecipeConfig,
)

MANIFEST_PACKAGE = "app.outcome_packs.manifests"


@dataclass(frozen=True)
class OutcomePack:
    pack_id: str
    department: str
    config: OutcomePackAssetConfig
    raw_config: dict[str, Any]
    marketplace: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return str(self.marketplace.get("title") or self.config.dashboard.title)

    @property
    def slug(self) -> str:
        return str(self.marketplace.get("slug") or self.pack_id)


class OutcomePackError(ValueError):
    pass


def _load_manifest(module_name: str) -> OutcomePack:
    module = importlib.import_module(module_name)
    build = getattr(module, "build", None)
    if not callable(build):
        raise OutcomePackError(f"{module_name} must export build()")
    manifest = build()
    raw = safe_normalize_stored_dict(manifest, key="config")
    config = OutcomePackAssetConfig.model_validate(raw)
    if not config.pack_id:
        raise OutcomePackError(f"{module_name} config requires pack_id")
    return OutcomePack(
        pack_id=config.pack_id,
        department=str(config.department or ""),
        config=config,
        raw_config=raw,
        marketplace=safe_normalize_stored_dict(manifest, key="marketplace"),
    )


@lru_cache(maxsize=1)
def _packs() -> tuple[OutcomePack, ...]:
    package = importlib.import_module(MANIFEST_PACKAGE)
    packs: list[OutcomePack] = []
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        packs.append(_load_manifest(f"{MANIFEST_PACKAGE}.{info.name}"))
    ids = [p.pack_id for p in packs]
    if len(ids) != len(set(ids)):
        raise OutcomePackError("duplicate Outcome Pack ids")
    play_keys = [play.key for p in packs for play in p.config.plays]
    duplicates = sorted({k for k in play_keys if play_keys.count(k) > 1})
    if duplicates:
        raise OutcomePackError(f"Play keys must be unique across packs: {', '.join(duplicates)}")
    recipe_keys = [r.key for p in packs for r in p.config.verification_recipes]
    duplicates = sorted({k for k in recipe_keys if recipe_keys.count(k) > 1})
    if duplicates:
        raise OutcomePackError(f"recipe keys must be unique across packs: {', '.join(duplicates)}")
    return tuple(packs)


def clear_cache() -> None:
    _packs.cache_clear()
    _metric_index.cache_clear()
    always_approve_actions.cache_clear()


def list_packs() -> list[OutcomePack]:
    return list(_packs())


def get_pack(pack_id: str) -> OutcomePack | None:
    wanted = str(pack_id or "").strip().lower()
    return next((p for p in _packs() if p.pack_id == wanted or p.slug == wanted), None)


# --------------------------------------------------------------------------- metrics

_SEMANTIC_FIELDS = (
    "description", "kind", "aggregation", "numerator", "denominator", "source_system",
    "source_record_type", "verification_recipe", "evidence_strategy", "definition_prompt",
)


def _merge_metric(existing: dict[str, Any] | None, kpi: OutcomeKpiConfig, pack: OutcomePack) -> dict[str, Any]:
    row = dict(existing or {})
    if not row:
        row = {
            "metric_key": kpi.key,
            "label": kpi.label,
            "unit": kpi.unit,
            "direction": kpi.direction,
            "formula": kpi.formula or kpi.description,
            "owner": "platform",
            "department": kpi.department or pack.department,
            "departments": [],
            "synonyms": [],
            "packs": [],
            "learning": dict(kpi.learning),
        }
        for name in _SEMANTIC_FIELDS:
            row[name] = getattr(kpi, name)
    else:
        # The first declaration owns semantics; later packs may only fill gaps.
        for name in _SEMANTIC_FIELDS:
            if not row.get(name) and getattr(kpi, name):
                row[name] = getattr(kpi, name)
    departments = list(row.get("departments") or [])
    for dept in [kpi.department or pack.department, *kpi.departments, pack.department]:
        if dept and dept not in departments:
            departments.append(dept)
    row["departments"] = departments
    row["synonyms"] = sorted({*row.get("synonyms", []), *[s.lower() for s in kpi.synonyms], kpi.label.lower()})
    row["packs"] = sorted({*row.get("packs", []), pack.pack_id})
    return row


@lru_cache(maxsize=1)
def _metric_index() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for pack in _packs():
        for kpi in pack.config.outcome_contract.kpis:
            index[kpi.key] = _merge_metric(index.get(kpi.key), kpi, pack)
    return index


def metric_definitions() -> list[dict[str, Any]]:
    """Platform metric catalog rows contributed by Outcome Packs (org overrides still win)."""
    return [dict(row) for _, row in sorted(_metric_index().items())]


def metric_definition(metric_key: str) -> dict[str, Any] | None:
    row = _metric_index().get(str(metric_key or "").strip().lower())
    return dict(row) if row else None


def metric_conflicts() -> list[str]:
    """Same key declared with different unit or direction across packs (certification check)."""
    seen: dict[str, tuple[str, str, str]] = {}
    problems: list[str] = []
    for pack in _packs():
        for kpi in pack.config.outcome_contract.kpis:
            sig = (kpi.unit, kpi.direction)
            if kpi.key in seen and seen[kpi.key][:2] != sig:
                problems.append(
                    f"{kpi.key}: {seen[kpi.key][2]} declares {seen[kpi.key][:2]}, {pack.pack_id} declares {sig}"
                )
            seen.setdefault(kpi.key, (*sig, pack.pack_id))
    return problems


# --------------------------------------------------------------------------- recipes

def verification_recipes() -> list[tuple[OutcomePack, VerificationRecipeConfig]]:
    return [(pack, recipe) for pack in _packs() for recipe in pack.config.verification_recipes]


def get_recipe(recipe_key: str) -> tuple[OutcomePack, VerificationRecipeConfig] | None:
    wanted = str(recipe_key or "").strip()
    return next(((p, r) for p, r in verification_recipes() if r.key == wanted), None)


def recipes_for_action(action: str) -> list[tuple[OutcomePack, VerificationRecipeConfig]]:
    """Recipes that verify records written by ``action`` (a concrete catalog action)."""
    wanted = str(action or "").strip().lower()
    return [(p, r) for p, r in verification_recipes() if wanted in {a.lower() for a in r.match_actions}]


def recipes_for_record(system: str, record_type: str) -> list[tuple[OutcomePack, VerificationRecipeConfig]]:
    sys_l, type_l = str(system or "").lower(), str(record_type or "").lower()
    return [
        (p, r)
        for p, r in verification_recipes()
        if r.source_system.lower() == sys_l and r.record_type.lower() == type_l
    ]


# --------------------------------------------------------------------------- plays

def play_assets() -> list[tuple[OutcomePack, PlayAssetConfig]]:
    return [(pack, play) for pack in _packs() for play in pack.config.plays]


def pack_for_play(play_key: str) -> OutcomePack | None:
    wanted = str(play_key or "").strip().lower()
    return next((pack for pack, play in play_assets() if play.key == wanted), None)


def play_asset(play_key: str) -> PlayAssetConfig | None:
    wanted = str(play_key or "").strip().lower()
    return next((play for _, play in play_assets() if play.key == wanted), None)


def plays_for_metric(metric_key: str) -> list[tuple[OutcomePack, PlayAssetConfig]]:
    """Plays declared to influence a canonical metric (directly or through a ratio's components)."""
    key = str(metric_key or "").strip().lower()
    definition = metric_definition(key) or {}
    keys = {key}
    if definition.get("aggregation") == "ratio":
        keys |= {str(definition.get("numerator") or ""), str(definition.get("denominator") or "")}
    return [(p, play) for p, play in play_assets() if keys & set(play.kpi_keys)]


def _capability_actions(capability_id: str) -> tuple[str, ...]:
    from app.capability_ontology.registry import capability_actions

    return capability_actions(capability_id)


def expand_group(group: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Concrete catalog actions for an OR group of capability ids and/or actions."""
    out: list[str] = []
    for item in group:
        actions = _capability_actions(item) if "." in item and _capability_actions(item) else (item,)
        for action in actions:
            if action not in out:
                out.append(action)
    return tuple(out)


def play_write_actions(play: PlayAssetConfig) -> tuple[str, ...]:
    """Every concrete write action a Play may take, across provider alternatives."""
    from app.capabilities.registry import get_action

    candidates: list[str] = []
    for item in play.write_actions:
        cap = str(item.get("capability") or "")
        action = str(item.get("action") or "")
        for tool in (_capability_actions(cap) if cap else ()) + ((action,) if action else ()):
            if tool and tool not in candidates:
                candidates.append(tool)
    for group in play.write_action_groups:
        for tool in expand_group(group):
            if tool not in candidates:
                candidates.append(tool)
    return tuple(
        tool for tool in candidates if not tool.startswith("gravitre.") and (get_action(tool) is None or get_action(tool).access == "write")
    )


def play_definitions() -> tuple[Any, ...]:
    """``PlayDefinition`` contracts derived from pack Plays (no hand-maintained duplicates)."""
    from app.capabilities.registry import get_action
    from app.plays.contracts import PlayDefinition, VerificationRequirement

    out = []
    for pack, item in play_assets():
        read_groups: list[tuple[str, ...]] = []
        write_groups: list[tuple[str, ...]] = []
        for group in item.capability_groups:
            actions = expand_group(group)
            concrete = tuple(a for a in actions if not a.startswith("gravitre."))
            if not concrete:
                continue
            accesses = {(get_action(a).access if get_action(a) else None) for a in concrete}
            if "write" in accesses and "read" not in accesses:
                write_groups.append(concrete)
            else:
                read_groups.append(concrete)
        for group in item.read_action_groups:
            read_groups.append(expand_group(group))
        for group in item.write_action_groups:
            write_groups.append(expand_group(group))
        connector_groups = [tuple(g) for g in item.required_connector_groups]
        if not connector_groups and pack.config.connector_alternatives:
            connector_groups = [tuple(pack.config.connector_alternatives[0])]
        verification = tuple(
            VerificationRequirement(action_tool=tool, minimum_mode="source_of_record")
            for tool in play_write_actions(item)
            if recipes_for_action(tool)
        )
        out.append(
            PlayDefinition(
                key=item.key,
                name=item.name,
                version="1",
                objective=item.objective or item.description,
                required_connector_groups=tuple(connector_groups),
                optional_connectors=tuple(item.optional_connectors),
                required_read_action_groups=tuple(read_groups),
                write_action_groups=tuple(write_groups),
                outcome_metrics=tuple(item.kpi_keys),
                verification_requirements=verification,
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- dashboards / governance / learning

def dashboard_templates() -> list[dict[str, Any]]:
    templates = []
    for pack in _packs():
        dash = pack.config.dashboard
        sections = dash.sections or [{"title": dash.title, "kpi_keys": [m.kpi_key for m in dash.metrics]}]
        templates.append(
            {
                "templateId": dash.template_id or f"{pack.pack_id}-dashboard",
                "name": dash.title,
                "department": dash.department or pack.department,
                "packId": pack.pack_id,
                "sections": [
                    {
                        "title": s.title if hasattr(s, "title") else s["title"],
                        "kpiKeys": list(s.kpi_keys if hasattr(s, "kpi_keys") else s["kpi_keys"]),
                    }
                    for s in sections
                ],
                "systemHealthKpis": list(dash.system_health_kpis),
            }
        )
    return templates


@lru_cache(maxsize=1)
def always_approve_actions() -> frozenset[str]:
    """Declared always-approve writes plus every provider alternative of a Play write marked approval=always."""
    out = {a for pack in _packs() for a in pack.config.governance.always_approve_actions}
    for _, play in play_assets():
        for item in play.write_actions:
            if str(item.get("approval") or "") != "always":
                continue
            cap = str(item.get("capability") or "")
            out.update(_capability_actions(cap) if cap else ())
            if item.get("action"):
                out.add(str(item["action"]))
    return frozenset(a for a in out if not a.startswith("gravitre."))


def learning_signals() -> dict[str, dict[str, str]]:
    """Per metric: which learning events verified movement emits (defaults are generic)."""
    out = {}
    for key, row in _metric_index().items():
        learning = safe_normalize_stored_dict(row, key="learning")
        out[key] = {
            "improved_event": learning.get("improved_event", "business_metric_improved"),
            "declined_event": learning.get("declined_event", "business_metric_declined"),
        }
    return out


_STOP = frozenset({"more", "help", "with", "this", "that", "from", "into", "month", "week", "quarter", "year", "time", "rate", "per", "our", "the"})


def _stems(text: str) -> set[str]:
    import re

    return {w[:5] for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3 and w not in _STOP}


def _token_overlap(text: str, phrases: list[str]) -> float:
    """Weak match: every meaningful word stem of a synonym appears in the text."""
    words = _stems(text)
    best = 0.0
    for phrase in phrases:
        stems = _stems(phrase)
        if len(stems) >= 2 and stems <= words:
            best = max(best, 0.5 * len(stems))
    return best


def match_metrics(text: str, *, limit: int = 3) -> list[tuple[str, float]]:
    """Rank canonical metrics against user language using declared synonyms (no hard-coded objectives)."""
    lowered = f" {str(text or '').lower()} "
    scored: list[tuple[str, float]] = []
    for key, row in _metric_index().items():
        best = 0.0
        for phrase in [*row.get("synonyms", []), key.replace("_", " ")]:
            phrase = phrase.strip().lower()
            if phrase and f" {phrase} " in lowered or (phrase and phrase in lowered and len(phrase) > 5):
                best = max(best, float(len(phrase.split())) + len(phrase) / 100.0)
        if not best:
            best = _token_overlap(lowered, [*row.get("synonyms", []), key.replace("_", " ")])
        if best:
            if row.get("kind") == "business":
                best += 0.5
            scored.append((key, best))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:limit]
