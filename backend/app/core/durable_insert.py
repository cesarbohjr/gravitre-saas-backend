"""Idempotent database effects with explicit identity readback after key conflict."""
from __future__ import annotations
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5


def _identity(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return value


def outcome_delivery_id(org_id: str, run_id: str, status: str, channel: str) -> str:
    return str(uuid5(NAMESPACE_URL,
        f"gravitre:outcome:v1:{_identity(org_id)}:{_identity(run_id)}:{status}:{channel}"))


def insert_once(client: Any, table: str, row: dict[str, Any], *, identity: tuple[str, ...]) -> tuple[bool, bool]:
    """Return (acknowledged, newly_created); never overwrite an existing effect.

    Only a unique-constraint failure triggers duplicate readback. A conflict on
    another key, wrong tenant/context, missing row or ambiguous write is not an
    acknowledgement. Callers retry ambiguous writes using the same stable ID.
    """
    try:
        data = client.table(table).insert(row).execute().data
        acknowledged = bool(isinstance(data, list) and data
                            and data[0].get("id") == row["id"])
        return acknowledged, acknowledged
    except Exception as exc:
        if (getattr(exc, "code", None) or getattr(exc, "sqlstate", None)) != "23505":
            raise
    rows = (client.table(table).select(",".join(dict.fromkeys(("id", *identity))))
            .eq("id", row["id"]).eq("org_id", row["org_id"]).limit(1).execute()).data
    if not isinstance(rows, list) or len(rows) != 1:
        return False, False
    return (all(_identity(rows[0].get(key)) == _identity(row.get(key))
                for key in ("id", *identity)), False)
