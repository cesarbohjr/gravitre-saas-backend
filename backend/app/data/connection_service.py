"""Connection testing and schema discovery for external data sources."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.core.logging import get_logger
from app.data.source_registry import DATA_SOURCE_TYPES, validate_connection_config

logger = get_logger(__name__)

_CONNECTION_TIMEOUT_SEC = 10
_POSTGRES_TYPES = frozenset({"postgresql", "neon", "supabase_db", "cockroachdb", "rds", "cloud_sql"})
_MYSQL_TYPES = frozenset({"mysql", "mariadb", "planetscale"})
_SQL_READONLY_TYPES = _POSTGRES_TYPES | _MYSQL_TYPES
_SAAS_CONNECTOR_VENDORS: dict[str, str] = {
    "salesforce": "salesforce",
    "hubspot": "hubspot",
    "stripe": "stripe",
    "notion": "notion",
    "google_sheets": "google_sheets",
    "zendesk": "zendesk",
    "jira": "jira",
    "github": "github",
}


class ConnectionTestError(Exception):
    def __init__(self, message: str, *, code: str = "CONNECTION_FAILED") -> None:
        super().__init__(message)
        self.code = code


def _postgres_dsn(config: dict[str, Any]) -> str:
    connection_string = str(config.get("connection_string") or "").strip()
    if connection_string:
        return connection_string
    host = str(config.get("host") or "").strip()
    port = int(config.get("port") or 5432)
    database = str(config.get("database") or "").strip()
    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "")
    if not host or not database or not username:
        raise ConnectionTestError("Host, database, and username are required for PostgreSQL")
    ssl = config.get("ssl", True)
    sslmode = "require" if ssl else "disable"
    user = quote_plus(username)
    pwd = quote_plus(password)
    return f"postgresql://{user}:{pwd}@{host}:{port}/{database}?sslmode={sslmode}"


async def _test_postgresql(config: dict[str, Any]) -> dict[str, Any]:
    try:
        import asyncpg  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError(
            "PostgreSQL driver (asyncpg) is not installed on the server",
            code="DRIVER_MISSING",
        ) from exc

    dsn = _postgres_dsn(config)
    conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=_CONNECTION_TIMEOUT_SEC)
    try:
        await conn.fetchval("SELECT 1")
        table_count = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT table_name)::int
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_type = 'BASE TABLE'
            """
        )
        record_estimate = await conn.fetchval(
            """
            SELECT COALESCE(SUM(reltuples), 0)::bigint
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            """
        )
        return {
            "success": True,
            "tables": int(table_count or 0),
            "records": int(record_estimate or 0),
            "message": "Connection successful",
        }
    finally:
        await conn.close()


async def _discover_postgresql_schema(config: dict[str, Any]) -> dict[str, Any]:
    try:
        import asyncpg  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("PostgreSQL driver (asyncpg) is not installed", code="DRIVER_MISSING") from exc

    dsn = _postgres_dsn(config)
    conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=_CONNECTION_TIMEOUT_SEC)
    try:
        rows = await conn.fetch(
            """
            SELECT table_schema, table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name, ordinal_position
            LIMIT 500
            """
        )
        tables: dict[str, dict[str, Any]] = {}
        for row in rows:
            table_key = f"{row['table_schema']}.{row['table_name']}"
            bucket = tables.setdefault(
                table_key,
                {"name": row["table_name"], "schema": row["table_schema"], "columns": []},
            )
            bucket["columns"].append(
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                }
            )
        return {"tables": list(tables.values()), "tableCount": len(tables)}
    finally:
        await conn.close()


def _mysql_params(config: dict[str, Any]) -> dict[str, Any]:
    connection_string = str(config.get("connection_string") or "").strip()
    if connection_string.startswith("mysql://"):
        # aiomysql does not parse URLs — fall back to host fields when possible.
        pass
    host = str(config.get("host") or "").strip()
    port = int(config.get("port") or 3306)
    database = str(config.get("database") or "").strip()
    username = str(config.get("username") or "").strip()
    password = str(config.get("password") or "")
    if not host or not database or not username:
        raise ConnectionTestError("Host, database, and username are required for MySQL")
    return {
        "host": host,
        "port": port,
        "db": database,
        "user": username,
        "password": password,
        "connect_timeout": _CONNECTION_TIMEOUT_SEC,
    }


