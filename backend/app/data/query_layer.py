"""Natural-language query layer over connected data sources."""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings
from app.data.connection_service import ConnectionTestError, discover_schema, execute_readonly_sql
from app.services.model_router import TaskType, get_model_router

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|call)\b",
    re.IGNORECASE,
)


def _build_schema_prompt(schema: dict[str, Any]) -> str:
    tables = schema.get("tables") or []
    if not tables:
        return "No schema metadata is available yet."
    lines: list[str] = []
    for table in tables[:40]:
        name = table.get("name") or "unknown"
        schema_name = table.get("schema")
        qualified = f"{schema_name}.{name}" if schema_name else name
        columns = table.get("columns") or []
        col_desc = ", ".join(
            f"{col.get('name')}:{col.get('type')}" for col in columns[:20] if col.get("name")
        )
        lines.append(f"- {qualified}({col_desc})")
    return "\n".join(lines)


async def generate_sql_from_question(
    *,
    question: str,
    schema: dict[str, Any],
    settings: Settings,
    dialect: str = "PostgreSQL",
) -> str:
    schema_text = _build_schema_prompt(schema)
    system = (
        f"You are a senior analytics engineer. Generate ONE read-only {dialect} query "
        "for the user's question. Return ONLY SQL, no markdown, no explanation. "
        "Use explicit table names from the schema. Prefer LIMIT 100."
    )
    user = f"Schema:\n{schema_text}\n\nQuestion: {question.strip()}"
    router = get_model_router()
    response = await router.complete(
        TaskType.RAG_ANSWERING,
        prompt=user,
        system_prompt=system,
        temperature=0,
        max_tokens=800,
    )
    sql = response.content
    cleaned = sql.strip().strip("`")
    if cleaned.lower().startswith("sql"):
        cleaned = cleaned[3:].strip()
    if _FORBIDDEN_SQL.search(cleaned):
        raise ConnectionTestError("Generated SQL contained forbidden statements", code="UNSAFE_SQL")
    if not re.match(r"^\s*(select|with)\b", cleaned, re.IGNORECASE):
        raise ConnectionTestError("Generated SQL must be SELECT/WITH only", code="UNSAFE_SQL")
    return cleaned


async def natural_language_query(
    *,
    type_id: str,
    config: dict[str, Any],
    question: str,
    settings: Settings,
) -> dict[str, Any]:
    if not question.strip():
        raise ConnectionTestError("Question is required", code="VALIDATION_ERROR")

    schema = await discover_schema(type_id, config)
    dialect = "MySQL" if type_id in {"mysql", "mariadb", "planetscale"} else "PostgreSQL"
    sql = await generate_sql_from_question(question=question, schema=schema, settings=settings, dialect=dialect)
    result = await execute_readonly_sql(type_id, config, sql)
    return {
        "question": question.strip(),
        "sql": sql,
        "columns": result.get("columns") or [],
        "rows": result.get("rows") or [],
        "rowCount": result.get("rowCount") or 0,
        "schemaTableCount": schema.get("tableCount") or 0,
    }


def suggest_exploration_questions(schema: dict[str, Any], *, limit: int = 5) -> list[str]:
    tables = schema.get("tables") or []
    suggestions: list[str] = []
    for table in tables[:limit]:
        name = table.get("name") or "table"
        suggestions.append(f"What are the 10 most recent rows in {name}?")
        suggestions.append(f"How many records are in {name}?")
    if not suggestions:
        return [
            "List all tables and row counts",
            "Show sample data from the largest table",
            "Which columns look like timestamps or IDs?",
        ]
    return suggestions[:limit]
