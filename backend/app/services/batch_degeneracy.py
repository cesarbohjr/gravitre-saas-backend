"""Phase 4 — statistical degenerate / low-information batch detection.

Independent of AI judgment: inspects value *distribution* across multi-record
results. Catches schema-valid, Phase-3-passing batches that are functionally
worthless (identical or placeholder-dominated fields).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

# Placeholder / non-answer patterns (case-insensitive exact or whole-token).
_PLACEHOLDER_EXACT = frozenset(
    {
        "",
        "-",
        "--",
        "n/a",
        "na",
        "n.a.",
        "none",
        "null",
        "nil",
        "unknown",
        "unk",
        "tbd",
        "todo",
        "?",
        "??",
        "cannot tell",
        "can't tell",
        "cant tell",
        "not available",
        "not applicable",
        "no data",
        "no information",
        "unavailable",
        "unclear",
        "unspecified",
        "missing",
        "empty",
        "blank",
        "xxx",
        "placeholder",
    }
)
_PLACEHOLDER_RE = re.compile(
    r"^(n/?a|unknown|cannot\s+tell|can'?t\s+tell|not\s+(?:available|applicable)|"
    r"no\s+(?:data|info(?:rmation)?)|tbd|todo|placeholder)\b",
    re.I,
)

# Fields that are identifiers / URLs — identical values are expected, skip.
_SKIP_FIELDS = frozenset(
    {
        "id",
        "list_id",
        "listid",
        "org_id",
        "orgid",
        "connector_id",
        "run_id",
        "status",
        "success",
        "type",
        "url",
        "result_url",
        "external_url",
        "href",
        "link",
        "created_at",
        "updated_at",
        "timestamp",
    }
)

# Thresholds chosen against representative batch shapes (see docs/delivery/phase4-*).
# identical_ratio: fraction sharing the modal value on a content field.
# placeholder_ratio: fraction matching placeholder/non-answer patterns.
# min_batch: below this, variance is not statistically meaningful.
BATCH_CLASS_THRESHOLDS: dict[str, dict[str, float | int]] = {
    # Enrichment / research outputs should vary across people/companies.
    "enrichment": {"min_batch": 3, "identical_ratio": 0.80, "placeholder_ratio": 0.50},
    # List populate / membership rows — contact payloads should differ.
    "list_population": {"min_batch": 3, "identical_ratio": 0.85, "placeholder_ratio": 0.50},
    # Generic multi-record writes / generations.
    "default": {"min_batch": 3, "identical_ratio": 0.85, "placeholder_ratio": 0.55},
}

_ENRICHMENT_ACTIONS = frozenset(
    {
        "clay.enrich",
        "clay.table_enrich",
        "apollo.people.enrich",
        "apollo.people.bulk_enrich",
        "apollo.organizations.enrich",
        "clearbit.enrich",
        "zoominfo.enrich",
    }
)


@dataclass(frozen=True)
class BatchDegeneracyResult:
    flagged: bool
    batch_class: str
    record_count: int
    reason: str
    field: str | None = None
    identical_ratio: float = 0.0
    placeholder_ratio: float = 0.0
    threshold_identical: float = 0.0
    threshold_placeholder: float = 0.0
    modal_value: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "flagged": self.flagged,
            "batch_class": self.batch_class,
            "record_count": self.record_count,
            "reason": self.reason,
            "field": self.field,
            "identical_ratio": round(self.identical_ratio, 4),
            "placeholder_ratio": round(self.placeholder_ratio, 4),
            "threshold_identical": self.threshold_identical,
            "threshold_placeholder": self.threshold_placeholder,
            "modal_value": self.modal_value,
        }


def batch_class_for_action(invoke_action: str | None) -> str:
    action = str(invoke_action or "").strip().lower()
    if action in _ENRICHMENT_ACTIONS or ".enrich" in action or "enrichment" in action:
        return "enrichment"
    if action in {
        "apollo.lists.add",
        "hubspot.lists.add_contact",
        "marketo.lists.add_to_static_list",
        "constant_contact.lists.add_contacts",
        "mailchimp.members.add",
        "mailchimp.segments.add_member",
        "mailchimp.batch.subscribe",
    } or action.endswith(".lists.add") or "add_contact" in action:
        return "list_population"
    return "default"


def _normalize_value(value: Any) -> str | None:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        # Join short scalar lists for comparison.
        parts = [_normalize_value(v) for v in value[:8]]
        if any(p is None for p in parts):
            return None
        return "|".join(parts)  # type: ignore[arg-type]
    if isinstance(value, dict):
        return None  # nested objects compared via flattened leaves elsewhere
    return str(value).strip()


def _is_placeholder(text: str) -> bool:
    low = text.strip().lower()
    if low in _PLACEHOLDER_EXACT:
        return True
    return bool(_PLACEHOLDER_RE.match(low))


def extract_batch_records(payload: Any) -> list[dict[str, Any]]:
    """Pull a list of record dicts from common write/enrichment response shapes."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in (
        "records",
        "contacts",
        "people",
        "results",
        "items",
        "rows",
        "entities",
        "memberships",
        "leads",
        "companies",
        "organizations",
        "enriched_records",
        "clay_records",
    ):
        raw = payload.get(key)
        if isinstance(raw, list) and raw and all(isinstance(x, dict) for x in raw[:5]):
            return [r for r in raw if isinstance(r, dict)]
    # Nested data/result envelopes
    for key in ("data", "result", "structured", "output"):
        nested = payload.get(key)
        if nested is not None and nested is not payload:
            found = extract_batch_records(nested)
            if found:
                return found
    return []