async def _test_mysql(config: dict[str, Any]) -> dict[str, Any]:
    try:
        import aiomysql  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("MySQL driver (aiomysql) is not installed", code="DRIVER_MISSING") from exc

    params = _mysql_params(config)
    conn = await asyncio.wait_for(aiomysql.connect(**params), timeout=_CONNECTION_TIMEOUT_SEC)
    try:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
            await cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                """,
                (params["db"],),
            )
            row = await cursor.fetchone()
            table_count = int(row[0] if row else 0)
        return {
            "success": True,
            "tables": table_count,
            "records": 0,
            "message": "Connection successful",
        }
    finally:
        conn.close()


async def _discover_mysql_schema(config: dict[str, Any]) -> dict[str, Any]:
    try:
        import aiomysql  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("MySQL driver (aiomysql) is not installed", code="DRIVER_MISSING") from exc

    params = _mysql_params(config)
    conn = await asyncio.wait_for(aiomysql.connect(**params), timeout=_CONNECTION_TIMEOUT_SEC)
    try:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
                LIMIT 500
                """,
                (params["db"],),
            )
            rows = await cursor.fetchall()
        tables: dict[str, dict[str, Any]] = {}
        for table_name, column_name, data_type, is_nullable in rows:
            bucket = tables.setdefault(
                str(table_name),
                {"name": str(table_name), "schema": params["db"], "columns": []},
            )
            bucket["columns"].append(
                {
                    "name": str(column_name),
                    "type": str(data_type),
                    "nullable": str(is_nullable).upper() == "YES",
                }
            )
        return {"tables": list(tables.values()), "tableCount": len(tables)}
    finally:
        conn.close()


async def _test_mongodb(config: dict[str, Any]) -> dict[str, Any]:
    connection_string = str(config.get("connection_string") or "").strip()
    database_name = str(config.get("database") or "").strip()
    if not connection_string or not database_name:
        raise ConnectionTestError("Connection string and database name are required")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("MongoDB driver (motor) is not installed", code="DRIVER_MISSING") from exc

    client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=_CONNECTION_TIMEOUT_SEC * 1000)
    try:
        await client.admin.command("ping")
        db = client[database_name]
        collections = await db.list_collection_names()
        return {
            "success": True,
            "tables": len(collections),
            "records": 0,
            "message": "Connection successful",
            "collections": collections[:20],
        }
    finally:
        client.close()


async def _discover_mongodb_schema(config: dict[str, Any]) -> dict[str, Any]:
    connection_string = str(config.get("connection_string") or "").strip()
    database_name = str(config.get("database") or "").strip()
    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("MongoDB driver (motor) is not installed", code="DRIVER_MISSING") from exc

    client = AsyncIOMotorClient(connection_string, serverSelectionTimeoutMS=_CONNECTION_TIMEOUT_SEC * 1000)
    try:
        db = client[database_name]
        collections = await db.list_collection_names()
        tables = [{"name": name, "schema": database_name, "columns": []} for name in collections[:100]]
        return {"tables": tables, "tableCount": len(tables), "message": "MongoDB collections discovered"}
    finally:
        client.close()


def _snowflake_connect(config: dict[str, Any]):
    try:
        import snowflake.connector  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("Snowflake driver is not installed", code="DRIVER_MISSING") from exc
    return snowflake.connector.connect(
        account=str(config.get("account") or "").strip(),
        user=str(config.get("username") or "").strip(),
        password=str(config.get("password") or ""),
        warehouse=str(config.get("warehouse") or "").strip(),
        database=str(config.get("database") or "").strip(),
        schema=str(config.get("schema") or "PUBLIC").strip() or "PUBLIC",
        login_timeout=_CONNECTION_TIMEOUT_SEC,
    )


