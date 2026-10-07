"""Objective-first capability composition for Outcome Ownership.

This is deliberately resource-agnostic: the planner composes evidence and action
resources around an objective instead of treating connectors as the only tools.

The same module carries the whole objective loop the cognitive planner runs:
objective contract (canonical metric, definition, target, period), baseline
and gap from verified results, resources (Plays from any Outcome Pack) with
each capability resolved across alternative providers, feasibility (a target
is not a promise), the recommended plan, progress and replanning. Nothing is
keyed by department or objective type; metrics, Plays, capabilities and
recipes come from the Outcome Pack registry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)


RESOURCE_KINDS = frozenset(
    {"connector", "agent", "workflow", "play", "knowledge", "dataset", "internet"}
)


@dataclass(frozen=True)
class CapabilityResource:
    resource_id: str
    kind: str
    capabilities: frozenset[str]
    # Callers state connection explicitly; raw runtime descriptors without a
    # "connected" flag are treated as disconnected by the planner.
    connected: bool = True
    writable: bool = False
    verified: bool = False
    priority: int = 100


def compose_capability_resources(
    *,
    required_capabilities: set[str],
    resources: list[CapabilityResource],
    require_write: bool = False,
    write_capabilities: set[str] | None = None,
) -> dict[str, Any]:
    """Greedy capability cover over connected resources.

    ``write_capabilities`` names the capabilities that must be served by a
    writable resource (e.g. ``crm.update`` but not ``web.search``);
    ``require_write`` applies that to every capability.
    """
    required = {str(x).strip() for x in required_capabilities if str(x).strip()}
    needs_write = set(required) if require_write else {
        str(x).strip() for x in (write_capabilities or set()) if str(x).strip()
    } & required

    def servable(r: CapabilityResource) -> set[str]:
        caps = set(r.capabilities) & required
        return caps if r.writable else caps - needs_write

    eligible = [r for r in resources if r.kind in RESOURCE_KINDS and r.connected and servable(r)]
    eligible.sort(key=lambda r: (r.priority, r.kind, r.resource_id))

    selected: list[CapabilityResource] = []
    covered: set[str] = set()
    # Greedy set cover with stable priority tie-breaking. The output is an
    # execution candidate set, not a completion claim.
    while required - covered:
        remaining = required - covered
        candidates = [r for r in eligible if servable(r) & remaining and r not in selected]
        if not candidates:
            break
        candidates.sort(
            key=lambda r: (
                -len(servable(r) & remaining),
                r.priority,
                r.kind,
                r.resource_id,
            )
        )
        chosen = candidates[0]
        selected.append(chosen)
        covered |= servable(chosen)

    missing = sorted(required - covered)
    ready = not missing
    return {
        "selected": [
            {
                "resource_id": r.resource_id,
                "kind": r.kind,
                "capabilities": sorted(r.capabilities),
                "serves": sorted(servable(r)),
                "writable": r.writable,
                "verified": r.verified,
            }
            for r in selected
        ],
        "covered_capabilities": sorted(covered & required),
        "missing_capabilities": missing,
        "write_capabilities": sorted(needs_write),
        # "ready" = every capability has an eligible resource; it is a plan, not
        # an outcome. "complete" is kept as a deprecated alias for older readers.
        "ready": ready,
        "complete": ready,
        "verification_ready": ready and all(r.verified for r in selected),
    }


# =========================================================================== objective loop

PERIOD_RANGE = {"week": "7d", "month": "30d", "quarter": "90d", "year": "365d"}
PERIOD_DAYS = {"week": 7, "month": 30, "quarter": 90, "year": 365}
REPLAN_EVERY = timedelta(days=7)

_PERIOD_PATTERNS = (
    (r"\b(per|a|each|every|this|next|in a)\s+week\b|\bweekly\b|/\s*w(ee)?k\b", "week"),
    (r"\b(per|a|each|every|this|next|in a)\s+month\b|\bmonthly\b|/\s*mo(nth)?\b|\bmo\b", "month"),
    (r"\b(per|a|each|every|this|next|in a)\s+quarter\b|\bquarterly\b|/\s*q(tr)?\b|\bq[1-4]\b", "quarter"),
    (r"\b(per|a|each|every|this|next|in a)\s+year\b|\byearly\b|\bannually\b|/\s*y(ea)?r\b", "year"),
)
_DECREASE_WORDS = ("reduce", "lower", "decrease", "cut", "shorten", "faster", "drop", "minimi", "less ")
_GOAL_VERBS = (
    "help me", "i want", "we want", "we need", "i need", "get us", "grow", "increase", "generate",
    "improve", "reduce", "lower", "boost", "hit", "reach", "achieve", "double", "book", "close",
    "retain", "win", "drive", "raise", "cut",
)
_TIME_UNITS = {"minute": 1.0, "min": 1.0, "hour": 60.0, "hr": 60.0, "day": 1440.0}
_TO_MINUTES = {"minutes": 1.0, "hours": 60.0, "days": 1440.0}
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|m|%|percent)?(?![\w])", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- understand


_GEO_TERMS: dict[str, str] = {
    "canada": "Canada", "canadian": "Canada",
    "united states": "United States", "usa": "United States", "u.s.": "United States", "us-based": "United States",
    "american": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "british": "United Kingdom",
    "australia": "Australia", "australian": "Australia", "new zealand": "New Zealand",
    "germany": "Germany", "german": "Germany", "france": "France", "french": "France",
    "ireland": "Ireland", "irish": "Ireland", "netherlands": "Netherlands", "dutch": "Netherlands",
    "europe": "Europe", "european": "Europe", "emea": "EMEA", "apac": "APAC",
    "north america": "North America", "north american": "North America",
    "latin america": "Latin America", "latam": "Latin America",
}
_GEO_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(k) for k in _GEO_TERMS), key=len, reverse=True)) + r")(?![\w])",
    re.I,
)
_US_TOKEN_RE = re.compile(r"(?<![\w.])US(?![\w.])")
_SIZE_NOUN = r"(?:employees?|staff|people|persons?|headcount|ftes?|seats?)"
_EMP_RANGE_RE = re.compile(r"(\d{1,6})\s*(?:-|–|—|to)\s*(\d{1,6})\s*" + _SIZE_NOUN, re.I)
_EMP_MIN_RE = re.compile(r"(?:over|more than|at least|above|minimum of)\s+(\d{1,6})\s*" + _SIZE_NOUN + r"|(\d{1,6})\s*\+\s*" + _SIZE_NOUN, re.I)
_EMP_MAX_RE = re.compile(r"(?:under|fewer than|less than|below|up to|at most)\s+(\d{1,6})\s*" + _SIZE_NOUN, re.I)
_GENERIC_SEGMENT = frozenset(
    {"companies", "company", "businesses", "business", "firms", "accounts", "organizations", "organisations",
     "orgs", "leads", "prospects", "customers", "ones", "them", "those", "people", "contacts", "a", "an", "the",
     "and", "or"}
)
_SEGMENT_STOP = r"(?:with|in|that|who|having|from|based|of|and|only|instead|please|per|each|every|$)"
_SEGMENT_AFTER_GEO_RE = re.compile(
    r"(?:" + "|".join(sorted((re.escape(k) for k in _GEO_TERMS), key=len, reverse=True)) + r")\s+"
    r"([A-Za-z][\w&/-]*(?:\s+[A-Za-z][\w&/-]*){0,2}?)\s*(?=\b" + _SEGMENT_STOP + r"\b|[,.;!?]|$)",
    re.I,
)
_SEGMENT_LEAD_RE = re.compile(
    r"(?:make (?:that|it)|only|target|focus on|just|switch to|change (?:it|that) to)\s+(?:to\s+)?"
    r"([A-Za-z][\w&/-]*(?:\s+[A-Za-z][\w&/-]*){0,2}?)\s*(?=\b" + _SEGMENT_STOP + r"\b|[,.;!?]|$)",
    re.I,
)


def _constraint_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for r in (_EMP_RANGE_RE, _EMP_MIN_RE, _EMP_MAX_RE) for m in r.finditer(text)]


def extract_constraints(text: str) -> dict[str, Any]:
    """Audience constraints stated in plain language: geography, segment and company size.

    Deterministic and vendor-neutral. The result is merged into the objective
    contract so a correction changes only the constraints it names.
    """
    raw = str(text or "")
    out: dict[str, Any] = {}
    geos = []
    for m in _GEO_RE.finditer(raw):
        if m.group(1).lower() == "us" or (m.group(1).lower() == "uk" and not m.group(1).isupper()):
            continue
        geo = _GEO_TERMS[m.group(1).lower()]
        if geo not in geos:
            geos.append(geo)
    # "US" only as an uppercase token, so the pronoun in "help us" is never a country.
    if _US_TOKEN_RE.search(raw) and "United States" not in geos:
        geos.append("United States")
    if geos:
        out["geography"] = geos
    employees: dict[str, int] = {}
    m = _EMP_RANGE_RE.search(raw)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        employees = {"min": lo, "max": hi}
    else:
        m = _EMP_MIN_RE.search(raw)
        if m:
            employees["min"] = int(m.group(1) or m.group(2))
        m = _EMP_MAX_RE.search(raw)
        if m:
            employees["max"] = int(m.group(1))
    if employees:
        out["employees"] = employees
    segment = None
    for pattern in (_SEGMENT_AFTER_GEO_RE, _SEGMENT_LEAD_RE):
        for m in pattern.finditer(raw):
            words = [
                w for w in m.group(1).split()
                if len(w) > 1 and w.lower() not in _GENERIC_SEGMENT and not _GEO_RE.fullmatch(w) and w != "US"
            ]
            if words and not any(w.isdigit() for w in words):
                segment = " ".join(words)
                break
        if segment:
            break
    if segment:
        out["segment"] = segment
    return out


def describe_constraints(constraints: dict[str, Any] | None) -> str:
    """'Canadian MSPs with 20–100 employees' style phrase, or '' when there are none."""
    c = constraints or {}
    parts: list[str] = []
    if c.get("segment"):
        parts.append(str(c["segment"]))
    else:
        parts.append("companies")
    if c.get("geography"):
        parts.append("in " + " or ".join(c["geography"]))
    emp = c.get("employees") or {}
    if emp.get("min") is not None and emp.get("max") is not None:
        parts.append(f"with {emp['min']}–{emp['max']} employees")
    elif emp.get("min") is not None:
        parts.append(f"with at least {emp['min']} employees")
    elif emp.get("max") is not None:
        parts.append(f"with up to {emp['max']} employees")
    return " ".join(parts) if (c.get("segment") or c.get("geography") or emp) else ""


def parse_objective(text: str) -> dict[str, Any]:
    """Extract target, period, direction and candidate canonical metrics from plain language."""
    from app.outcome_packs.registry import match_metrics, metric_definition

    raw = str(text or "").strip()
    lowered = raw.lower()
    target_value: float | None = None
    relative = False
    time_unit = None
    target_text = lowered
    for start, end in sorted(_constraint_spans(lowered), reverse=True):
        target_text = target_text[:start] + " " * (end - start) + target_text[end:]
    match = _NUMBER.search(target_text)
    if match:
        number = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix == "k":
            number *= 1_000
        elif suffix == "m":
            number *= 1_000_000
        relative = suffix in {"%", "percent"}
        target_value = number
        after = target_text[match.end():match.end() + 12].strip()
        time_unit = next((u for u in _TIME_UNITS if after.startswith(u)), None)
    period = next((p for pattern, p in _PERIOD_PATTERNS if re.search(pattern, lowered)), None)
    direction_hint = "decrease" if any(w in lowered for w in _DECREASE_WORDS) else None

    candidates = []
    for key, score in match_metrics(raw, limit=4):
        definition = metric_definition(key) or {}
        candidates.append({"metricKey": key, "label": definition.get("label") or key, "score": round(score, 3)})
    return {
        "statement": raw,
        "target": target_value,
        "relative": relative,
        "period": period,
        "directionHint": direction_hint,
        "timeUnit": time_unit,
        "candidates": candidates,
        "constraints": extract_constraints(raw),
    }


def looks_like_objective(text: str) -> bool:
    """A business objective names an outcome metric and an ambition, not a lookup."""
    lowered = f" {str(text or '').lower()} "
    if "?" in lowered and not any(v in lowered for v in ("help me", "can you help", "how do i", "how can we")):
        return False
    if not any(v in lowered for v in _GOAL_VERBS):
        return False
    parsed = parse_objective(text)
    if not parsed["candidates"]:
        return False
    top = parsed["candidates"][0]
    return bool(parsed["target"] is not None or parsed["period"] or top["score"] >= 1.5)


# --------------------------------------------------------------------------- contract


def _definition_for(client: Any, org_id: str, metric_key: str) -> dict[str, Any]:
    from app.outcome_packs.registry import metric_definition
    from app.services.cognitive_metrics import get_org_metric_semantics

    definition = dict(metric_definition(metric_key) or {})
    try:
        semantics = get_org_metric_semantics(client, org_id, metric_key) if client is not None else {}
    except Exception:  # noqa: BLE001
        semantics = {}
    definition["orgSemantics"] = semantics or {}
    return definition


def _baseline(client: Any, org_id: str, metric_key: str, period: str | None) -> dict[str, Any]:
    from app.services.business_metrics_service import compute_business_metrics

    range_key = PERIOD_RANGE.get(period or "month", "30d")
    try:
        row = compute_business_metrics(client, org_id, range_key=range_key, metric_keys=[metric_key])["metrics"][0]
    except Exception as exc:  # noqa: BLE001
        logger.debug("objective_baseline_failed org_id=%s metric=%s err=%s", org_id, metric_key, exc)
        row = {"value": None, "status": "insufficient_data", "reason": "The baseline could not be read."}
    return {
        "value": row.get("value"),
        "status": row.get("status"),
        "reason": row.get("reason"),
        "range": range_key,
        "verifiedResultCount": row.get("verifiedResultCount", 0),
    }


def _supporting_metrics(metric_key: str) -> list[str]:
    """Funnel metrics the same Plays move, so progress is visible before the primary metric moves."""
    from app.outcome_packs.registry import metric_definition, plays_for_metric

    seen: list[str] = []
    for _, play in plays_for_metric(metric_key):
        for key in play.kpi_keys:
            definition = metric_definition(key) or {}
            if key != metric_key and key not in seen and definition.get("verification_recipe"):
                seen.append(key)
    return seen[:6]


def build_objective_contract(
    client: Any,
    org_id: str,
    statement: str,
    *,
    metric_key: str | None = None,
    target: float | None = None,
    period: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_objective(statement)
    key = (metric_key or (parsed["candidates"][0]["metricKey"] if parsed["candidates"] else "")).strip().lower()
    if not key:
        return {
            "statement": parsed["statement"],
            "status": "needs_metric",
            "candidates": [],
            "question": (
                "Which business result should move? For example qualified leads, meetings booked, "
                "pipeline, organic clicks, ticket resolution time or retained customers."
            ),
        }
    definition = _definition_for(client, org_id, key)
    period = period or parsed["period"] or "month"
    target_value = target if target is not None else parsed["target"]
    direction = str(definition.get("direction") or "increase")
    baseline = _baseline(client, org_id, key, period)
    unit = str(definition.get("unit") or "count")
    if target_value is not None and parsed.get("timeUnit") and unit in _TO_MINUTES and target is None:
        # "4 hours" against a metric kept in minutes (or days) is converted, never misread.
        target_value = target_value * _TIME_UNITS[parsed["timeUnit"]] / _TO_MINUTES[unit]
    if target_value is not None and parsed["relative"]:
        if isinstance(baseline["value"], (int, float)):
            factor = target_value / 100.0
            absolute = baseline["value"] * (1 - factor if direction == "decrease" else 1 + factor)
        else:
            absolute = None  # a % change needs a verified baseline before it becomes a number
    else:
        absolute = target_value
    gap = None
    if isinstance(absolute, (int, float)) and isinstance(baseline["value"], (int, float)):
        gap = (baseline["value"] - absolute) if direction == "decrease" else (absolute - baseline["value"])
        gap = max(gap, 0.0)
    definition_text = definition.get("definition_prompt") or definition.get("description") or definition.get("label")
    org_override = bool((definition.get("orgSemantics") or {}).get("qualifying_values"))
    return {
        "statement": parsed["statement"],
        "status": "proposed",
        "metricKey": key,
        "metricLabel": definition.get("label") or key,
        "unit": definition.get("unit") or "count",
        "direction": direction,
        "definition": definition_text,
        "definitionSource": "org" if org_override else "platform",
        "definitionConfirmed": org_override,
        "sourceSystem": definition.get("source_system"),
        "sourceRecordType": definition.get("source_record_type"),
        "verificationRecipe": definition.get("verification_recipe"),
        "target": {
            "value": absolute,
            "requested": target_value,
            "relative": parsed["relative"],
            "period": period,
        },
        "baseline": baseline,
        "gap": gap,
        "successMetrics": [key, *_supporting_metrics(key)],
        "alternatives": [c for c in parsed["candidates"] if c["metricKey"] != key],
        # Who the objective is about (ICP filters). Execution steps receive them
        # as parameters; they never change which metric or verification applies.
        "constraints": constraints if constraints is not None else parsed["constraints"],
    }


# --------------------------------------------------------------------------- context + resources


def org_context(client: Any, org_id: str, *, environment_name: str = "production", settings: Any = None) -> dict[str, Any]:
    from app.capabilities.registry import connected_vendors
    from app.services.capability_availability import load_blocks, web_research_available

    try:
        connected = sorted(connected_vendors(client, org_id, environment_name))
    except Exception:  # noqa: BLE001
        connected = []
    blocks = load_blocks(client, org_id)
    installs: dict[str, dict[str, Any]] = {}
    try:
        rows = (
            client.table("play_installations")
            .select("id, play_key, operating_mode, status")
            .eq("org_id", org_id)
            .eq("environment_name", environment_name)
            .limit(500)
            .execute()
            .data
            or []
        )
        installs = {str(r.get("play_key")): r for r in rows if r.get("play_key")}
    except Exception:  # noqa: BLE001
        installs = {}
    tier = None
    if settings is not None:
        try:
            from app.middleware.entitlements import resolve_entitlements

            tier = resolve_entitlements(settings, org_id).get("tier")
        except Exception:  # noqa: BLE001
            tier = None
    return {
        "connected": connected,
        "blocks": blocks,
        "playInstallations": installs,
        "webResearch": web_research_available(settings),
        "plan": tier,
    }


def _readable_vendor(vendor: str) -> str:
    names = {
        "pdl": "People Data Labs", "gravitre": "web research", "hubspot": "HubSpot", "linkedin": "LinkedIn",
        "google_search_console": "Google Search Console", "google_analytics": "Google Analytics",
        "quickbooks": "QuickBooks", "zendesk": "Zendesk", "freshservice": "Freshservice", "netsuite": "NetSuite",
        "salesforce": "Salesforce", "pagerduty": "PagerDuty", "connectwise": "ConnectWise",
    }
    return names.get(vendor, vendor.replace("_", " ").title())


def _join_names(vendors: list[str]) -> str:
    names = [_readable_vendor(v) for v in vendors]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def _group_resolution(
    group: list[str],
    *,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one OR group of capabilities to the best available provider.

    Every provider the capability supports is evaluated on the readiness ladder
    (supported, connected, authorized, entitled, healthy, executable). Only an
    executable provider is selected; better-ranked providers that are supported
    but not connected become optional improvements the plan can mention, and
    connected providers refused by plan, auth or health stay visible as skipped
    so the plan can say why they were not used.
    """
    from app.capability_ontology.registry import get_capability
    from app.services.capability_availability import provider_states

    skipped: list[dict[str, Any]] = []
    connect_options: list[str] = []
    providers: list[dict[str, Any]] = []
    for capability_id in group:
        definition = get_capability(capability_id)
        if definition is None:
            continue
        states = provider_states(
            capability_id,
            connected=context["connected"],
            blocks=context["blocks"],
            web_research=bool(context.get("webResearch")),
        )
        providers.extend({**p, "capability": capability_id} for p in states)
        skipped.extend(
            {"vendor": p["vendor"], "action": p["action"], "state": p["blockedState"], "reason": p["reason"], "capability": capability_id}
            for p in states
            if p["supported"] and p["connected"] and not p["executable"] and p["blockedState"]
        )
        executable = [p for p in states if p["executable"] and not p["builtin"]]
        improvements: list[str] = []
        for p in states:
            if executable and p is executable[0]:
                break
            if p["supported"] and not p["builtin"] and p["state"] == "not_connected" and p["vendor"] not in improvements:
                improvements.append(p["vendor"])
        if executable:
            chosen = executable[0]
            return {
                "group": list(group),
                "status": "ready",
                "capability": capability_id,
                "vendor": chosen["vendor"],
                "action": chosen["action"],
                "alternatives": [p["vendor"] for p in executable[1:]],
                "skipped": skipped,
                "improvements": improvements,
                "providers": providers,
                "writable": definition.kind == "write",
            }
        connect_options.extend(
            p["vendor"] for p in states if p["supported"] and not p["builtin"] and p["vendor"] not in connect_options
        )
    for capability_id in group:
        research = next(
            (p for p in providers if p["capability"] == capability_id and p["builtin"] and p["executable"]), None
        )
        if research is not None:
            return {
                "group": list(group),
                "status": "research",
                "capability": capability_id,
                "vendor": "gravitre",
                "action": research["action"],
                "alternatives": [],
                "skipped": skipped,
                "improvements": [v for v in connect_options if v not in {s["vendor"] for s in skipped}][:6],
                "providers": providers,
                "writable": False,
            }
    return {
        "group": list(group),
        "status": "blocked" if skipped else "missing",
        "capability": group[0] if group else None,
        "vendor": None,
        "action": None,
        "alternatives": [],
        "skipped": skipped,
        "improvements": [],
        "providers": providers,
        "connectOptions": connect_options[:6],
        "writable": False,
    }


