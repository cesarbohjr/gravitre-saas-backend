"""Generic source-of-record measurement for Play results.

One engine for every department. It knows nothing about growth, sales, SEO,
customer success or service desks: Outcome Pack verification recipes declare
which records to re-read, with which catalog read action, and what counts.

Flow per ACTIONED Play result (``intelligence_outcome_events``):
1. The ACTIONED writer stored ``source_record_candidates`` (recipe, system,
   record type, record id) for each record a Play wrote.
2. When a recipe's measurement window is open, the engine re-reads the record
   through the declared catalog read action (``invoke_tool``), optionally also
   over a baseline window, and evaluates each contribution.
3. Decisive results are appended through ``record_source_verified_play_result``
   (the only VERIFIED writer). A claim key per metric and source record means
   the first verified result counts; later ones are ASSISTED and excluded from
   totals. A closed window without decisive evidence appends INCONCLUSIVE.
4. Counted verified movement emits a learning event; nothing else does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.core.logging import get_logger
from app.marketplace.schemas import PredicateConfig, RecipeContributionConfig, VerificationRecipeConfig
from app.outcome_packs.predicates import evaluate_predicate, evaluate_value, parse_time, read_field
from app.plays.outcomes import PLAY_BUSINESS_RESULT_EVENT, AttributionType, SourceRecordRef

logger = get_logger(__name__)

LEDGER = "intelligence_outcome_events"
MEASUREMENT_ACTOR = "outcome-measurement"
MAX_LOOKBACK_DAYS = 400

# A reader returns {"current": <read data or None>, "baseline": <read data or None>}.
RecordReader = Callable[[VerificationRecipeConfig, str, dict[str, Any]], dict[str, Any]]


# --------------------------------------------------------------------------- candidates (ACTIONED side)

def record_key(system: str, record_type: str, record_id: str) -> str:
    return f"{system}|{record_type}|{record_id}".lower()


def claim_key(metric_key: str, system: str, record_type: str, record_id: str) -> str:
    return f"{metric_key}|{record_key(system, record_type, record_id)}"


def _ids_at(source: Any, path: str) -> list[str]:
    value = read_field(source, path)
    if isinstance(value, list):
        return [str(v.get("id") if isinstance(v, dict) else v).strip() for v in value if v not in (None, "")]
    if isinstance(value, dict):
        value = value.get("id")
    text = str(value).strip() if value not in (None, "") else ""
    return [text] if text else []


def source_record_candidates(
    action: str,
    *,
    output: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Records a write produced that some pack recipe can verify later."""
    from app.outcome_packs.registry import recipes_for_action

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pack, recipe in recipes_for_action(action):
        ids: list[str] = []
        for path in recipe.record_id_fields:
            for source in (output or {}, params or {}):
                ids = _ids_at(source, path)
                if ids:
                    break
            if ids:
                break
        for record_id in ids:
            marker = (recipe.key, record_id)
            if marker in seen:
                continue
            seen.add(marker)
            out.append(
                {
                    "recipe_key": recipe.key,
                    "pack_id": pack.pack_id,
                    "system": recipe.source_system,
                    "record_type": recipe.record_type,
                    "record_id": record_id,
                }
            )
    return out


# --------------------------------------------------------------------------- windows + reads

def _now() -> datetime:
    return datetime.now(timezone.utc)


def measurement_windows(actioned_at: datetime, now: datetime, recipe: VerificationRecipeConfig) -> dict[str, Any]:
    window_end = min(now, actioned_at + timedelta(days=recipe.measure_window_days))
    length = max(window_end - actioned_at, timedelta(days=1))
    baseline_start = actioned_at - length
    def fmt(prefix: str, value: datetime) -> dict[str, Any]:
        return {
            prefix: value.isoformat(),
            f"{prefix}_date": value.date().isoformat(),
            f"{prefix}_ms": int(value.timestamp() * 1000),
        }
    return {
        **fmt("window_start", actioned_at),
        **fmt("window_end", window_end),
        **fmt("baseline_start", baseline_start),
        **fmt("baseline_end", actioned_at),
    }


def _fill(value: Any, tokens: dict[str, Any]) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}") and stripped[1:-1] in tokens:
            return tokens[stripped[1:-1]]
        out = value
        for key, token in tokens.items():
            out = out.replace("{" + key + "}", str(token))
        return out
    if isinstance(value, list):
        return [_fill(v, tokens) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, tokens) for k, v in value.items()}
    return value