async def _test_snowflake(config: dict[str, Any]) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        conn = _snowflake_connect(config)
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.execute(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = CURRENT_SCHEMA()
                """
            )
            table_count = int(cur.fetchone()[0])
            return {"success": True, "tables": table_count, "records": 0, "message": "Connection successful"}
        finally:
            conn.close()

    try:
        return await asyncio.to_thread(_run)
    except ConnectionTestError as exc:
        if exc.code == "DRIVER_MISSING":
            return await _test_config_only("snowflake", config)
        raise


async def _discover_snowflake_schema(config: dict[str, Any]) -> dict[str, Any]:
    def _run() -> dict[str, Any]:
        conn = _snowflake_connect(config)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = CURRENT_SCHEMA()
                ORDER BY table_name, ordinal_position
                LIMIT 500
                """
            )
            rows = cur.fetchall()
            tables: dict[str, dict[str, Any]] = {}
            for table_schema, table_name, column_name, data_type, is_nullable in rows:
                key = f"{table_schema}.{table_name}"
                bucket = tables.setdefault(
                    key,
                    {"name": str(table_name), "schema": str(table_schema), "columns": []},
                )
                bucket["columns"].append(
                    {
                        "name": str(column_name),
                        "type": str(data_type),
                        "nullable": str(is_nullable) == "YES",
                    }
                )
            return {"tables": list(tables.values()), "tableCount": len(tables)}
        finally:
            conn.close()

    return await asyncio.to_thread(_run)


async def _test_bigquery(config: dict[str, Any]) -> dict[str, Any]:
    project_id = str(config.get("project_id") or "").strip()
    credentials_json = str(config.get("credentials_json") or "").strip()
    if not project_id or not credentials_json:
        raise ConnectionTestError("Project ID and service account JSON are required")

    def _run() -> dict[str, Any]:
        try:
            from google.cloud import bigquery  # type: ignore
            from google.oauth2 import service_account  # type: ignore
        except ImportError as exc:
            raise ConnectionTestError("BigQuery driver is not installed", code="DRIVER_MISSING") from exc
        info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(info)
        client = bigquery.Client(project=project_id, credentials=credentials)
        datasets = list(client.list_datasets(max_results=100))
        table_count = 0
        for dataset in datasets[:10]:
            table_count += sum(1 for _ in client.list_tables(dataset.dataset_id, max_results=50))
        return {
            "success": True,
            "tables": table_count,
            "records": 0,
            "message": f"BigQuery reachable ({len(datasets)} datasets)",
        }

    return await asyncio.to_thread(_run)


async def _discover_bigquery_schema(config: dict[str, Any]) -> dict[str, Any]:
    project_id = str(config.get("project_id") or "").strip()
    dataset_filter = str(config.get("dataset") or "").strip()
    credentials_json = str(config.get("credentials_json") or "").strip()

    def _run() -> dict[str, Any]:
        from google.cloud import bigquery  # type: ignore
        from google.oauth2 import service_account  # type: ignore

        info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(info)
        client = bigquery.Client(project=project_id, credentials=credentials)
        tables: list[dict[str, Any]] = []
        datasets = list(client.list_datasets(max_results=20))
        for dataset in datasets:
            if dataset_filter and dataset.dataset_id != dataset_filter:
                continue
            for table in client.list_tables(dataset.dataset_id, max_results=50):
                table_ref = client.get_table(table)
                columns = [{"name": field.name, "type": field.field_type, "nullable": field.is_nullable} for field in table_ref.schema]
                tables.append(
                    {
                        "name": table.table_id,
                        "schema": dataset.dataset_id,
                        "columns": columns,
                    }
                )
        return {"tables": tables, "tableCount": len(tables)}

    return await asyncio.to_thread(_run)