def _approvals_for(play: Any) -> list[dict[str, Any]]:
    out = []
    for item in play.write_actions:
        cap = str(item.get("capability") or item.get("action") or "")
        approval = str(item.get("approval") or "policy")
        out.append({"capability": cap, "approval": "always" if approval == "always" else "policy"})
    for step in play.workflow_steps:
        if str(step.get("type") or "") == "approval":
            out.append({"capability": str(step.get("id")), "approval": "always"})
    return out


def discover_resources(
    client: Any,
    org_id: str,
    contract: dict[str, Any],
    *,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Every Play that can move the objective's metrics, resolved against this org."""
    from app.outcome_packs.registry import get_recipe, metric_definition, plays_for_metric

    primary = str(contract.get("metricKey") or "")
    metrics = list(contract.get("successMetrics") or [primary])
    seen: set[str] = set()
    resources: list[dict[str, Any]] = []
    for metric in metrics:
        for pack, play in plays_for_metric(metric):
            if play.key in seen:
                continue
            seen.add(play.key)
            groups = [_group_resolution(list(g), context=context) for g in play.capability_groups]
            connector_groups = []
            for group in play.required_connector_groups:
                hit = next((v for v in group if v in context["connected"]), None)
                connector_groups.append({"anyOf": list(group), "connected": hit})
            statuses = {g["status"] for g in groups}
            connectors_ok = all(c["connected"] for c in connector_groups)
            if not connectors_ok or statuses & {"blocked", "missing"}:
                status = "blocked"
            elif "research" in statuses:
                status = "degraded"
            else:
                status = "ready"
            recipes = []
            measure = []
            for key in play.kpi_keys:
                recipe_key = (metric_definition(key) or {}).get("verification_recipe")
                found = get_recipe(recipe_key) if recipe_key else None
                if found and recipe_key not in recipes:
                    recipes.append(recipe_key)
                    _, recipe = found
                    measure.append(
                        {
                            "recipe": recipe.key,
                            "sourceSystem": recipe.source_system,
                            "afterHours": recipe.measure_after_hours,
                            "windowDays": recipe.measure_window_days,
                        }
                    )
            install = context["playInstallations"].get(play.key) or {}
            resources.append(
                {
                    "playKey": play.key,
                    "name": play.name,
                    "objective": play.objective or play.description,
                    "packId": pack.pack_id,
                    "department": pack.department,
                    "kpiKeys": list(play.kpi_keys),
                    "movesPrimary": primary in play.kpi_keys,
                    "status": status,
                    "capabilities": groups,
                    "connectorGroups": connector_groups,
                    "approvals": _approvals_for(play),
                    "measurement": measure,
                    "installation": {
                        "id": install.get("id"),
                        "operatingMode": install.get("operating_mode"),
                        "status": install.get("status"),
                    }
                    if install
                    else None,
                }
            )
    return resources


def compose(resources: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    """Run the objective capability composer over this org's real resources."""
    from app.capability_ontology.registry import get_capability
    required: set[str] = set()
    write_caps: set[str] = set()
    for resource in resources:
        if resource["status"] == "blocked":
            continue
        for group in resource["capabilities"]:
            if group.get("capability"):
                required.add(group["capability"])
                definition = get_capability(group["capability"])
                if definition is not None and definition.kind == "write":
                    write_caps.add(group["capability"])
    return compose_capability_resources(
        required_capabilities=required,
        resources=capability_resources(context, required),
        write_capabilities=write_caps,
    )


def capability_resources(context: dict[str, Any], capabilities: set[str]) -> list[Any]:
    """Connected providers (and built-in web research) as composer resources."""
    from app.capability_ontology.registry import get_capability
    from app.services.capability_availability import _binds_web_research, ordered_alternatives
    by_vendor: dict[str, dict[str, set[str]]] = {}
    for capability_id in capabilities:
        definition = get_capability(capability_id)
        if definition is None:
            continue
        usable, _ = ordered_alternatives(capability_id, connected=context["connected"], blocks=context["blocks"])
        for vendor, _action in usable:
            entry = by_vendor.setdefault(vendor, {"caps": set(), "write": set()})
            entry["caps"].add(capability_id)
            if definition.kind == "write":
                entry["write"].add(capability_id)
    resources = [
        CapabilityResource(
            resource_id=f"connector:{vendor}",
            kind="connector",
            capabilities=frozenset(entry["caps"]),
            connected=True,
            writable=bool(entry["write"]),
            verified=True,
            priority=10,
        )
        for vendor, entry in sorted(by_vendor.items())
    ]
    if context.get("webResearch"):
        research = frozenset(c for c in capabilities if _binds_web_research(c))
        if research:
            resources.append(
                CapabilityResource(
                    resource_id="internet:gravitre-web-research",
                    kind="internet",
                    capabilities=research,
                    connected=True,
                    writable=False,
                    verified=False,
                    priority=90,
                )
            )
    return resources


# --------------------------------------------------------------------------- feasibility + plan


def assess_feasibility(contract: dict[str, Any], resources: list[dict[str, Any]], composition: dict[str, Any]) -> dict[str, Any]:
    direct = [r for r in resources if r["movesPrimary"] and r["status"] in {"ready", "degraded"}]
    supporting = [r for r in resources if not r["movesPrimary"] and r["status"] in {"ready", "degraded"}]
    blocked = [r for r in resources if r["status"] == "blocked"]
    constraints: list[dict[str, Any]] = []
    if not contract.get("definitionConfirmed"):
        constraints.append({"kind": "definition", "message": f"Confirm how a result counts: {contract.get('definition')}"})
    baseline = contract.get("baseline") or {}
    if baseline.get("value") is None:
        constraints.append(
            {
                "kind": "baseline_unknown",
                "message": "There is no verified baseline yet, so the gap to the target is unknown until results are measured.",
            }
        )
    for resource in blocked:
        for group in resource["capabilities"]:
            if group["status"] == "blocked":
                reasons = ", ".join(f"{_readable_vendor(s['vendor'])} ({s['state'].replace('_', ' ')})" for s in group["skipped"])
                constraints.append({"kind": "provider_unavailable", "play": resource["playKey"], "message": f"{resource['name']}: {reasons}."})
            elif group["status"] == "missing":
                options = _join_names(list(group.get("connectOptions") or [])) if group.get("connectOptions") else "a supported system"
                constraints.append(
                    {"kind": "connect", "play": resource["playKey"], "message": f"{resource['name']} needs {options} connected."}
                )
        for group in resource["connectorGroups"]:
            if not group["connected"]:
                constraints.append(
                    {"kind": "connect", "play": resource["playKey"], "message": f"{resource['name']} needs {_join_names(list(group['anyOf']))} connected."}
                )
    degraded = [r for r in resources if r["status"] == "degraded"]
    if degraded:
        constraints.append(
            {
                "kind": "degraded",
                "message": "Some research runs on public web results instead of a data provider, so lists need review before outreach.",
            }
        )
    lags = [m["afterHours"] for r in direct for m in r["measurement"]]
    if lags:
        constraints.append(
            {
                "kind": "measurement_lag",
                "message": f"Results count only after the source system confirms them, at least {min(lags)} hours after each action.",
            }
        )
    if direct:
        verdict = "achievable_plan"
    elif supporting:
        verdict = "partial"
    else:
        verdict = "blocked"
    return {
        "verdict": verdict,
        "targetIsNotAPromise": True,
        "explanation": (
            "The target is what the plan aims for, not a guarantee. Progress counts only results "
            "re-read from the source system, and the plan is re-checked as results come in."
        ),
        "directPlays": len(direct),
        "supportingPlays": len(supporting),
        "blockedPlays": len(blocked),
        "constraints": constraints,
        "composition": {
            "ready": composition.get("ready"),
            "missingCapabilities": composition.get("missing_capabilities", []),
            "selected": [s["resource_id"] for s in composition.get("selected", [])],
        },
    }


def recommend_plan(contract: dict[str, Any], resources: list[dict[str, Any]]) -> dict[str, Any]:
    """Strongest achievable plan: direct, ready Plays first; blocked Plays become unlock steps."""
    order = {"ready": 0, "degraded": 1, "blocked": 2}
    ranked = sorted(resources, key=lambda r: (order[r["status"]], 0 if r["movesPrimary"] else 1, r["playKey"]))
    steps = []
    unlocks = []
    for resource in ranked:
        vendors = {g["capability"]: g["vendor"] for g in resource["capabilities"] if g.get("vendor")}
        actions = {g["capability"]: g["action"] for g in resource["capabilities"] if g.get("action")}
        if resource["status"] == "blocked":
            unlocks.append({"playKey": resource["playKey"], "name": resource["name"]})
            continue
        steps.append(
            {
                "playKey": resource["playKey"],
                "name": resource["name"],
                "why": resource["objective"],
                "movesPrimary": resource["movesPrimary"],
                "status": resource["status"],
                "capabilityVendors": vendors,
                "capabilityActions": actions,
                "approvals": resource["approvals"],
                "measurement": resource["measurement"],
            }
        )
    return {
        "steps": steps,
        "unlocks": unlocks,
        "capabilityLedger": capability_ledger(resources),
        "cadence": {"measure": "daily", "replanEveryDays": REPLAN_EVERY.days},
        "requiresApproval": any(a["approval"] == "always" for s in steps for a in s["approvals"]),
    }


def plan_objective(
    client: Any,
    org_id: str,
    statement: str,
    *,
    metric_key: str | None = None,
    target: float | None = None,
    period: str | None = None,
    environment_name: str = "production",
    settings: Any = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = build_objective_contract(
        client, org_id, statement, metric_key=metric_key, target=target, period=period, constraints=constraints
    )
    if contract.get("status") == "needs_metric":
        return {"contract": contract, "resources": [], "feasibility": None, "plan": None, "summary": contract["question"]}
    context = org_context(client, org_id, environment_name=environment_name, settings=settings)
    resources = discover_resources(client, org_id, contract, context=context)
    composition = compose(resources, context)
    feasibility = assess_feasibility(contract, resources, composition)
    plan = recommend_plan(contract, resources)
    plan["audience"] = safe_normalize_stored_dict(contract.get("constraints"))
    return {
        "_context": context,
        "contract": contract,
        "context": {
            "connected": context["connected"],
            "unavailableProviders": [
                {"vendor": b.vendor, "action": b.action, "state": b.state} for b in context["blocks"]
            ],
            "webResearch": context["webResearch"],
            "plan": context["plan"],
        },
        "resources": resources,
        "feasibility": feasibility,
        "plan": plan,
        "summary": summarize(contract, feasibility, plan),
    }


# --------------------------------------------------------------------------- conversation objective

_REVISION_MARKERS = (
    "actually", "make that", "make it", "instead", "only ", "change ", "switch", "rather", "wait",
    "limit ", "focus on", "just ", "no,", "no ", "narrow", "target ", "update ", "let's do", "lets do",
)


def objective_state(brief: dict[str, Any], *, prior: dict[str, Any] | None = None, change: str | None = None) -> dict[str, Any]:
    """Compact, surface-neutral record of the conversation's objective for task_state.

    Text, voice and agent turns all write and read this same record, so a follow-up
    on any surface revises one objective rather than creating a parallel one.
    """
    contract = brief.get("contract") or {}
    plan = brief.get("plan") or {}
    revision = int((prior or {}).get("revision") or 0) + 1
    history = list((prior or {}).get("history") or [])[-5:]
    history.append({"revision": revision, "change": change or "created", "at": _now().isoformat()})
    return {
        "statement": contract.get("statement"),
        "metricKey": contract.get("metricKey"),
        "metricLabel": contract.get("metricLabel"),
        "target": contract.get("target"),
        "constraints": contract.get("constraints") or {},
        "definition": contract.get("definition"),
        "verificationRecipe": contract.get("verificationRecipe"),
        "sourceSystem": contract.get("sourceSystem"),
        "baseline": contract.get("baseline"),
        "feasibility": (brief.get("feasibility") or {}).get("verdict"),
        "planSteps": [s.get("playKey") for s in plan.get("steps") or []],
        "unlocks": [u.get("playKey") for u in plan.get("unlocks") or []],
        "capabilityLedger": plan.get("capabilityLedger") or {},
        "requiresApproval": bool(plan.get("requiresApproval")),
        "objectiveId": (prior or {}).get("objectiveId") or brief.get("objectiveId"),
        "revision": revision,
        "history": history,
    }


def is_objective_revision(text: str, active: dict[str, Any] | None) -> bool:
    """A follow-up that changes the active objective's audience, target or period.

    A sentence that states a different business metric is a new objective, not a
    revision. A question or chit-chat is neither.
    """
    if not isinstance(active, dict) or not active.get("metricKey"):
        return False
    lowered = f" {str(text or '').lower().strip()} "
    parsed = parse_objective(text)
    if parsed["candidates"] and looks_like_objective(text):
        top = parsed["candidates"][0]
        if top["metricKey"] != active.get("metricKey") and top["score"] >= 1.5:
            return False
    if not any(marker in lowered for marker in _REVISION_MARKERS):
        return False
    return bool(parsed["constraints"] or parsed["target"] is not None or parsed["period"])


def _describe_change(before: dict[str, Any], after: dict[str, Any]) -> str:
    parts: list[str] = []
    if (before.get("constraints") or {}) != (after.get("constraints") or {}):
        who = describe_constraints(after.get("constraints"))
        parts.append(f"audience is now {who}" if who else "audience constraints were cleared")
    if (before.get("target") or {}).get("value") != (after.get("target") or {}).get("value"):
        parts.append(f"target is now {_fmt((after.get('target') or {}).get('value'), after.get('unit'))}")
    if (before.get("target") or {}).get("period") != (after.get("target") or {}).get("period"):
        parts.append(f"period is now per {(after.get('target') or {}).get('period')}")
    return "; ".join(parts) or "no material change"


def revise_objective(
    client: Any,
    org_id: str,
    active: dict[str, Any],
    text: str,
    *,
    environment_name: str = "production",
    settings: Any = None,
) -> dict[str, Any]:
    """Apply a correction to the active objective, preserving everything it does not name."""
    parsed = parse_objective(text)
    prior_constraints = safe_normalize_stored_dict(active.get("constraints"))
    merged = {**prior_constraints, **parsed["constraints"]}
    prior_target = active.get("target") or {}
    if parsed["target"] is not None:
        target = parsed["target"]
    else:
        target = prior_target.get("requested") if prior_target.get("relative") else prior_target.get("value")
    brief = plan_objective(
        client,
        org_id,
        str(active.get("statement") or ""),
        metric_key=active.get("metricKey"),
        target=target,
        period=parsed["period"] or prior_target.get("period"),
        environment_name=environment_name,
        settings=settings,
        constraints=merged,
    )
    before = {"constraints": prior_constraints, "target": prior_target}
    change = _describe_change(before, brief.get("contract") or {})
    brief["revision"] = {"change": change, "text": str(text or "")[:300], "preserved": sorted(
        k for k in ("metricKey", "definition", "verificationRecipe", "sourceSystem")
        if (brief.get("contract") or {}).get(k) == active.get(k)
    )}
    return brief


def public_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """The brief without the planner-only raw context."""
    return {k: v for k, v in brief.items() if not k.startswith("_")}


def _fmt(value: Any, unit: str | None) -> str:
    if value is None:
        return "unknown"
    number = float(value)
    text = f"{number:,.0f}" if abs(number) >= 10 or number == int(number) else f"{number:,.2f}"
    if unit == "currency":
        return f"${text}"
    if unit in {"percent"}:
        return f"{text}%"
    if unit in {"minutes", "hours", "days"}:
        return f"{text} {unit}"
    return text


_REFUSAL_WORDS = {
    "plan_limit": "its current plan does not include this action",
    "auth_expired": "its connection needs to be re-authorized",
    "permission_denied": "it is missing a required permission",
    "rate_limited": "it is rate limited right now",
    "unhealthy": "it is not responding right now",
}


def capability_ledger(resources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One row per capability the plan needs: chosen provider, refused, fallbacks, optional improvements.

    This is the modality-neutral record of capability reasoning that text, voice,
    Plays and scheduled replans all read, so the same tenant state yields the
    same provider decisions on every surface.
    """
    ledger: dict[str, dict[str, Any]] = {}
    for resource in resources:
        for group in resource.get("capabilities") or []:
            cap = group.get("capability")
            if not cap or cap in ledger:
                continue
            ledger[cap] = {
                "status": group.get("status"),
                "selected": group.get("vendor"),
                "alternatives": list(group.get("alternatives") or []),
                "refused": sorted({f"{s['vendor']}:{s['state']}" for s in group.get("skipped") or []}),
                "improvements": list(group.get("improvements") or []),
                "connectOptions": list(group.get("connectOptions") or []),
                "states": {
                    p["vendor"]: p["state"] for p in group.get("providers") or [] if p.get("capability") == cap
                },
            }
    return ledger


def provider_notes(plan: dict[str, Any]) -> list[str]:
    """Plain-language notes on refused providers and optional improvements (no ids, no action keys)."""
    from app.capability_ontology.registry import get_capability

    notes: list[str] = []
    seen: set[str] = set()
    for item in plan.get("capabilityLedger", {}).items() if isinstance(plan.get("capabilityLedger"), dict) else []:
        cap, row = item
        definition = get_capability(cap)
        label = (definition.label if definition else cap).lower()
        for refused in row.get("refused") or []:
            vendor, _, state = refused.partition(":")
            key = f"refused:{vendor}:{state}"
            if key in seen:
                continue
            seen.add(key)
            instead = row.get("selected")
            tail = (
                f", so I'm using {_readable_vendor(instead)} to {label} instead."
                if instead
                else f", and nothing else can {label} right now."
            )
            notes.append(f"{_readable_vendor(vendor)} is connected, but {_REFUSAL_WORDS.get(state, 'it is unavailable')}{tail}")
        improvements = list(row.get("improvements") or [])[:3]
        if improvements and row.get("status") in {"research", "ready"}:
            key = f"improve:{','.join(improvements)}:{row.get('selected')}"
            if key in seen:
                continue
            seen.add(key)
            notes.append(
                f"Optional: connecting {_join_names(improvements)} would give stronger results than "
                f"{_readable_vendor(row.get('selected') or '')} to {label}."
            )
    return notes[:4]


def summarize(contract: dict[str, Any], feasibility: dict[str, Any], plan: dict[str, Any]) -> str:
    """Plain-language brief for the chat answer (no ids, no tool names)."""
    label = str(contract.get("metricLabel") or "the result").lower()
    unit = contract.get("unit")
    target = (contract.get("target") or {}).get("value")
    period = (contract.get("target") or {}).get("period") or "month"
    baseline = (contract.get("baseline") or {}).get("value")
    tgt = contract.get("target") or {}
    aggregation = "avg" if unit in {"minutes", "hours", "days", "position", "percent", "score", "ratio"} else "sum"
    more = "lower" if contract.get("direction") == "decrease" else "more"
    if target is not None and aggregation == "avg":
        lines = [f"Goal: {label} of {_fmt(target, unit)}, measured over each {period}."]
    elif target is not None:
        lines = [f"Goal: {_fmt(target, unit)} {label} per {period}."]
    elif tgt.get("relative") and tgt.get("requested") is not None:
        lines = [f"Goal: {_fmt(tgt['requested'], None)}% {more} {label} per {period}, set against the baseline once it is verified."]
    elif aggregation == "avg":
        better = "lower" if contract.get("direction") == "decrease" else "higher"
        lines = [f"Goal: a {better} {label}, measured over each {period}."]
    else:
        lines = [f"Goal: {more} {label} per {period}."]
    who = describe_constraints(contract.get("constraints"))
    if who:
        lines.append(f"Who: {who}.")
    lines.append(f"How it counts: {contract.get('definition')}")
    if baseline is None:
        lines.append("Baseline: unknown, because nothing has been verified in the source system yet.")
    else:
        gap = contract.get("gap")
        lines.append(f"Baseline: {_fmt(baseline, unit)} in the last {period}; gap {_fmt(gap, unit)}.")
    ready = [s for s in plan["steps"] if s["movesPrimary"]][:3] or plan["steps"][:3]
    if ready:
        lines.append("Plan: " + "; ".join(s["name"] for s in ready) + ".")
    for c in feasibility["constraints"][:3]:
        if c["kind"] in {"provider_unavailable", "connect", "degraded"}:
            lines.append(c["message"])
    lines.extend(provider_notes(plan))
    lines.append(feasibility["explanation"])
    if plan.get("requiresApproval"):
        lines.append("Every write to your systems waits for your approval.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- persistence, progress, replan

GOAL_CATEGORY = "objective"


def save_objective(client: Any, org_id: str, brief: dict[str, Any], *, status: str = "draft") -> dict[str, Any]:
    """Persist on goals/goal_plans: the contract lives in goals.success_metrics, the plan in goal_plans."""
    contract = brief["contract"]
    plan = brief.get("plan") or {}
    now = _now().isoformat()
    goal = (
        client.table("goals")
        .insert(
            {
                "org_id": org_id,
                "objective": contract["statement"][:800],
                "category": GOAL_CATEGORY,
                "department": next((r["department"] for r in brief.get("resources") or [] if r.get("movesPrimary")), None),
                "success_metrics": {"contract": contract, "planned_at": now},
                "connected_systems": list((brief.get("context") or {}).get("connected") or []),
                "status": status,
                "created_at": now,
                "updated_at": now,
            }
        )
        .execute()
        .data
        or [{}]
    )[0]
    goal_id = str(goal.get("id") or "")
    _save_plan(client, org_id, goal_id, brief, revision=1, reason="initial")
    return {"objectiveId": goal_id, **public_brief(brief)}


def _save_plan(client: Any, org_id: str, goal_id: str, brief: dict[str, Any], *, revision: int, reason: str) -> None:
    plan = brief.get("plan") or {}
    connectors = sorted({v for s in plan.get("steps") or [] for v in s["capabilityVendors"].values() if v and v != "gravitre"})
    client.table("goal_plans").insert(
        {
            "org_id": org_id,
            "goal_id": goal_id,
            "proposed_steps": plan.get("steps") or [],
            "required_connectors": connectors,
            "approval_gates": [a for s in plan.get("steps") or [] for a in s["approvals"]],
            "estimated_impact": {
                "feasibility": brief.get("feasibility"),
                "unlocks": plan.get("unlocks") or [],
                "revision": revision,
                "reason": reason,
                "planned_at": _now().isoformat(),
            },
        }
    ).execute()


def load_objective(client: Any, org_id: str, objective_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("goals").select("*").eq("org_id", org_id).eq("id", objective_id).eq("category", GOAL_CATEGORY).limit(1).execute().data
        or []
    )
    if not rows:
        return None
    goal = dict(rows[0])
    plans = (
        client.table("goal_plans").select("*").eq("org_id", org_id).eq("goal_id", objective_id).order("created_at", desc=True).limit(20).execute().data
        or []
    )
    plans.sort(key=lambda p: int(((p.get("estimated_impact") or {}).get("revision") or 0)), reverse=True)
    goal["plan"] = plans[0] if plans else None
    goal["planHistory"] = [
        {"revision": (p.get("estimated_impact") or {}).get("revision"), "reason": (p.get("estimated_impact") or {}).get("reason")}
        for p in plans
    ]
    return goal


def objective_progress(client: Any, org_id: str, objective_id: str) -> dict[str, Any] | None:
    """Verified progress on the objective's canonical metrics, plus what this objective's Plays verified."""
    from app.plays.impact import counts_in_total
    from app.plays.outcomes import list_play_business_results
    from app.services.business_metrics_service import compute_business_metrics

    goal = load_objective(client, org_id, objective_id)
    if goal is None:
        return None
    contract = ((goal.get("success_metrics") or {}).get("contract")) or {}
    period = (contract.get("target") or {}).get("period") or "month"
    keys = list(contract.get("successMetrics") or [contract.get("metricKey")])
    metrics = compute_business_metrics(client, org_id, range_key=PERIOD_RANGE.get(period, "30d"), metric_keys=keys)["metrics"]
    attributed: dict[str, float] = {}
    pending = 0
    for row in list_play_business_results(client, org_id, limit=5000, since=goal.get("created_at"), max_limit=5000):
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if str(meta.get("objective_id") or "") != objective_id:
            continue
        state = str(meta.get("verification_state") or "")
        if state == "ACTIONED":
            pending += 1
        elif state == "VERIFIED SUCCESS" and counts_in_total(meta) and isinstance(meta.get("delta_value"), (int, float)):
            key = str(meta.get("metric_key") or "")
            attributed[key] = attributed.get(key, 0.0) + float(meta["delta_value"])
    primary = next((m for m in metrics if m["metricKey"] == contract.get("metricKey")), None) or {}
    target = (contract.get("target") or {}).get("value")
    value = primary.get("value")
    return {
        "objectiveId": objective_id,
        "statement": goal.get("objective"),
        "status": goal.get("status"),
        "metricKey": contract.get("metricKey"),
        "target": target,
        "period": period,
        "current": value,
        "currentStatus": primary.get("status"),
        "remaining": (max(float(target) - float(value), 0.0) if contract.get("direction") != "decrease" else max(float(value) - float(target), 0.0))
        if isinstance(target, (int, float)) and isinstance(value, (int, float))
        else None,
        "metrics": metrics,
        "attributedToObjective": attributed,
        "actionsAwaitingVerification": pending,
        "plan": (goal.get("plan") or {}).get("proposed_steps") or [],
        "planHistory": goal.get("planHistory") or [],
        "truthRule": "Only results re-read from the source system count. Unknown is shown as unknown, never zero.",
    }


def replan_objective(
    client: Any,
    org_id: str,
    objective_id: str,
    *,
    environment_name: str = "production",
    settings: Any = None,
    reason: str = "scheduled",
    force: bool = False,
) -> dict[str, Any] | None:
    """Re-resolve resources against current availability; save a new plan revision when it changed."""
    goal = load_objective(client, org_id, objective_id)
    if goal is None:
        return None
    contract = ((goal.get("success_metrics") or {}).get("contract")) or {}
    previous = (goal.get("plan") or {}).get("proposed_steps") or []
    revision = int((((goal.get("plan") or {}).get("estimated_impact") or {}).get("revision")) or 1)
    target = (contract.get("target") or {})
    brief = plan_objective(
        client,
        org_id,
        contract.get("statement") or goal.get("objective") or "",
        metric_key=contract.get("metricKey"),
        target=target.get("value") if not target.get("relative") else target.get("requested"),
        period=target.get("period"),
        environment_name=environment_name,
        settings=settings,
        constraints=contract.get("constraints"),
    )
    new_steps = (brief.get("plan") or {}).get("steps") or []
    before = {s["playKey"]: s.get("capabilityVendors") for s in previous}
    after = {s["playKey"]: s.get("capabilityVendors") for s in new_steps}
    changes = []
    for key in sorted(set(before) | set(after)):
        if key not in after:
            changes.append({"playKey": key, "change": "removed"})
        elif key not in before:
            changes.append({"playKey": key, "change": "added"})
        elif before[key] != after[key]:
            changes.append({"playKey": key, "change": "providers", "before": before[key], "after": after[key]})
    if changes or force:
        _save_plan(client, org_id, objective_id, brief, revision=revision + 1, reason=reason)
    return {"objectiveId": objective_id, "changed": bool(changes), "changes": changes, "revision": revision + (1 if changes or force else 0), **public_brief(brief)}


def replan_due_objectives(
    client: Any,
    *,
    settings: Any = None,
    org_id: str | None = None,
    now: datetime | None = None,
    limit: int = 50,
) -> dict[str, int]:
    """Scheduled sweep: replan active objectives whose plan is stale or whose providers became unavailable."""
    now = now or _now()
    try:
        q = client.table("goals").select("id, org_id, status, updated_at").eq("category", GOAL_CATEGORY).eq("status", "active")
        if org_id:
            q = q.eq("org_id", org_id)
        goals = q.limit(limit).execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("objective_replan_scan_failed err=%s", exc)
        return {"scanned": 0, "replanned": 0}
    from app.services.capability_availability import load_blocks

    replanned = 0
    for goal in goals:
        goal_org = str(goal.get("org_id") or "")
        try:
            current = load_objective(client, goal_org, str(goal["id"]))
            plan = (current or {}).get("plan") or {}
            planned_at = str(((plan.get("estimated_impact") or {}).get("planned_at")) or "")
            stale = not planned_at or planned_at < (now - REPLAN_EVERY).isoformat()
            active_blocks = load_blocks(client, goal_org, now=now)
            blocked = {b.vendor for b in active_blocks if b.action == "*"}
            blocked_actions = {b.action for b in active_blocks if b.action != "*"}
            uses_blocked = any(
                v in blocked for s in plan.get("proposed_steps") or [] for v in (s.get("capabilityVendors") or {}).values()
            ) or any(
                a in blocked_actions for s in plan.get("proposed_steps") or [] for a in (s.get("capabilityActions") or {}).values()
            )
            if stale or uses_blocked:
                result = replan_objective(client, goal_org, str(goal["id"]), settings=settings, reason="provider_unavailable" if uses_blocked else "scheduled", force=stale)
                replanned += 1 if result and (result["changed"] or stale) else 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("objective_replan_failed goal_id=%s err=%s", goal.get("id"), exc)
    return {"scanned": len(goals), "replanned": replanned}


def execution_requests(goal_plan_steps: list[dict[str, Any]], installations: dict[str, dict[str, Any]], objective_id: str) -> list[dict[str, Any]]:
    """What each plan step needs before it can run under the canonical Play runtime."""
    out = []
    for step in goal_plan_steps:
        install = installations.get(step["playKey"]) or {}
        mode = str(install.get("operating_mode") or "")
        if not install:
            state = "needs_setup"
        elif mode not in {"ACT WITH APPROVAL", "ACT WITHIN POLICY"}:
            state = "needs_action_mode"
        else:
            state = "runnable"
        out.append(
            {
                "playKey": step["playKey"],
                "name": step["name"],
                "state": state,
                "installationId": install.get("id"),
                "objectiveId": objective_id,
                "capabilityVendors": step.get("capabilityVendors") or {},
            }
        )
    return out


def capability_resources_for_planner(brief: dict[str, Any]) -> dict[str, Any]:
    """task_state entries the cognitive planner composes (objective_contract + capability_resources)."""
    from app.capability_ontology.registry import get_capability

    required: set[str] = set()
    writes: set[str] = set()
    for step in (brief.get("plan") or {}).get("steps") or []:
        for capability in step.get("capabilityVendors") or {}:
            required.add(capability)
            definition = get_capability(capability)
            if definition is not None and definition.kind == "write":
                writes.add(capability)
    context = brief.get("_context") or {}
    resources = [
        {
            "resource_id": r.resource_id,
            "kind": r.kind,
            "capabilities": sorted(r.capabilities),
            "connected": r.connected,
            "writable": r.writable,
            "verified": r.verified,
            "priority": r.priority,
        }
        for r in (capability_resources(context, required) if context else [])
    ]
    contract = brief.get("contract") or {}
    return {
        "objective_contract": {
            "objective": contract.get("statement"),
            "metric_key": contract.get("metricKey"),
            "required_capabilities": sorted(required),
            "write_capabilities": sorted(writes),
            "requires_write": False,
        },
        "capability_resources": resources,
    }
