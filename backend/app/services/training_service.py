"""Resilient training hub queries (schema-safe for partial prod migrations)."""
from __future__ import annotations

from typing import Any

from app.core.supabase_response import response_error
from app.core.ttl_cache import TTLCache, ttl_from_env


def is_schema_unavailable_error(error: Exception | None) -> bool:
    """True when Supabase/Postgres schema is missing tables or columns."""
    if error is None:
        return False
    text = str(error).lower()
    if "column" in text and "does not exist" in text:
        return False
    markers = (
        "does not exist",
        "could not find the table",
        "schema cache",
        "pgrst205",
        "pgrst204",
        "42703",
        "42p01",
        "undefined table",
        "relation",
    )
    return any(marker in text for marker in markers)


def is_missing_column_error(error: Exception | None) -> bool:
    if error is None:
        return False
    text = str(error).lower()
    return "column" in text and "does not exist" in text


def execute_or_empty(client: Any, builder: Any, *, resource: str) -> list[dict[str, Any]]:
    """Run a select builder; return [] when schema is unavailable."""
    try:
        response = builder.execute()
    except Exception as exc:  # noqa: BLE001
        if is_schema_unavailable_error(exc):
            return []
        raise
    error = response_error(response)
    if is_schema_unavailable_error(error):
        return []
    if error:
        raise RuntimeError(f"{resource}: {error}")
    return list(response.data or [])


