"""ClickHouse append-only analytics replica — Postgres remains source of truth."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ClickHouseService:
    """Graceful no-op when CLICKHOUSE_HOST is unset."""

    def __init__(self) -> None:
        self._client = None
        host = (os.getenv("CLICKHOUSE_HOST") or "").strip()
        host = host.removeprefix("https://").removeprefix("http://").split("/", 1)[0].split(":", 1)[0]
        if not host:
            logger.warning(
                "CLICKHOUSE_HOST not set — analytics events will not be written to ClickHouse. "
                "Dashboards fall back to Postgres."
            )
            return

        import clickhouse_connect

        database = (os.getenv("CLICKHOUSE_DATABASE") or "gravitre").strip() or "gravitre"
        password = (
            (os.getenv("CLICKHOUSE_PASSWORD") or "").strip()
            or (os.getenv("CLICKHOUSE_SECRET_KEY") or "").strip()
        )
        port = int(os.getenv("CLICKHOUSE_PORT", "8443"))
        username = os.getenv("CLICKHOUSE_USER", "default")
        try:
            try:
                self._client = clickhouse_connect.get_client(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    database=database,
                    secure=True,
                )
            except Exception as exc:  # noqa: BLE001
                if "UNKNOWN_DATABASE" not in str(exc):
                    raise
                bootstrap = clickhouse_connect.get_client(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    database="default",
                    secure=True,
                )
                bootstrap.command(f"CREATE DATABASE IF NOT EXISTS {database}")
                self._client = clickhouse_connect.get_client(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    database=database,
                    secure=True,
                )
            self._client.query("SELECT 1")
        except Exception as exc:  # noqa: BLE001
            self._client = None
            logger.warning(
                "ClickHouse client init failed host=%s error=%s — analytics fall back to Postgres.",
                host,
                exc,
            )

    def is_available(self) -> bool:
        return self._client is not None

    async def insert_events(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not self._client or not rows:
            return
        try:
            await asyncio.to_thread(
                self._client.insert,
                table,
                rows,
                column_names=list(rows[0].keys()),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("clickhouse_insert_failed table=%s error=%s", table, exc)

    async def query(self, sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self._client:
            return []
        try:
            result = await asyncio.to_thread(self._client.query, sql, parameters=parameters or {})
            return list(result.named_results())
        except Exception as exc:  # noqa: BLE001
            logger.debug("clickhouse_query_failed error=%s", exc)
            return []


_clickhouse_service: ClickHouseService | None = None


def get_clickhouse_service() -> ClickHouseService:
    global _clickhouse_service
    if _clickhouse_service is None:
        _clickhouse_service = ClickHouseService()
    return _clickhouse_service