def read_params(recipe: VerificationRecipeConfig, record_id: str, windows: dict[str, Any], *, baseline: bool) -> dict[str, Any]:
    tokens = dict(windows)
    tokens["record_id"] = record_id
    if baseline:
        for name in ("", "_date", "_ms"):
            tokens[f"window_start{name}"] = windows[f"baseline_start{name}"]
            tokens[f"window_end{name}"] = windows[f"baseline_end{name}"]
    params = _fill(dict(recipe.read_params), tokens)
    params[recipe.record_id_param] = record_id
    return params


def tool_reader(client: Any, org_id: str, settings: Any = None) -> RecordReader:
    """Re-read records through the canonical catalog read path (audited, rate limited)."""
    from app.config import get_settings
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=settings or get_settings(),
        client=client,
        org_id=org_id,
        actor_id=MEASUREMENT_ACTOR,
        environment_name="production",
    )

    def read(recipe: VerificationRecipeConfig, record_id: str, windows: dict[str, Any]) -> dict[str, Any]:
        current = invoke_tool(ctx, recipe.read_action, read_params(recipe, record_id, windows, baseline=False))
        baseline = None
        if recipe.baseline_read:
            baseline = invoke_tool(ctx, recipe.read_action, read_params(recipe, record_id, windows, baseline=True))
        return {
            "current": current.data if current.success else None,
            "baseline": (baseline.data if baseline.success else None) if baseline is not None else None,
        }

    return read


# --------------------------------------------------------------------------- evaluation

@dataclass
class ContributionDecision:
    metric_key: str
    decision: str  # success | failure | undecided
    value: float | None = None
    baseline: float | None = None
    currency: str | None = None
    reason: str = ""


def _apply_org_definition(pred: PredicateConfig | None, semantics: dict[str, Any]) -> PredicateConfig | None:
    """Org-defined qualifying values replace a recipe's ``in`` lists (no code per org)."""
    values = semantics.get("qualifying_values")
    if pred is None or not isinstance(values, list) or not values:
        return pred
    wanted_field = semantics.get("qualifying_field")

    def rewrite(node: PredicateConfig) -> PredicateConfig:
        if node.all is not None:
            return node.model_copy(update={"all": [rewrite(child) for child in node.all]})
        if node.any is not None:
            return node.model_copy(update={"any": [rewrite(child) for child in node.any]})
        if node.op == "in" and (not wanted_field or node.field == wanted_field):
            return node.model_copy(update={"value": list(values)})
        return node

    return rewrite(pred)


def _direction_ok(direction: str, value: float, baseline: float) -> bool:
    if direction == "increase":
        return value > baseline
    if direction == "decrease":
        return value < baseline
    return True


def evaluate_contribution(
    contribution: RecipeContributionConfig,
    record: dict[str, Any],
    *,
    direction: str = "increase",
    semantics: dict[str, Any] | None = None,
) -> ContributionDecision:
    semantics = semantics or {}
    when = _apply_org_definition(contribution.when, semantics)
    metric = contribution.metric_key
    if record.get("current") is None:
        return ContributionDecision(metric, "undecided", reason="source record could not be read")
    if contribution.fail_when is not None and evaluate_predicate(contribution.fail_when, record):
        value = evaluate_value(contribution.value, record)
        baseline = evaluate_value(contribution.baseline, record)
        return ContributionDecision(metric, "failure", value if value is not None else 0.0,
                                    baseline if baseline is not None else 0.0, reason="failure condition met")
    if not evaluate_predicate(when, record):
        return ContributionDecision(metric, "undecided", reason="success condition not met yet")
    value = evaluate_value(contribution.value, record)
    baseline = evaluate_value(contribution.baseline, record)
    if value is None:
        return ContributionDecision(metric, "undecided", reason="the source record has no value for this metric")
    if baseline is None:
        return ContributionDecision(metric, "undecided", value=value, reason="no baseline measurement")
    compared = contribution.baseline.const is None
    if compared and not _direction_ok(direction, value, baseline):
        return ContributionDecision(metric, "failure", value, baseline, reason="metric moved the wrong way")
    currency = read_field(record, contribution.currency_field) if contribution.currency_field else None
    return ContributionDecision(metric, "success", value, baseline, str(currency).upper() if currency else None)