def _scalar_fields(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Map field → list of normalized scalar values (aligned to records; '' if missing)."""
    keys: set[str] = set()
    for rec in records:
        for k, v in rec.items():
            kl = str(k).strip().lower()
            if not kl or kl in _SKIP_FIELDS or kl.endswith("_id") or kl.endswith("url"):
                continue
            if _normalize_value(v) is None:
                continue
            keys.add(str(k))
    out: dict[str, list[str]] = {}
    n = len(records)
    for key in keys:
        vals: list[str] = []
        present = 0
        for rec in records:
            if key not in rec:
                vals.append("")
                continue
            norm = _normalize_value(rec.get(key))
            if norm is None:
                vals.append("")
                continue
            present += 1
            vals.append(norm)
        # Require field present on ≥ half the batch to avoid sparse noise.
        if present >= max(2, (n + 1) // 2):
            out[key] = vals
    return out


def assess_batch_degeneracy(
    payload: Any,
    *,
    invoke_action: str | None = None,
    thresholds: dict[str, float | int] | None = None,
) -> BatchDegeneracyResult:
    """Return flagged=True when batch distribution is degenerate / low-info."""
    batch_class = batch_class_for_action(invoke_action)
    cfg = dict(BATCH_CLASS_THRESHOLDS.get(batch_class) or BATCH_CLASS_THRESHOLDS["default"])
    if thresholds:
        cfg.update(thresholds)
    min_batch = int(cfg["min_batch"])
    identical_threshold = float(cfg["identical_ratio"])
    placeholder_threshold = float(cfg["placeholder_ratio"])

    records = extract_batch_records(payload)
    n = len(records)
    if n < min_batch:
        return BatchDegeneracyResult(
            flagged=False,
            batch_class=batch_class,
            record_count=n,
            reason="batch_too_small",
            threshold_identical=identical_threshold,
            threshold_placeholder=placeholder_threshold,
        )

    fields = _scalar_fields(records)
    if not fields:
        return BatchDegeneracyResult(
            flagged=False,
            batch_class=batch_class,
            record_count=n,
            reason="no_comparable_fields",
            threshold_identical=identical_threshold,
            threshold_placeholder=placeholder_threshold,
        )

    best_identical: BatchDegeneracyResult | None = None
    best_placeholder: BatchDegeneracyResult | None = None

    for field, values in fields.items():
        counts = Counter(values)
        modal_value, modal_count = counts.most_common(1)[0]
        identical_ratio = modal_count / n
        placeholder_count = sum(1 for v in values if _is_placeholder(v))
        placeholder_ratio = placeholder_count / n

        if identical_ratio >= identical_threshold and modal_value != "":
            # All-identical empty strings handled via placeholder path.
            candidate = BatchDegeneracyResult(
                flagged=True,
                batch_class=batch_class,
                record_count=n,
                reason="identical_value_dominance",
                field=field,
                identical_ratio=identical_ratio,
                placeholder_ratio=placeholder_ratio,
                threshold_identical=identical_threshold,
                threshold_placeholder=placeholder_threshold,
                modal_value=modal_value[:120],
            )
            if best_identical is None or identical_ratio > best_identical.identical_ratio:
                best_identical = candidate

        if placeholder_ratio >= placeholder_threshold:
            candidate = BatchDegeneracyResult(
                flagged=True,
                batch_class=batch_class,
                record_count=n,
                reason="placeholder_dominance",
                field=field,
                identical_ratio=identical_ratio,
                placeholder_ratio=placeholder_ratio,
                threshold_identical=identical_threshold,
                threshold_placeholder=placeholder_threshold,
                modal_value=modal_value[:120] if modal_value else None,
            )
            if best_placeholder is None or placeholder_ratio > best_placeholder.placeholder_ratio:
                best_placeholder = candidate

    # Prefer identical-value flags (cmumulle72 scenario) over placeholder when both fire.
    if best_identical is not None:
        return best_identical
    if best_placeholder is not None:
        return best_placeholder

    return BatchDegeneracyResult(
        flagged=False,
        batch_class=batch_class,
        record_count=n,
        reason="ok_variance",
        threshold_identical=identical_threshold,
        threshold_placeholder=placeholder_threshold,
    )


def apply_batch_degeneracy_to_status(
    *,
    status: str,
    invoke_action: str | None,
    result_data: Any,
) -> tuple[str, BatchDegeneracyResult | None]:
    """Downgrade completed/partial_success → flagged_for_review when batch is degenerate.

    Does not upgrade failed/cancelled. Never leaves COMPLETED when flagged.
    """
    normalized = str(status or "").strip().lower()
    if normalized not in {"completed", "success", "partial_success"}:
        return status, None
    result = assess_batch_degeneracy(result_data, invoke_action=invoke_action)
    if not result.flagged:
        return status, result
    return "flagged_for_review", result