async def _test_saas_connector(
    type_id: str,
    config: dict[str, Any],
    *,
    client: Any,
    org_id: str,
    environment: str,
) -> dict[str, Any]:
    spec = DATA_SOURCE_TYPES.get(type_id)
    oauth_vendor = str((spec or {}).get("oauth_vendor") or type_id)
    connector_id = str(config.get("connector_id") or "").strip()
    if not connector_id:
        raise ConnectionTestError("Linked connector ID is required")
    expected = _SAAS_CONNECTOR_VENDORS.get(oauth_vendor, oauth_vendor)
    row = (
        client.table("connectors")
        .select("id, type, status, environment, config")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise ConnectionTestError("Connector not found")
    connector = row.data[0]
    if str(connector.get("environment") or environment) != environment:
        raise ConnectionTestError("Connector environment mismatch")
    connector_type = str(connector.get("type") or "").lower()
    cfg = connector.get("config") or {}
    vendor = str(cfg.get("vendor") or connector_type).lower() if isinstance(cfg, dict) else connector_type
    if connector_type != expected and vendor != expected:
        raise ConnectionTestError(f"Expected a {expected} connector")
    if str(connector.get("status") or "").lower() not in {"active", "connected"}:
        raise ConnectionTestError("Connector is not connected")
    return {
        "success": True,
        "message": f"{spec['name'] if spec else type_id} connector linked",
        "tables": 0,
        "records": 0,
        "connectorId": connector_id,
    }


async def _test_http_url(config: dict[str, Any], *, url_key: str = "url") -> dict[str, Any]:
    url = str(config.get(url_key) or config.get("base_url") or config.get("endpoint") or "").strip()
    if not url:
        raise ConnectionTestError(f"{url_key} is required")
    headers: dict[str, str] = {}
    auth_header = str(config.get("auth_header") or "").strip()
    if auth_header:
        headers["Authorization"] = auth_header
    async with httpx.AsyncClient(timeout=_CONNECTION_TIMEOUT_SEC, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
    return {
        "success": response.status_code < 500,
        "statusCode": response.status_code,
        "message": f"HTTP {response.status_code}",
        "tables": 0,
        "records": 0,
    }


async def _test_redis(config: dict[str, Any]) -> dict[str, Any]:
    url = str(config.get("url") or "").strip()
    if not url:
        raise ConnectionTestError("Redis URL is required")
    try:
        import redis.asyncio as redis  # type: ignore
    except ImportError as exc:
        raise ConnectionTestError("Redis driver is not installed", code="DRIVER_MISSING") from exc
    client = redis.from_url(url)
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=_CONNECTION_TIMEOUT_SEC)
        return {"success": bool(pong), "message": "PONG", "tables": 0, "records": 0}
    finally:
        await client.aclose()


async def _test_config_only(type_id: str, config: dict[str, Any]) -> dict[str, Any]:
    spec = DATA_SOURCE_TYPES[type_id]
    return {
        "success": True,
        "message": f"{spec['name']} configuration validated (live driver: {spec['driver']})",
        "tables": 0,
        "records": 0,
        "driverPending": True,
    }


async def run_connection_test(
    type_id: str,
    config: dict[str, Any] | None,
    *,
    client: Any | None = None,
    org_id: str | None = None,
    environment: str = "production",
) -> dict[str, Any]:
    normalized_id = type_id.strip().lower()
    errors = validate_connection_config(normalized_id, config)
    if errors:
        raise ConnectionTestError("; ".join(errors), code="VALIDATION_ERROR")
    payload = dict(config or {})
    spec = DATA_SOURCE_TYPES.get(normalized_id) or {}

    if spec.get("driver") == "connector":
        if client is None or not org_id:
            return await _test_config_only(normalized_id, payload)
        return await _test_saas_connector(
            normalized_id,
            payload,
            client=client,
            org_id=org_id,
            environment=environment,
        )

    if normalized_id in _POSTGRES_TYPES:
        if normalized_id == "rds" and str(payload.get("engine") or "postgresql") == "mysql":
            return await _test_mysql(payload)
        if payload.get("host") or payload.get("connection_string") or normalized_id in {"neon", "supabase_db"}:
            return await _test_postgresql(payload)

    if normalized_id in _MYSQL_TYPES:
        return await _test_mysql(payload)

    if normalized_id == "mongodb":
        return await _test_mongodb(payload)

    if normalized_id == "snowflake":
        return await _test_snowflake(payload)

    if normalized_id == "bigquery":
        return await _test_bigquery(payload)

    if normalized_id in {"rest_api", "graphql", "elasticsearch", "weaviate", "qdrant"}:
        key = "endpoint" if normalized_id == "graphql" else "url" if normalized_id != "rest_api" else "base_url"
        return await _test_http_url(payload, url_key=key)

    if normalized_id == "redis":
        return await _test_redis(payload)

    if normalized_id == "linear":
        api_key = str(payload.get("api_key") or "").strip()
        if not api_key:
            raise ConnectionTestError("API key is required")
        async with httpx.AsyncClient(timeout=_CONNECTION_TIMEOUT_SEC) as http_client:
            response = await http_client.post(
                "https://api.linear.app/graphql",
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                json={"query": "{ viewer { id name } }"},
            )
        body = response.json() if response.content else {}
        ok = response.status_code == 200 and "errors" not in body
        return {
            "success": ok,
            "message": "Linear API reachable" if ok else "Linear API authentication failed",
            "tables": 0,
            "records": 0,
        }

    return await _test_config_only(normalized_id, payload)


async def discover_schema(type_id: str, config: dict[str, Any] | None) -> dict[str, Any]:
    normalized_id = type_id.strip().lower()
    errors = validate_connection_config(normalized_id, config)
    if errors:
        raise ConnectionTestError("; ".join(errors), code="VALIDATION_ERROR")
    payload = dict(config or {})

    if normalized_id in _POSTGRES_TYPES:
        if normalized_id == "rds" and str(payload.get("engine") or "postgresql") == "mysql":
            return await _discover_mysql_schema(payload)
        return await _discover_postgresql_schema(payload)

    if normalized_id in _MYSQL_TYPES:
        return await _discover_mysql_schema(payload)

    if normalized_id == "mongodb":
        return await _discover_mongodb_schema(payload)

    if normalized_id == "snowflake":
        return await _discover_snowflake_schema(payload)

    if normalized_id == "bigquery":
        return await _discover_bigquery_schema(payload)

    spec = DATA_SOURCE_TYPES.get(normalized_id)
    return {
        "tables": [],
        "tableCount": 0,
        "message": f"Schema discovery not yet implemented for {spec['name'] if spec else normalized_id}",
    }


async def execute_readonly_sql(type_id: str, config: dict[str, Any], sql: str) -> dict[str, Any]:
    """Execute a read-only SQL statement for supported relational sources."""
    normalized = sql.strip()
    if not normalized:
        raise ConnectionTestError("SQL query is empty", code="INVALID_QUERY")
    if not re.match(r"^\s*(select|with)\b", normalized, re.IGNORECASE):
        raise ConnectionTestError("Only read-only SELECT/WITH queries are allowed", code="READONLY_VIOLATION")
    if re.search(r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke)\b", normalized, re.IGNORECASE):
        raise ConnectionTestError("Mutating SQL statements are not allowed", code="READONLY_VIOLATION")

    normalized_id = type_id.strip().lower()
    if normalized_id in _POSTGRES_TYPES:
        if normalized_id == "rds" and str(config.get("engine") or "postgresql") == "mysql":
            normalized_id = "mysql"
        else:
            try:
                import asyncpg  # type: ignore
            except ImportError as exc:
                raise ConnectionTestError("PostgreSQL driver (asyncpg) is not installed", code="DRIVER_MISSING") from exc
            dsn = _postgres_dsn(config)
            conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=_CONNECTION_TIMEOUT_SEC)
            try:
                rows = await conn.fetch(normalized)
                columns = list(rows[0].keys()) if rows else []
                serialized = [dict(row) for row in rows[:200]]
                return {"columns": columns, "rows": serialized, "rowCount": len(rows)}
            finally:
                await conn.close()

    if normalized_id in _MYSQL_TYPES:
        try:
            import aiomysql  # type: ignore
        except ImportError as exc:
            raise ConnectionTestError("MySQL driver (aiomysql) is not installed", code="DRIVER_MISSING") from exc
        params = _mysql_params(config)
        conn = await asyncio.wait_for(aiomysql.connect(**params), timeout=_CONNECTION_TIMEOUT_SEC)
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:  # type: ignore[name-defined]
                await cursor.execute(normalized)
                rows = await cursor.fetchmany(200)
                columns = list(rows[0].keys()) if rows else []
                return {"columns": columns, "rows": rows, "rowCount": len(rows)}
        finally:
            conn.close()

    raise ConnectionTestError(f"SQL execution not supported for {normalized_id}", code="UNSUPPORTED")


def config_from_encrypted_blob(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {"connection_string": text}