# --------------------------------------------------------------------------- ledger helpers

def _ledger(client: Any, org_id: str):
    return client.table(LEDGER).select("id, org_id, metadata, created_at").eq("org_id", org_id).eq(
        "outcome_event", PLAY_BUSINESS_RESULT_EVENT
    )


def _existing_decisions(client: Any, org_id: str, actioned_id: str) -> set[str]:
    rows = _ledger(client, org_id).eq("metadata->>verified_from_actioned_outcome_id", actioned_id).limit(500).execute().data or []
    return {str((r.get("metadata") or {}).get("decision_key") or "") for r in rows if isinstance(r, dict)}


def _claimed(client: Any, org_id: str, key: str) -> bool:
    rows = (
        _ledger(client, org_id)
        .eq("metadata->>claim_key", key)
        .eq("metadata->>verification_state", "VERIFIED SUCCESS")
        .eq("metadata->>counted_in_total", "true")
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def _is_unique_violation(exc: Exception) -> bool:
    code = str(getattr(exc, "code", "") or "")
    return code == "23505" or "23505" in str(exc) or "duplicate key" in str(exc).lower()


def _emit_learning(client: Any, org_id: str, verified: dict[str, Any], *, success: bool) -> None:
    from app.outcome_packs.registry import learning_signals

    meta = verified.get("metadata") if isinstance(verified.get("metadata"), dict) else {}
    metric = str(meta.get("metric_key") or "")
    signals = learning_signals().get(metric) or {}
    event = signals.get("improved_event" if success else "declined_event")
    if not event:
        return
    now = _now().isoformat()
    try:
        client.table(LEDGER).insert(
            {
                "org_id": org_id,
                "outcome_event": event,
                "entity_type": verified.get("entity_type"),
                "entity_id": verified.get("entity_id"),
                "workflow_id": verified.get("workflow_id"),
                "workflow_run_id": verified.get("workflow_run_id"),
                "agent_id": verified.get("agent_id"),
                "before_value": verified.get("before_value"),
                "after_value": verified.get("after_value"),
                "measured_at": verified.get("measured_at") or now,
                "measurement_status": "recorded",
                "metadata": {
                    "metric_key": metric,
                    "play_key": meta.get("play_key"),
                    "verified_result_id": verified.get("id"),
                    "learning_source": "source_of_record_verified_play_result",
                },
                "created_at": now,
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug("play_measurement_learning_skipped org_id=%s error=%s", org_id, exc)


# --------------------------------------------------------------------------- measurement

@dataclass
class MeasurementSummary:
    verified: int = 0
    assisted: int = 0
    failed: int = 0
    inconclusive: int = 0
    pending: int = 0
    errors: int = 0
    exceptions: list[dict[str, Any]] = field(default_factory=list)

    def merge(self, other: "MeasurementSummary") -> None:
        self.verified += other.verified
        self.assisted += other.assisted
        self.failed += other.failed
        self.inconclusive += other.inconclusive
        self.pending += other.pending
        self.errors += other.errors
        self.exceptions.extend(other.exceptions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "assisted": self.assisted,
            "failed": self.failed,
            "inconclusive": self.inconclusive,
            "pending": self.pending,
            "errors": self.errors,
            "exceptions": self.exceptions[:50],
        }


def _write_decision(
    client: Any,
    org_id: str,
    actioned_id: str,
    candidate: dict[str, Any],
    recipe: VerificationRecipeConfig,
    decision: ContributionDecision,
    *,
    observed_at: str,
    summary: MeasurementSummary,
) -> None:
    from app.outcome_packs.registry import metric_definition
    from app.plays.verification import SourceVerificationEvidence, record_source_verified_play_result

    definition = metric_definition(decision.metric_key) or {}
    unit = str(definition.get("unit") or "count")
    system, rtype, rid = candidate["system"], candidate["record_type"], candidate["record_id"]
    ck = claim_key(decision.metric_key, system, rtype, rid)
    extra = {
        "claim_key": ck,
        "decision_key": f"{actioned_id}|{ck}",
        "recipe_key": recipe.key,
        "pack_id": candidate.get("pack_id"),
        "objective_id": candidate.get("objective_id"),
        "measurement_engine": "outcome_pack_recipe/v1",
    }
    evidence = SourceVerificationEvidence(
        system=system,
        record_type=rtype,
        record_id=rid,
        method=recipe.verification_method,
        observed_at=observed_at,
        baseline_value=decision.baseline,
        result_value=decision.value,
        outcome_type="business_metric",
        metric_key=decision.metric_key,
        unit=unit,
        currency=decision.currency if unit == "currency" else None,
    )
    success = decision.decision == "success"
    counted = success and not _claimed(client, org_id, ck)
    for attempt in range(2):
        try:
            row = record_source_verified_play_result(
                client,
                org_id=org_id,
                actioned_outcome_id=actioned_id,
                evidence=evidence,
                success=success,
                attribution_type=AttributionType.DIRECT if counted or not success else AttributionType.ASSISTED,
                attribution_weight=1.0 if counted or not success else 0.0,
                extra_metadata={**extra, "counted_in_total": bool(counted)},
            )
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc) and counted and attempt == 0:
                # Another Play verified this record first: this result is assisted.
                counted = False
                continue
            if _is_unique_violation(exc):
                return  # already decided for this ACTIONED result (idempotent re-run)
            raise
        break
    if not success:
        summary.failed += 1
        _emit_learning(client, org_id, row, success=False)
    elif counted:
        summary.verified += 1
        _emit_learning(client, org_id, row, success=True)
    else:
        summary.assisted += 1


def measure_actioned_row(
    client: Any,
    org_id: str,
    row: dict[str, Any],
    *,
    reader: RecordReader,
    now: datetime | None = None,
    only_record: str | None = None,
) -> MeasurementSummary:
    """Measure one ACTIONED result against every recipe candidate it carries."""
    from app.outcome_packs.registry import get_recipe, metric_definition
    from app.plays.verification import record_inconclusive_play_result
    from app.services.cognitive_metrics import get_org_metric_semantics

    summary = MeasurementSummary()
    now = now or _now()
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if str(meta.get("verification_state") or "") != "ACTIONED":
        return summary
    actioned_id = str(row.get("id") or "")
    actioned_at = parse_time(row.get("created_at") or meta.get("occurred_at"))
    candidates = [c for c in (meta.get("source_record_candidates") or []) if isinstance(c, dict)]
    if not actioned_id or actioned_at is None or not candidates:
        return summary
    decided = _existing_decisions(client, org_id, actioned_id)
    semantics_cache: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        candidate = {**candidate, "objective_id": meta.get("objective_id")}
        if only_record and record_key(candidate["system"], candidate["record_type"], candidate["record_id"]) != only_record:
            continue
        found = get_recipe(str(candidate.get("recipe_key") or ""))
        if found is None:
            summary.exceptions.append({"outcomeId": actioned_id, "kind": "recipe_missing", "message": str(candidate.get("recipe_key"))})
            continue
        _, recipe = found
        open_contributions = [
            c for c in recipe.contributions
            if f"{actioned_id}|{claim_key(c.metric_key, candidate['system'], candidate['record_type'], candidate['record_id'])}" not in decided
        ]
        if not open_contributions:
            continue
        earliest = actioned_at + timedelta(hours=recipe.measure_after_hours)
        deadline = earliest + timedelta(days=recipe.measure_window_days)
        if now < earliest:
            summary.pending += len(open_contributions)
            continue
        windows = measurement_windows(actioned_at, now, recipe)
        try:
            record = reader(recipe, str(candidate["record_id"]), windows)
        except Exception as exc:  # noqa: BLE001 — a failed read is retried next run
            summary.errors += 1
            summary.exceptions.append({"outcomeId": actioned_id, "kind": "read_failed", "message": str(exc)[:300]})
            continue
        observed_at = now.isoformat()
        for contribution in open_contributions:
            metric = contribution.metric_key
            if metric not in semantics_cache:
                semantics_cache[metric] = get_org_metric_semantics(client, org_id, metric)
            definition = metric_definition(metric) or {}
            decision = evaluate_contribution(
                contribution,
                record,
                direction=str(definition.get("direction") or "increase"),
                semantics=semantics_cache[metric],
            )
            if decision.decision in {"success", "failure"}:
                try:
                    _write_decision(client, org_id, actioned_id, candidate, recipe, decision,
                                    observed_at=observed_at, summary=summary)
                except Exception as exc:  # noqa: BLE001
                    summary.errors += 1
                    summary.exceptions.append({"outcomeId": actioned_id, "kind": "write_failed", "message": str(exc)[:300]})
            elif now >= deadline:
                ck = claim_key(metric, candidate["system"], candidate["record_type"], candidate["record_id"])
                try:
                    record_inconclusive_play_result(
                        client,
                        org_id=org_id,
                        actioned_outcome_id=actioned_id,
                        metric_key=metric,
                        reason=decision.reason,
                        observed_at=observed_at,
                        source_record=SourceRecordRef(candidate["system"], candidate["record_type"], candidate["record_id"]),
                        extra_metadata={"claim_key": ck, "decision_key": f"{actioned_id}|{ck}", "recipe_key": recipe.key,
                                        "counted_in_total": False, "measurement_engine": "outcome_pack_recipe/v1"},
                    )
                    summary.inconclusive += 1
                except Exception as exc:  # noqa: BLE001
                    if not _is_unique_violation(exc):
                        summary.errors += 1
            else:
                summary.pending += 1
                if decision.reason and decision.reason != "success condition not met yet":
                    summary.exceptions.append({"outcomeId": actioned_id, "kind": "evidence_gap", "message": f"{metric}: {decision.reason}"})
    return summary


def _actioned_rows(client: Any, *, org_id: str | None, since: datetime, limit: int, record: str | None = None) -> list[dict[str, Any]]:
    q = (
        client.table(LEDGER)
        .select("id, org_id, outcome_event, entity_type, entity_id, workflow_id, workflow_run_id, agent_id, metadata, created_at")
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .eq("metadata->>verification_state", "ACTIONED")
        .gte("created_at", since.isoformat())
    )
    if org_id:
        q = q.eq("org_id", org_id)
    if record:
        q = q.contains("metadata", {"source_record_keys": [record]})
    return list(q.order("created_at", desc=False).limit(max(1, min(int(limit), 1000))).execute().data or [])


def measure_record_now(
    client: Any,
    org_id: str,
    *,
    system: str,
    record_type: str | None = None,
    record_id: str,
    settings: Any = None,
    reader: RecordReader | None = None,
    now: datetime | None = None,
) -> int:
    """Re-measure ACTIONED results that reference one source record (webhook path). Never raises."""
    try:
        from app.outcome_packs.registry import verification_recipes

        now = now or _now()
        types = [record_type] if record_type else sorted({r.record_type for _, r in verification_recipes() if r.source_system == system})
        reader = reader or tool_reader(client, org_id, settings)
        total = MeasurementSummary()
        for rtype in types:
            key = record_key(system, rtype, record_id)
            for row in _actioned_rows(client, org_id=org_id, since=now - timedelta(days=MAX_LOOKBACK_DAYS), limit=50, record=key):
                total.merge(measure_actioned_row(client, org_id, row, reader=reader, now=now, only_record=key))
        return total.verified
    except Exception as exc:  # noqa: BLE001
        logger.warning("play_measure_record_now_failed org_id=%s system=%s err=%s", org_id, system, exc)
        return 0


def measure_pending_play_results(
    client: Any,
    *,
    org_id: str | None = None,
    settings: Any = None,
    limit: int = 200,
    reader: RecordReader | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Scheduled job: measure every open ACTIONED result (all packs, all departments)."""
    now = now or _now()
    total = MeasurementSummary()
    try:
        rows = _actioned_rows(client, org_id=org_id, since=now - timedelta(days=MAX_LOOKBACK_DAYS), limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("play_measurement_scan_failed org_id=%s err=%s", org_id, exc)
        return {**total.as_dict(), "scanned": 0}
    readers: dict[str, RecordReader] = {}
    for row in rows:
        row_org = str(row.get("org_id") or "")
        if not row_org:
            continue
        if reader is not None:
            row_reader = reader
        else:
            row_reader = readers.setdefault(row_org, tool_reader(client, row_org, settings))
        try:
            total.merge(measure_actioned_row(client, row_org, row, reader=row_reader, now=now))
        except Exception as exc:  # noqa: BLE001
            total.errors += 1
            logger.warning("play_measurement_row_failed outcome_id=%s err=%s", row.get("id"), exc)
    return {**total.as_dict(), "scanned": len(rows)}
