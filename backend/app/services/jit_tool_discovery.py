"""3.0-E JIT tool discovery — eligible ActionSpec set, not a 732-tool dump.

Search when needed (capability + connected sources + availability). Attach
catalog examples. F1 READ keys stay eligible when their vendor is connected.
Does not execute tools and does not weaken WRITE gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.connectors.action_catalog.action_retrieval_enrichment import enrichment_for_action
from app.connectors.action_catalog.f1_read_slice import F1_CATALOG_ACTIONS, is_f1_read_action
from app.connectors.action_catalog.models import ActionSpec
from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.core.safe_dict import safe_normalize_stored_dict
from app.connectors.action_catalog.tool_aliases import REGISTRY_VENDOR_PREFIX_ALIASES
from app.services.agent_platform_optimizer import _capability_eligible_prefixes

MAX_ELIGIBLE_TOOLS = 16
HARD_CAP_ELIGIBLE = 32

_REVERSE_ALIAS = {alias: vendor for vendor, alias in REGISTRY_VENDOR_PREFIX_ALIASES.items()}


def _normalize_vendor(raw: str) -> str:
    value = str(raw or "").strip().lower()
    return _REVERSE_ALIAS.get(value, value)


def _spec_vendor(spec_id: str) -> str:
    return str(spec_id or "").split(".", 1)[0].strip().lower()


def _connected_set(connected: list[str] | None) -> set[str]:
    out: set[str] = set()
    for item in connected or []:
        vendor = _normalize_vendor(item)
        if vendor:
            out.add(vendor)
            alias = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor)
            if alias:
                out.add(alias)
    return out


def _vendor_available(spec_id: str, connected: set[str], unavailable: set[str]) -> bool:
    vendor = _spec_vendor(spec_id)
    if vendor in unavailable:
        return False
    if not connected:
        return True
    alias = REGISTRY_VENDOR_PREFIX_ALIASES.get(vendor, vendor)
    return vendor in connected or alias in connected


def _capability_allows(spec: ActionSpec, prefixes: tuple[str, ...] | None) -> bool:
    if not prefixes:
        return True
    blob = f"{spec.id} {spec.name}".lower()
    vendor = _spec_vendor(spec.id)
    for prefix in prefixes:
        p = str(prefix).strip().lower().rstrip(".")
        if not p:
            continue
        if blob.startswith(p) or vendor.startswith(p) or p in blob:
            return True
    return False


def _score_spec(spec: ActionSpec, tokens: set[str], examples: list[str], tags: list[str]) -> float:
    if not tokens:
        return 0.0
    hay = " ".join(
        [
            spec.id.replace(".", " ").replace("_", " "),
            spec.name,
            spec.description or "",
            " ".join(tags),
            " ".join(examples),
        ]
    ).lower()
    hits = sum(1 for tok in tokens if tok in hay)
    return float(hits)


def _query_tokens(query: str) -> set[str]:
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in query).split() if len(part) >= 3}


@dataclass(frozen=True)
class EligibleAction:
    action_id: str
    name: str
    kind: str
    vendor: str
    score: float
    examples: tuple[str, ...]
    f1_read: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "name": self.name,
            "kind": self.kind,
            "vendor": self.vendor,
            "score": self.score,
            "examples": list(self.examples),
            "f1_read": self.f1_read,
        }


def search_eligible_action_specs(
    *,
    query: str,
    capability_id: str | None = None,
    connected: list[str] | None = None,
    unavailable: list[str] | None = None,
    include_writes: bool = False,
    max_results: int = MAX_ELIGIBLE_TOOLS,
) -> list[EligibleAction]:
    """Return a bounded eligible ActionSpec set. Never the full catalog."""
    cap = max(1, min(int(max_results or MAX_ELIGIBLE_TOOLS), HARD_CAP_ELIGIBLE))
    connected_set = _connected_set(connected)
    unavailable_set = {_normalize_vendor(v) for v in (unavailable or []) if str(v).strip()}
    prefixes = _capability_eligible_prefixes({"capability_id": capability_id} if capability_id else None)
    tokens = _query_tokens(query)
    ranked: list[EligibleAction] = []
    f1_keep: list[EligibleAction] = []

    for spec in all_catalog_action_specs():
        if not _vendor_available(spec.id, connected_set, unavailable_set):
            continue
        if not _capability_allows(spec, prefixes):
            continue
        if spec.kind == "write" and not include_writes:
            continue
        row = enrichment_for_action(spec.id) or {}
        examples = [str(x) for x in (row.get("examples") or []) if str(x).strip()][:2]
        tags = [str(x) for x in (row.get("tags") or []) if str(x).strip()]
        score = _score_spec(spec, tokens, examples, tags)
        item = EligibleAction(
            action_id=spec.id,
            name=spec.name,
            kind=str(spec.kind),
            vendor=_spec_vendor(spec.id),
            score=score,
            examples=tuple(examples),
            f1_read=is_f1_read_action(spec.id),
        )
        if item.f1_read and spec.id in F1_CATALOG_ACTIONS:
            f1_keep.append(item)
        ranked.append(item)

    ranked.sort(key=lambda row: (row.score, row.f1_read, row.action_id), reverse=True)
    selected: list[EligibleAction] = []
    seen: set[str] = set()
    for item in f1_keep:
        if item.action_id in seen:
            continue
        selected.append(item)
        seen.add(item.action_id)
        if len(selected) >= cap:
            return selected
    for item in ranked:
        if item.action_id in seen:
            continue
        if tokens and item.score <= 0 and not item.f1_read:
            continue
        selected.append(item)
        seen.add(item.action_id)
        if len(selected) >= cap:
            break
    return selected


def map_eligible_actions_to_tool_names(
    eligible: list[EligibleAction],
    full_by_name: dict[str, dict[str, Any]] | None,
    *,
    max_load: int = 5,
) -> list[str]:
    """Map eligible ActionSpecs onto already-narrowed tool schemas. Never invent tools."""
    cap = max(1, min(int(max_load or 5), HARD_CAP_ELIGIBLE))
    names: list[str] = []
    seen: set[str] = set()
    by_invoke: dict[str, str] = {}
    for name, tool in (full_by_name or {}).items():
        if not isinstance(tool, dict) or not name:
            continue
        inv = str(tool.get("invoke_action") or "").strip()
        if inv:
            by_invoke[inv] = name
        by_invoke.setdefault(str(name).replace("_", "."), name)
    for item in eligible:
        name = by_invoke.get(item.action_id) or item.action_id.replace(".", "_")
        if name not in (full_by_name or {}) or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= cap:
            break
    return names


def rank_tool_names(query: str, candidate_names: list[str], *, max_load: int = 5) -> list[str]:
    """Rank already-narrowed tool names for search_catalog_tools query fallback."""
    tokens = _query_tokens(query)
    if not tokens:
        return list(candidate_names)[:max_load]
    scored: list[tuple[float, str]] = []
    for name in candidate_names:
        blob = str(name or "").replace("_", " ").lower()
        hits = sum(1 for tok in tokens if tok in blob)
        if hits:
            scored.append((float(hits), name))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [name for _, name in scored[:max_load]]


def attach_examples_to_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append one catalog example onto tool descriptions. Does not expand the set."""
    out: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        cloned = dict(tool)
        fn = safe_normalize_stored_dict(cloned.get("function")) if isinstance(cloned.get("function"), dict) else {}
        invoke = str(cloned.get("invoke_action") or "").strip()
        name = str(fn.get("name") or cloned.get("name") or "")
        if not invoke and name:
            try:
                from app.connectors.action_catalog.action_id_resolve import (
                    resolve_action_id_from_tool_name,
                )

                invoke = resolve_action_id_from_tool_name(name)
            except Exception:  # noqa: BLE001
                invoke = ""
        row = enrichment_for_action(invoke) if invoke else None
        examples = [str(x) for x in (row.get("examples") or [])] if isinstance(row, dict) else []
        if examples:
            desc = str(fn.get("description") or cloned.get("description") or "").rstrip()
            example = examples[0].strip()
            if example and example.lower() not in desc.lower():
                fn["description"] = f"{desc} Example: {example}"[:240] if desc else f"Example: {example}"[:240]
                cloned["function"] = fn
            cloned["jit_examples"] = examples[:2]
        out.append(cloned)
    return out