def list_training_datasets(client: Any, org_id: str) -> list[dict[str, Any]]:
    return execute_or_empty(
        client,
        client.table("training_datasets")
        .select("id, name, description, type, status, record_count, created_by, created_at, updated_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True),
        resource="training_datasets",
    )


def list_training_jobs(client: Any, org_id: str) -> list[dict[str, Any]]:
    return execute_or_empty(
        client,
        client.table("training_jobs")
        .select("id, dataset_id, model_base, status, progress, metrics, started_at, completed_at, error, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True),
        resource="training_jobs",
    )


# (org_id, agent_id) -> active instruction texts. Every chat turn (text and
# voice) builds a system prompt that needs these, and the read used to run
# synchronously on the event loop each turn. Writers must call
# invalidate_instruction_cache(org_id).
_instruction_cache = TTLCache(ttl_from_env("ORG_STATE_CACHE_TTL_SECONDS", 30.0), max_entries=4096)


def invalidate_instruction_cache(org_id: str | None) -> None:
    """Drop cached instruction texts for an org; never raises."""
    oid = str(org_id or "").strip()
    if not oid:
        return
    try:
        _instruction_cache.invalidate_tag(("org", oid))
    except Exception:  # noqa: BLE001 - a cache bug must not fail a write
        pass


INSTRUCTION_KINDS = ("guidance", "guardrail")
INSTRUCTION_DEPARTMENTS = (
    "sales",
    "marketing",
    "customer_success",
    "operations",
    "finance",
    "engineering",
    "security",
    "general",
)

_INSTRUCTION_COLUMNS = "id, agent_id, name, content, is_active, kind, department, created_at, updated_at"
_LEGACY_INSTRUCTION_COLUMNS = "id, agent_id, name, content, is_active, created_at, updated_at"


def fleet_department(raw: str | None) -> str | None:
    """Agent department label -> roster department id (mirrors the web app's mapping)."""
    key = " ".join(str(raw or "").lower().replace("_", " ").replace("-", " ").split())
    if not key:
        return None
    exact = {
        "sales": "sales",
        "customer success": "customer_success",
        "support": "customer_success",
        "finance": "finance",
        "operations": "operations",
        "engineering": "engineering",
        "marketing": "marketing",
        "security": "security",
        "general": "general",
        "hr": "general",
    }
    if key in exact:
        return exact[key]
    if "sale" in key or "revenue" in key:
        return "sales"
    if "support" in key or "success" in key or "customer" in key:
        return "customer_success"
    if "finance" in key or "account" in key:
        return "finance"
    if "market" in key:
        return "marketing"
    if "secur" in key or "compliance" in key:
        return "security"
    if "engineer" in key or "platform" in key or "sre" in key:
        return "engineering"
    if any(word in key for word in ("hr", "people", "talent", "recruit")):
        return "general"
    return "operations"


def _with_scope_defaults(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        kind = str(row.get("kind") or "guidance")
        row["kind"] = kind if kind in INSTRUCTION_KINDS else "guidance"
        row["department"] = row.get("department") or None
    return rows


def _scope_columns_missing(error: object) -> bool:
    """The kind/department columns are not there yet (any PostgREST/Postgres wording)."""
    text = str(error or "").lower()
    return ("kind" in text or "department" in text) and any(
        marker in text for marker in ("does not exist", "schema cache", "pgrst204", "42703")
    )


def _select_instructions(client: Any, org_id: str, *, active_only: bool, limit: int | None = None) -> list[dict[str, Any]]:
    """Instruction rows with kind/department; falls back to the pre-scope columns."""

    def builder_for(columns: str) -> Any:
        builder = client.table("custom_instructions").select(columns).eq("org_id", org_id)
        if active_only:
            builder = builder.eq("is_active", True)
        builder = builder.order("updated_at", desc=True)
        return builder.limit(limit) if limit is not None else builder

    # Run the scoped read directly: execute_or_empty would turn a missing-column error into
    # an empty list and the legacy retry below would never run.
    try:
        response = builder_for(_INSTRUCTION_COLUMNS).execute()
        error = response_error(response)
    except Exception as exc:  # noqa: BLE001
        response, error = None, exc
    if error is None and response is not None:
        return _with_scope_defaults(list(response.data or []))
    if not _scope_columns_missing(error):
        if is_schema_unavailable_error(error):
            return []
        if isinstance(error, Exception):
            raise error
        raise RuntimeError(f"custom_instructions: {error}")
    return _with_scope_defaults(
        execute_or_empty(client, builder_for(_LEGACY_INSTRUCTION_COLUMNS), resource="custom_instructions")
    )


def load_active_instruction_texts(
    client: Any,
    org_id: str,
    *,
    agent_id: str | None = None,
    department: str | None = None,
    limit: int = 12,
) -> list[str]:
    """Active custom instructions for prompt injection.

    Order: guardrails first (marked ``[Guardrail]``), then guidance from broad to
    specific (whole team, the agent's department, the agent itself), so a later
    line is the more specific one.
    """
    from app.core.org_state_cache import cache_allowed

    dept = fleet_department(department)
    cacheable = cache_allowed(client)
    key = (str(org_id), str(agent_id or ""), str(dept or ""), int(limit))
    if cacheable:
        cached = _instruction_cache.get(key)
        if cached is not None:
            return cached
        token = _instruction_cache.token()
    texts = _query_active_instruction_texts(client, org_id, agent_id=agent_id, department=dept, limit=limit)
    if cacheable:
        _instruction_cache.set(key, texts, tags=[("org", str(org_id))], token=token)
    return texts


def _query_active_instruction_texts(
    client: Any,
    org_id: str,
    *,
    agent_id: str | None,
    department: str | None = None,
    limit: int,
) -> list[str]:
    rows = _select_instructions(client, org_id, active_only=True, limit=max(1, min(limit * 3, 60)))
    agent_key = str(agent_id or "").strip()
    ranked: list[tuple[int, int, str]] = []
    for index, row in enumerate(rows):
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        row_agent = str(row.get("agent_id") or "").strip()
        row_dept = str(row.get("department") or "").strip()
        # Whole-team rows always apply; scoped rows only for their agent or department.
        if row_agent:
            if row_agent != agent_key:
                continue
            level = 3
        elif row_dept:
            if row_dept != department:
                continue
            level = 2
        else:
            level = 1
        name = str(row.get("name") or "Instruction").strip()
        if row.get("kind") == "guardrail":
            ranked.append((0, index, f"[Guardrail] {name}: {content}"))
        else:
            ranked.append((level, index, f"{name}: {content}"))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [text for _, _, text in ranked[:limit]]


def list_custom_instructions(client: Any, org_id: str) -> list[dict[str, Any]]:
    rows = _select_instructions(client, org_id, active_only=False)
    agent_ids = sorted({str(row["agent_id"]) for row in rows if row.get("agent_id")})
    agent_names: dict[str, str] = {}
    if agent_ids:
        try:
            agents_resp = (
                client.table("agents")
                .select("id, name")
                .eq("org_id", org_id)
                .in_("id", agent_ids)
                .execute()
            )
            agents_error = response_error(agents_resp)
            if not agents_error:
                agent_names = {
                    str(row["id"]): str(row.get("name") or "Agent")
                    for row in (agents_resp.data or [])
                }
        except Exception:  # noqa: BLE001
            pass
    for row in rows:
        agent_id = row.get("agent_id")
        if agent_id:
            row["agent_name"] = agent_names.get(str(agent_id))
    return rows


def list_workflow_agents(client: Any, org_id: str) -> list[dict[str, Any]]:
    select_with_ft = "id, name, role, model, status, trained_model_id"
    select_base = "id, name, role, model, status"
    for columns in (select_with_ft, select_base):
        try:
            response = (
                client.table("agents")
                .select(columns)
                .eq("org_id", org_id)
                .order("name")
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            if is_missing_column_error(exc) and columns == select_with_ft:
                continue
            if is_schema_unavailable_error(exc):
                return []
            raise
        if is_schema_unavailable_error(response_error(response)):
            return []
        error = response_error(response)
        if error:
            if is_missing_column_error(error) and columns == select_with_ft:
                continue
            if is_schema_unavailable_error(error):
                return []
            raise RuntimeError(str(error))
        return [
            {
                "id": str(row["id"]),
                "name": row.get("name"),
                "role": row.get("role"),
                "model": row.get("model"),
                "status": row.get("status"),
                "trainedModelId": row.get("trained_model_id"),
            }
            for row in (response.data or [])
        ]
    return []
