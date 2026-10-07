"""Marketplace 3.0 Outcome Pack certification.

Certification is deliberately stricter than schema validation. A syntactically
valid pack may remain a blueprint, but it cannot be published as a verified
operating capability until runtime actions, governance, verification, and skill
dependencies are real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.schemas import OutcomePackAssetConfig
from app.services.tool_service import list_registered_actions
from app.services.write_success_verification import resolve_success_verification


_CERT_LEVELS = (
    "compatible",
    "tested",
    "governed",
    "production_verified",
    "outcome_verified",
)


@dataclass
class CertificationFinding:
    code: str
    message: str
    blocking: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "blocking": self.blocking,
            "metadata": self.metadata,
        }


@dataclass
class OutcomePackCertification:
    level: str
    publish_ready: bool
    findings: list[CertificationFinding]
    play_count: int
    runtime_actions: list[str]
    verified_skills: list[str]
    unresolved_skill_requirements: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "publishReady": self.publish_ready,
            "playCount": self.play_count,
            "runtimeActions": self.runtime_actions,
            "verifiedSkills": self.verified_skills,
            "unresolvedSkillRequirements": self.unresolved_skill_requirements,
            "findings": [item.as_dict() for item in self.findings],
        }


def _workflow_actions(config: OutcomePackAssetConfig) -> set[str]:
    out: set[str] = set()
    for play in config.plays:
        for step in play.workflow_steps:
            if step.get("type") != "invoke_tool":
                continue
            step_config = step.get("config")
            if not isinstance(step_config, dict):
                continue
            action = str(
                step_config.get("action")
                or step_config.get("tool_action")
                or ""
            ).strip()
            if action:
                out.add(action)
    return out


def certify_outcome_pack(
    config: OutcomePackAssetConfig,
    *,
    resolved_skill_ids: set[str] | None = None,
    outcome_evidence: dict[str, Any] | None = None,
) -> OutcomePackCertification:
    """Return the strongest certification level supported by current evidence.

    This function never turns test intent into evidence. production_verified
    requires the runtime profile itself to carry production verification state,
    and outcome_verified requires explicit measured outcome evidence.
    """
    findings: list[CertificationFinding] = []
    registered = set(list_registered_actions())
    runtime_actions = sorted(_workflow_actions(config))

    if len(config.plays) < 6:
        findings.append(
            CertificationFinding(
                "MINIMUM_PLAYS",
                "Marketplace 3.0 Outcome Packs require at least six meaningful Plays.",
            )
        )

    declared_actions = {
        action
        for profile in config.runtime_profiles
        for action in profile.actions
    }
    missing_registered = sorted(action for action in runtime_actions if action not in registered)
    if missing_registered:
        findings.append(
            CertificationFinding(
                "RUNTIME_ACTION_NOT_REGISTERED",
                "One or more workflow actions are not executable in Gravitre.",
                metadata={"actions": missing_registered},
            )
        )
    undeclared = sorted(set(runtime_actions) - declared_actions)
    if undeclared:
        findings.append(
            CertificationFinding(
                "RUNTIME_ACTION_UNDECLARED",
                "Workflow actions must belong to an explicit runtime profile.",
                metadata={"actions": undeclared},
            )
        )

    for action in sorted(declared_actions):
        spec = get_action_spec(action)
        if spec is None:
            findings.append(
                CertificationFinding(
                    "ACTION_SPEC_MISSING",
                    f"Action {action} is missing a Marketplace action specification.",
                    metadata={"action": action},
                )
            )
            continue
        if spec.kind != "read":
            if not spec.requires_approval:
                findings.append(
                    CertificationFinding(
                        "WRITE_APPROVAL_MISSING",
                        f"Write action {action} is not approval governed.",
                        metadata={"action": action},
                    )
                )
            verification = resolve_success_verification(action)
            if verification.mode == "accepted_async":
                findings.append(
                    CertificationFinding(
                        "WRITE_VERIFICATION_INCOMPLETE",
                        f"Write action {action} lacks independent source-of-record verification.",
                        metadata={"action": action, "mode": verification.mode},
                    )
                )
            if verification.mode in {"follow_up_entity_get", "follow_up_field_assert"}:
                read_action = str(verification.read_action or "").strip()
                if not read_action or read_action not in registered:
                    findings.append(
                        CertificationFinding(
                            "WRITE_VERIFICATION_READ_UNAVAILABLE",
                            f"Write verification for {action} depends on an unavailable read action.",
                            metadata={"action": action, "readAction": read_action},
                        )
                    )

    resolved_package_ids = set(resolved_skill_ids or set()) | set(config.skills)
    bound_requirements = {
        requirement
        for requirement, package_id in config.skill_bindings.items()
        if str(package_id).strip()
        and str(package_id).strip() in resolved_package_ids
    }
    unresolved_skills = sorted(
        requirement for requirement in config.skill_requirements
        if requirement not in bound_requirements
    )
    if unresolved_skills:
        findings.append(
            CertificationFinding(
                "SKILL_REQUIREMENTS_UNRESOLVED",
                "Required skill capabilities have not been resolved to reviewed Marketplace packages.",
                metadata={"requirements": unresolved_skills},
            )
        )

    runtime_statuses = {profile.status for profile in config.runtime_profiles}
    if not config.runtime_profiles:
        findings.append(
            CertificationFinding(
                "RUNTIME_PROFILE_MISSING",
                "Outcome Pack has no declared executable runtime profile.",
            )
        )

    schema_runtime_ok = not any(
        finding.code in {
            "MINIMUM_PLAYS",
            "RUNTIME_ACTION_NOT_REGISTERED",
            "RUNTIME_ACTION_UNDECLARED",
            "ACTION_SPEC_MISSING",
        }
        for finding in findings
    )
    governed_ok = schema_runtime_ok and not any(
        finding.code in {
            "WRITE_APPROVAL_MISSING",
            "WRITE_VERIFICATION_INCOMPLETE",
            "WRITE_VERIFICATION_READ_UNAVAILABLE",
        }
        for finding in findings
    )

    level = "compatible"
    if schema_runtime_ok and runtime_statuses and runtime_statuses <= {"tested", "production_verified"}:
        level = "tested"
    if governed_ok and level == "tested":
        level = "governed"
    production_ok = (
        governed_ok
        and bool(config.runtime_profiles)
        and all(profile.status == "production_verified" for profile in config.runtime_profiles)
        and not unresolved_skills
    )
    if production_ok:
        level = "production_verified"

    evidence = outcome_evidence if isinstance(outcome_evidence, dict) else {}
    observed_events = {
        str(value)
        for value in (evidence.get("verified_outcome_events") or [])
        if str(value).strip()
    }
    declared_events = set(config.outcome_contract.outcome_events)
    if production_ok and declared_events.intersection(observed_events):
        level = "outcome_verified"

    publish_ready = level in {"production_verified", "outcome_verified"}
    return OutcomePackCertification(
        level=level,
        publish_ready=publish_ready,
        findings=findings,
        play_count=len(config.plays),
        runtime_actions=runtime_actions,
        verified_skills=sorted(
            str(package_id).strip()
            for package_id in config.skill_bindings.values()
            if str(package_id).strip()
        ),
        unresolved_skill_requirements=unresolved_skills,
    )


def certification_level_rank(level: str) -> int:
    try:
        return _CERT_LEVELS.index(level)
    except ValueError:
        return -1


# =========================================================================== outcome contract certification
#
# Runs every Outcome Pack through the production outcome machinery (ACTIONED
# writer, recipe measurement, claims, business metrics, evidence chains,
# governance, capability fallback, objective planning) against an in-memory
# store with the pack's declared fixtures. Nothing here is pack specific.

CONTRACT_CHECKS = (
    ("metrics_resolve", "Canonical metrics resolve", "Metrics"),
    ("plays_map_kpis", "Plays map to canonical KPI keys", "Plays"),
    ("capabilities_resolve", "Required capabilities resolve", "Capabilities"),
    ("fallbacks_resolve", "Fallback capability groups resolve", "Fallbacks"),
    ("verification_exists", "Source-of-record verification exists", "Verification"),
    ("verified_results_produced", "VERIFIED results can be produced", "Verification"),
    ("evidence_chains_resolve", "Evidence chains resolve", "Evidence"),
    ("no_double_count", "Duplicate source records cannot double count", "Attribution"),
    ("dashboard_kpis_verified", "Dashboard KPIs resolve from verified outcomes", "Dashboard"),
    ("missing_evidence_unknown", "Missing evidence is unknown, never fabricated", "Dashboard"),
    ("dashboard_installable", "Pack dashboard installs are consumable", "Dashboard"),
    ("learning_verified_only", "Learning receives only verified business outcomes", "Learning"),
    ("governance_enforced", "Governance and approval policies are enforced", "Certification"),
    ("degraded_replans", "Degraded providers replan where alternatives exist", "Fallbacks"),
)

_CERT_ORG = "00000000-0000-4000-8000-00000000c3c7"


def _check(key: str, ok: bool | None, detail: str = "", **extra: Any) -> dict[str, Any]:
    label = next(label for k, label, _ in CONTRACT_CHECKS if k == key)
    return {"key": key, "label": label, "status": "n/a" if ok is None else ("pass" if ok else "fail"), "detail": detail, **extra}


def _simulate_play_write(store: Any, play_key: str, action: str, record_id: str, *, run_no: int) -> None:
    """A Play-bound workflow run that wrote one record, through the production ACTIONED writer."""
    from uuid import uuid4

    from app.services.execution_outcome import ExecutionOutcomeEvent, _record_play_actioned_result

    run_id = str(uuid4())
    store.table("workflow_runs").insert(
        {"id": run_id, "org_id": _CERT_ORG, "parameters": {"play": {"key": play_key, "version": "1", "run_id": f"cert-{run_no}"}}}
    ).execute()
    event = ExecutionOutcomeEvent(
        org_id=_CERT_ORG,
        status="completed",
        source="canvas",
        run_id=run_id,
        workflow_id=str(uuid4()),
        metadata={
            "connector_output_refs": [
                {"success": True, "invoke_action": action, "entity_id": record_id, "id": record_id, "params_ids": {"id": record_id}}
            ]
        },
    )
    _record_play_actioned_result(store, event, "completed", "2026-01-01T00:00:00+00:00")


def _fixture_reader(fixtures: dict[str, Any]):
    def read(recipe: Any, record_id: str, windows: dict[str, Any]) -> dict[str, Any]:
        fixture = fixtures.get(recipe.key) or {}
        return {"current": fixture.get("current"), "baseline": fixture.get("baseline")}

    return read


def certify_outcome_contract(pack: Any) -> dict[str, Any]:
    """Run the 14 contract checks for one registry Outcome Pack."""
    from datetime import datetime, timedelta, timezone

    from app.capability_ontology.registry import get_capability
    from app.connectors.action_catalog.f1_write_slice import is_always_approve_write_action
    from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
    from app.marketplace.schemas import DashboardPackAssetConfig
    from app.outcome_packs.memory_store import MemoryStore
    from app.outcome_packs.registry import (
        dashboard_templates,
        expand_group,
        metric_conflicts,
        metric_definition,
        play_write_actions,
    )
    from app.plays.evidence import build_play_evidence_chain
    from app.services.business_metrics_service import compute_business_metrics
    from app.services.capability_availability import _binds_web_research, ordered_alternatives, load_blocks, record_unavailable
    from app.services.play_outcome_measurement import measure_pending_play_results

    config = pack.config
    contract = config.outcome_contract
    kpis = {k.key: k for k in contract.kpis}
    registered = set(list_registered_actions())
    checks: list[dict[str, Any]] = []

    # 1 metrics resolve
    referenced = {k for p in config.plays for k in p.kpi_keys} | {m.kpi_key for m in config.dashboard.metrics}
    referenced |= {k for s in config.dashboard.sections for k in s.kpi_keys} | {k for o in config.objectives for k in o.kpi_keys}
    unresolved = sorted(k for k in referenced if metric_definition(k) is None)
    conflicts = [c for c in metric_conflicts() if any(c.startswith(f"{k}:") or k in c for k in kpis)]
    checks.append(_check("metrics_resolve", not unresolved and not conflicts, ", ".join(unresolved + conflicts) or f"{len(referenced)} metrics"))

    # 2 plays map to canonical KPIs
    stray = sorted({f"{p.key}:{k}" for p in config.plays for k in p.kpi_keys if k not in kpis})
    checks.append(_check("plays_map_kpis", not stray and len(config.plays) >= config.certification.minimum_plays, ", ".join(stray) or f"{len(config.plays)} Plays"))

    # 3 capabilities resolve
    missing_caps: list[str] = []
    for play in config.plays:
        for group in play.capability_groups:
            for item in group:
                if get_capability(item) is None and not catalog_tool_is_implemented(item, registered):
                    missing_caps.append(f"{play.key}:{item}")
                    continue
                actions = [a for a in expand_group([item]) if a != "gravitre.web.research"]
                if not any(catalog_tool_is_implemented(a, registered) for a in actions) and not _binds_web_research(item):
                    missing_caps.append(f"{play.key}:{item} (no registered provider)")
    checks.append(_check("capabilities_resolve", not missing_caps, ", ".join(sorted(set(missing_caps))) or "all resolve"))

    # 4 fallbacks resolve: a capability bound to several providers keeps at least two usable ones
    weak: list[str] = []
    multi = 0
    for play in config.plays:
        for group in play.capability_groups:
            providers: set[str] = set()
            bound: set[str] = set()
            for item in group:
                definition = get_capability(item)
                if definition is None:
                    continue
                bound |= {b.vendor for b in definition.bindings}
                usable, _ = ordered_alternatives(item, connected=sorted(bound), blocks=[])
                providers |= {v for v, _ in usable}
                if _binds_web_research(item):
                    providers.add("gravitre")
            if len(bound) > 1:
                multi += 1
                if len(providers) < 2:
                    weak.append(f"{play.key}:{'|'.join(group)}")
    checks.append(_check("fallbacks_resolve", None if not multi else not weak, ", ".join(sorted(set(weak))) or f"{multi} groups with alternatives"))

    # 5 verification exists
    from app.outcome_packs.registry import get_recipe

    gaps: list[str] = []

    def canonical_recipe(key: str) -> str | None:
        return (metric_definition(key) or {}).get("verification_recipe") or (kpis[key].verification_recipe if key in kpis else None)

    def verifiable_key(key: str) -> bool:
        definition = metric_definition(key) or {}
        if definition.get("aggregation") == "ratio":
            return bool(canonical_recipe(str(definition.get("numerator") or ""))) and bool(canonical_recipe(str(definition.get("denominator") or "")))
        return bool(canonical_recipe(key))

    verifiable = [k for k in kpis if verifiable_key(k)]
    for key in kpis:
        recipe_key = canonical_recipe(key)
        if recipe_key:
            found = get_recipe(recipe_key)
            if found is None or not catalog_tool_is_implemented(found[1].read_action, registered):
                gaps.append(f"{key}:{recipe_key}")
    # Read-only (analysis) Plays never write, so they produce no ACTIONED result to verify.
    acting = [p for p in config.plays if p.write_actions or p.write_action_groups]
    unverified_plays = [p.key for p in acting if not any(verifiable_key(k) for k in p.kpi_keys)]
    checks.append(_check("verification_exists", bool(verifiable) and not gaps and not unverified_plays, ", ".join(gaps + unverified_plays) or f"{len(verifiable)} verified KPIs"))

    # 6-9, 12: run the production pipeline on fixtures
    store = MemoryStore()
    fixtures = dict(config.certification.fixtures)
    recipes = [r for r in config.verification_recipes if r.key in fixtures]
    now = datetime.now(timezone.utc)
    run_no = 0
    for recipe in recipes:
        metric_keys = {c.metric_key for c in recipe.contributions}
        plays = [p for p in config.plays if metric_keys & set(p.kpi_keys)] or list(config.plays[:1])
        for play in plays[:2]:  # a second Play on the same record exercises attribution
            run_no += 1
            _simulate_play_write(store, play.key, recipe.match_actions[0], str(fixtures[recipe.key]["record_id"]), run_no=run_no)
    later = now + timedelta(hours=max([r.measure_after_hours for r in recipes] or [0]) + 1)
    first = measure_pending_play_results(store, org_id=_CERT_ORG, reader=_fixture_reader(fixtures), now=later)
    second = measure_pending_play_results(store, org_id=_CERT_ORG, reader=_fixture_reader(fixtures), now=later)
    ledger = [r for r in store.rows("intelligence_outcome_events") if r.get("outcome_event") == "play_business_result"]
    verified = [r for r in ledger if (r.get("metadata") or {}).get("verification_state") == "VERIFIED SUCCESS"]
    counted = [r for r in verified if (r.get("metadata") or {}).get("counted_in_total") is True]
    produced_recipes = {(r.get("metadata") or {}).get("recipe_key") for r in counted}
    missing_recipes = sorted(r.key for r in recipes if r.key not in produced_recipes)
    no_fixture = sorted(r.key for r in config.verification_recipes if r.key not in fixtures)
    checks.append(
        _check(
            "verified_results_produced",
            bool(recipes) and not missing_recipes and not no_fixture,
            ", ".join([f"no result: {k}" for k in missing_recipes] + [f"no fixture: {k}" for k in no_fixture]) or f"{len(counted)} verified results",
        )
    )

    chains_ok = bool(counted)
    for row in counted:
        chain = build_play_evidence_chain(store, _CERT_ORG, str(row["id"]))
        meta = row.get("metadata") or {}
        actioned = meta.get("verified_from_actioned_outcome_id")
        if not chain or not chain["metric"].get("key") or not meta.get("source_records") or not any(r.get("id") == actioned for r in ledger):
            chains_ok = False
    checks.append(_check("evidence_chains_resolve", chains_ok, f"{len(counted)} chains"))

    claims = [(r.get("metadata") or {}).get("claim_key") for r in counted]
    assisted = [r for r in verified if (r.get("metadata") or {}).get("counted_in_total") is False]
    double = len(claims) != len(set(claims))
    idempotent = second.get("verified", 0) == 0 and second.get("assisted", 0) == 0
    multi_play = any(len([p for p in config.plays if {c.metric_key for c in r.contributions} & set(p.kpi_keys)]) > 1 for r in recipes)
    checks.append(
        _check(
            "no_double_count",
            not double and idempotent and (bool(assisted) or not multi_play),
            f"{len(counted)} counted, {len(assisted)} assisted, re-run added {second.get('verified', 0)}",
        )
    )

    dash_keys = sorted({m.kpi_key for m in config.dashboard.metrics})
    values = {m["metricKey"]: m for m in compute_business_metrics(store, _CERT_ORG, range_key="all", metric_keys=dash_keys)["metrics"]}
    expected = {c.metric_key for r in recipes for c in r.contributions} & set(dash_keys)
    unresolved_dash = sorted(k for k in expected if values.get(k, {}).get("status") != "verified")
    business_dash = [k for k in dash_keys if kpis.get(k) and kpis[k].kind != "operational"]
    checks.append(_check("dashboard_kpis_verified", bool(business_dash) and bool(expected) and not unresolved_dash, ", ".join(unresolved_dash) or f"{len(expected)} KPIs verified"))

    empty = compute_business_metrics(MemoryStore(), _CERT_ORG, range_key="all", metric_keys=dash_keys)["metrics"]
    fabricated = [m["metricKey"] for m in empty if m.get("value") is not None or m.get("status") == "verified"]
    checks.append(_check("missing_evidence_unknown", not fabricated, ", ".join(fabricated) or "all unknown without evidence"))

    try:
        dash = DashboardPackAssetConfig.model_validate(config.dashboard.model_dump())
        section_keys = {k for s in dash.sections for k in s.kpi_keys}
        templates = {t["templateId"]: t for t in dashboard_templates()}
        installable = bool(dash.template_id) and dash.template_id in templates and section_keys <= set(dash_keys) and bool(section_keys)
        detail = "" if installable else "template or sections incomplete"
    except Exception as exc:  # noqa: BLE001
        installable, detail = False, str(exc)[:200]
    checks.append(_check("dashboard_installable", installable, detail or str(config.dashboard.template_id)))

    learning = [r for r in store.rows("intelligence_outcome_events") if (r.get("metadata") or {}).get("learning_source")]
    decided = [r for r in ledger if (r.get("metadata") or {}).get("verification_state") in {"VERIFIED SUCCESS", "VERIFIED FAILURE"} and (r.get("metadata") or {}).get("counted_in_total") is not False]
    decided_ids = {r["id"] for r in decided}
    stray_learning = [r for r in learning if (r.get("metadata") or {}).get("verified_result_id") not in decided_ids]
    checks.append(_check("learning_verified_only", bool(learning) and not stray_learning, f"{len(learning)} learning events, {len(stray_learning)} from unverified"))

    # 13 governance
    ungoverned: list[str] = []
    for play in config.plays:
        for item in play.write_actions:
            if str(item.get("approval") or "") != "always":
                continue
            for action in play_write_actions(play):
                if not is_always_approve_write_action(action):
                    ungoverned.append(f"{play.key}:{action}")
    for action in config.governance.always_approve_actions:
        if not is_always_approve_write_action(action):
            ungoverned.append(action)
    has_writes = any(p.write_actions or p.write_action_groups for p in config.plays)
    checks.append(_check("governance_enforced", None if not has_writes else not ungoverned, ", ".join(sorted(set(ungoverned))) or "approvals enforced"))

    # 14 degraded scenarios replan
    failures: list[str] = []
    for scenario in config.certification.degraded_scenarios:
        capability = str(scenario.get("capability") or "")
        vendor = str(scenario.get("unavailable_vendor") or "")
        definition = get_capability(capability)
        if definition is None:
            failures.append(f"{capability}: unknown")
            continue
        degraded_store = MemoryStore()
        binding = next((b for b in definition.bindings if b.vendor == vendor), None)
        record_unavailable(degraded_store, _CERT_ORG, action=binding.action_key if binding else f"{vendor}.*", state=str(scenario.get("reason") or "plan_limit"))
        connected = sorted({b.vendor for b in definition.bindings})
        usable, skipped = ordered_alternatives(capability, connected=connected, blocks=load_blocks(degraded_store, _CERT_ORG))
        if not any(s["vendor"] == vendor for s in skipped) or (not usable and not _binds_web_research(capability)):
            failures.append(f"{capability}: no alternative after {vendor} {scenario.get('reason')}")
    checks.append(_check("degraded_replans", None if not config.certification.degraded_scenarios else not failures, ", ".join(failures) or f"{len(config.certification.degraded_scenarios)} scenarios"))

    applicable = [c for c in checks if c["status"] != "n/a"]
    complete = all(c["status"] == "pass" for c in applicable)
    columns: dict[str, str] = {}
    for key, _label, column in CONTRACT_CHECKS:
        status = next(c["status"] for c in checks if c["key"] == key)
        prior = columns.get(column)
        if status == "fail" or prior == "fail":
            columns[column] = "fail"
        elif status == "pass" or prior == "pass":
            columns[column] = "pass"
        else:
            columns[column] = "n/a"
    return {
        "packId": pack.pack_id,
        "department": pack.department,
        "metrics": len(kpis),
        "plays": len(config.plays),
        "checks": checks,
        "columns": columns,
        "complete": complete,
        "measurement": {k: v for k, v in first.items() if k != "exceptions"},
    }


def certify_all_outcome_packs() -> list[dict[str, Any]]:
    from app.outcome_packs.registry import list_packs

    return [certify_outcome_contract(pack) for pack in list_packs()]
