"""Time and cost record for one workflow run.

Built from what the run left behind, never estimated: model calls attributed to
the run (``model_calls.run_id``), the run's step rows and its timestamps.

* ``execution_ms``: time spent executing steps (``workflow_runs.duration_ms``).
* ``waiting_ms``: from the run's creation to its first step starting, which for
  a governed event run is mostly the wait for approval.
* ``elapsed_ms``: creation to completion.
* ``model``: call count, tokens and cost in USD, with ``attributed`` false when
  the database does not have the attribution columns yet (cost then unknown,
  not zero).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _read_pages(query: Any, *, page_size: int = 500, max_rows: int = 10_000) -> tuple[list[dict[str, Any]], bool]:
    """Bound report reads and distinguish an incomplete denominator from zero."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    while len(rows) < max_rows:
        batch = (query.order("id")
                 .range(len(rows), min(len(rows) + page_size, max_rows) - 1)
                 .execute().data or [])
        for item in batch:
            row_id = str(item.get("id") or "")
            if not row_id or row_id in seen:
                return rows, False
            seen.add(row_id)
        rows.extend(batch)
        if len(rows) >= max_rows:
            return rows, False
        if len(batch) < page_size:
            return rows, True
    return rows, False


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _ms(start: datetime | None, end: datetime | None) -> int | None:
    if not start or not end:
        return None
    return max(int((end - start).total_seconds() * 1000), 0)


def run_cost_summary(client: Any, org_id: str, run_id: str) -> dict[str, Any] | None:
    run_rows = (
        client.table("workflow_runs")
        .select("id,org_id,workflow_id,status,trigger_type,approval_status,created_at,completed_at,duration_ms")
        .eq("id", run_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    ).data or []
    if not run_rows:
        return None
    run = run_rows[0]
    steps, steps_complete = _read_pages(
        client.table("workflow_steps")
        .select("id,step_type,status,started_at,completed_at,output_snapshot")
        .eq("run_id", run_id)
        .eq("org_id", org_id)
    )

    model: dict[str, Any] = {"attributed": True, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": "0"}
    try:
        calls, models_complete = _read_pages(
            client.table("model_calls")
            .select("id,input_tokens,output_tokens,cost_usd")
            .eq("org_id", org_id)
            .eq("run_id", run_id)
        )
        total = Decimal("0")
        for c in calls:
            model["calls"] += 1
            model["input_tokens"] += int(c.get("input_tokens") or 0)
            model["output_tokens"] += int(c.get("output_tokens") or 0)
            total += Decimal(str(c.get("cost_usd") or 0))
        model["cost_usd"] = str(total.quantize(Decimal("0.000001")))
        model["attributed"] = models_complete
        if not models_complete:
            model.update(calls=None, input_tokens=None, output_tokens=None, cost_usd=None)
    except Exception as exc:  # noqa: BLE001  (columns not migrated yet)
        logger.info("run_cost_model_calls_unavailable run_id=%s error=%s", run_id, str(exc)[:120])
        model = {"attributed": False, "calls": None, "input_tokens": None, "output_tokens": None, "cost_usd": None}

    created = _ts(run.get("created_at"))
    first_start = min((t for t in (_ts(s.get("started_at")) for s in steps) if t), default=None)
    tool_steps = [s for s in steps if str(s.get("step_type") or "") == "invoke_tool"]
    verified = sum(
        1 for s in tool_steps if isinstance(s.get("output_snapshot"), dict) and s["output_snapshot"].get("outcome_verified")
    )
    return {
        "run_id": run_id,
        "workflow_id": run.get("workflow_id"),
        "status": run.get("status"),
        "trigger_type": run.get("trigger_type"),
        "approval_status": run.get("approval_status"),
        "time": {
            "execution_ms": run.get("duration_ms"),
            "waiting_ms": _ms(created, first_start),
            "elapsed_ms": _ms(created, _ts(run.get("completed_at"))),
        },
        "model": model,
        "steps": {
            "total": len(steps) if steps_complete else None,
            "tool_calls": len(tool_steps) if steps_complete else None,
            "verified_writes": verified if steps_complete else None,
            "failed": (sum(1 for s in steps if str(s.get("status") or "") == "failed")
                       if steps_complete else None),
            "coverage_complete": steps_complete,
        },
    }
