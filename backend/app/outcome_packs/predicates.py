"""Generic predicate and value evaluation over normalized evidence records.

Recipes in Outcome Pack manifests describe *what* counts as a verified result
with these expressions; this module is the only interpreter. Nothing here knows
about a department, vendor or metric.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.marketplace.schemas import PredicateConfig, ValueExpressionConfig

_MISSING = object()


def get_path(record: Any, path: str | None) -> Any:
    """Read ``a.b.0.c`` from nested dicts/lists. Missing segments return ``_MISSING``."""
    if not path:
        return _MISSING
    current = record
    for part in str(path).split("."):
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return _MISSING
        else:
            return _MISSING
    return current


def read_field(record: Any, path: str | None) -> Any:
    value = get_path(record, path)
    return None if value is _MISSING else value


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000.0 if float(value) > 1e11 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip()
    if text.isdigit():
        return parse_time(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _comparable(left: Any, right: Any) -> tuple[Any, Any] | None:
    ln, rn = _number(left), _number(right)
    if ln is not None and rn is not None:
        return ln, rn
    lt, rt = parse_time(left), parse_time(right)
    if lt is not None and rt is not None:
        return lt, rt
    return None


def _norm(value: Any) -> Any:
    return value.strip().lower() if isinstance(value, str) else value


def evaluate_predicate(predicate: PredicateConfig | dict[str, Any] | None, record: Any) -> bool:
    """True when the record satisfies the predicate. A missing field never satisfies a comparison."""
    if predicate is None:
        return True
    pred = predicate if isinstance(predicate, PredicateConfig) else PredicateConfig.model_validate(predicate)
    if pred.all is not None:
        return all(evaluate_predicate(child, record) for child in pred.all)
    if pred.any is not None:
        return any(evaluate_predicate(child, record) for child in pred.any)

    raw = get_path(record, pred.field)
    if pred.op == "exists":
        return raw is not _MISSING and raw not in (None, "")
    if pred.op == "missing":
        return raw is _MISSING or raw in (None, "")
    if raw is _MISSING or raw is None:
        return False

    if pred.value_field:
        other = get_path(record, pred.value_field)
        if other is _MISSING or other is None:
            return False
        expected = other
    else:
        expected = pred.value

    if pred.op in {"eq", "ne"}:
        pair = _comparable(raw, expected)
        same = (pair[0] == pair[1]) if pair else (_norm(raw) == _norm(expected))
        return same if pred.op == "eq" else not same
    if pred.op in {"in", "nin"}:
        options = expected if isinstance(expected, (list, tuple, set)) else [expected]
        member = _norm(raw) in {_norm(option) for option in options}
        return member if pred.op == "in" else not member
    pair = _comparable(raw, expected)
    if pair is None:
        return False
    left, right = pair
    if pred.op == "gt":
        return left > right
    if pred.op == "gte":
        return left >= right
    if pred.op == "lt":
        return left < right
    if pred.op == "lte":
        return left <= right
    return False


_UNIT_SECONDS = {"minutes": 60.0, "hours": 3600.0, "days": 86400.0}


def evaluate_value(expr: ValueExpressionConfig | dict[str, Any] | None, record: Any) -> float | None:
    """Numeric value of an expression, or ``None`` when the evidence cannot establish it."""
    if expr is None:
        return None
    spec = expr if isinstance(expr, ValueExpressionConfig) else ValueExpressionConfig.model_validate(expr)
    if spec.const is not None:
        return float(spec.const)
    if spec.field is not None:
        value = _number(read_field(record, spec.field))
    else:
        start = parse_time(read_field(record, spec.duration_from))
        end = parse_time(read_field(record, spec.duration_to))
        value = None if start is None or end is None else (end - start).total_seconds() / _UNIT_SECONDS[spec.duration_unit]
    if value is None:
        value = spec.default
    return None if value is None else value * spec.scale
