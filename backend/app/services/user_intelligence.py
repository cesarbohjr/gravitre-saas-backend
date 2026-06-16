"""User query pattern learning and personalized assistant suggestions."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("workflow_status", re.compile(r"workflow|run|failed|failure", re.I)),
    ("agent_status", re.compile(r"agent|operator|active", re.I)),
    ("connector_health", re.compile(r"connector|integration|sync|auth", re.I)),
    ("analytics", re.compile(r"analytics|metric|performance|report", re.I)),
    ("help", re.compile(r"how do i|how to|create|build|setup", re.I)),
]


def classify_query(query: str) -> str:
    text = query.strip()
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    return "general"


class UserIntelligenceService:
    """Learns from user queries to personalize assistant UX."""

    async def record_query(
        self,
        settings: Any,
        *,
        org_id: str,
        user_id: str,
        query: str,
        category: str | None = None,
        response_quality: float | None = None,
        model_used: str | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        try:
            client = get_supabase_client(settings)
            client.table("user_query_patterns").insert(
                {
                    "org_id": org_id,
                    "user_id": user_id,
                    "query_category": category or classify_query(query),
                    "query_text": query[:2000],
                    "response_quality": response_quality,
                    "model_used": model_used,
                    "response_time_ms": response_time_ms,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("user_query_pattern insert skipped: %s", exc)

    async def get_personalized_suggestions(
        self,
        settings: Any,
        *,
        org_id: str,
        user_id: str,
    ) -> list[str]:
        try:
            client = get_supabase_client(settings)
            since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            rows = (
                client.table("user_query_patterns")
                .select("query_category")
                .eq("user_id", user_id)
                .gte("created_at", since)
                .execute()
                .data
                or []
            )
            counts: dict[str, int] = {}
            for row in rows:
                cat = str(row.get("query_category") or "general")
                counts[cat] = counts.get(cat, 0) + 1
            top = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:3]
            categories = [cat for cat, _ in top]

            suggestions: list[str] = []
            changes = await self._get_changes_since(client, org_id)
            if "workflow_status" in categories and changes.get("failed_workflows", 0) > 0:
                count = changes["failed_workflows"]
                suggestions.append(f"Show {count} failed workflows since yesterday")
            if "agent_status" in categories:
                suggestions.append("What are my agents currently working on?")
            if "connector_health" in categories:
                suggestions.append("Are any connectors having sync issues?")
            if not suggestions:
                suggestions = [
                    "What agents are currently active?",
                    "Show failed workflows from today",
                    "Which connectors have sync errors?",
                ]
            return suggestions[:3]
        except Exception as exc:  # noqa: BLE001
            logger.debug("personalized suggestions fallback: %s", exc)
            return [
                "What agents are currently active?",
                "Show failed workflows from today",
                "Which connectors have sync errors?",
            ]

    async def get_daily_briefing(
        self,
        settings: Any,
        *,
        org_id: str,
        user_id: str,
        user_name: str | None = None,
    ) -> dict[str, Any]:
        try:
            client = get_supabase_client(settings)
            changes = await self._get_changes_since(client, org_id)
            patterns = await self.get_personalized_suggestions(
                settings, org_id=org_id, user_id=user_id
            )
            prefs = (
                client.table("user_preferences")
                .select("last_session_at")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            last_session = prefs[0].get("last_session_at") if prefs else None
            greeting = "Good morning" if datetime.now().hour < 12 else "Welcome back"
            if user_name:
                first = user_name.split()[0]
                if first and "@" not in first:
                    greeting = f"{greeting}, {first}"

            bullets: list[dict[str, str]] = []
            failed = int(changes.get("failed_workflows") or 0)
            if failed:
                bullets.append(
                    {
                        "id": "failed-workflows",
                        "text": f"{failed} workflow{'s' if failed != 1 else ''} failed recently",
                        "href": "/workflows",
                        "tone": "warning",
                    }
                )
            pending = int(changes.get("pending_auth_connectors") or 0)
            if pending:
                bullets.append(
                    {
                        "id": "pending-auth-connectors",
                        "text": f"{pending} connector{'s' if pending != 1 else ''} need authentication",
                        "href": "/connectors",
                        "tone": "error",
                    }
                )
            agent_tasks = int(changes.get("agent_tasks_completed") or 0)
            top_agent_id = str(changes.get("top_agent_id") or "").strip()
            top_agent_name = str(changes.get("top_agent_name") or "").strip()
            top_agent_tasks = int(changes.get("top_agent_task_count") or 0)
            if agent_tasks:
                if top_agent_name and top_agent_id and top_agent_tasks:
                    bullets.append(
                        {
                            "id": f"agent-{top_agent_id}",
                            "text": (
                                f"{top_agent_name} completed {top_agent_tasks} "
                                f"task{'s' if top_agent_tasks != 1 else ''} recently"
                            ),
                            "href": f"/agents/{top_agent_id}",
                            "tone": "success",
                        }
                    )
                else:
                    bullets.append(
                        {
                            "id": "agent-tasks-completed",
                            "text": (
                                f"Your agents completed {agent_tasks} "
                                f"task{'s' if agent_tasks != 1 else ''} recently"
                            ),
                            "href": "/agents",
                            "tone": "success",
                        }
                    )

            return {
                "greeting": greeting,
                "bullets": bullets,
                "suggestions": patterns,
                "lastSessionAt": last_session,
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("daily briefing fallback: %s", exc)
            return {
                "greeting": "Welcome back",
                "bullets": [],
                "suggestions": [
                    "What agents are currently active?",
                    "Show failed workflows from today",
                ],
            }

    async def touch_session(
        self,
        settings: Any,
        *,
        org_id: str,
        user_id: str,
        preferred_model: str | None = None,
        preferred_mode: str | None = None,
    ) -> None:
        try:
            client = get_supabase_client(settings)
            now = datetime.now(timezone.utc).isoformat()
            row: dict[str, Any] = {
                "user_id": user_id,
                "org_id": org_id,
                "last_session_at": now,
                "updated_at": now,
            }
            if preferred_model:
                row["preferred_model"] = preferred_model
            if preferred_mode:
                row["preferred_mode"] = preferred_mode
            client.table("user_preferences").upsert(row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("touch_session skipped: %s", exc)

    async def get_preferences(
        self,
        settings: Any,
        *,
        user_id: str,
    ) -> dict[str, Any]:
        try:
            client = get_supabase_client(settings)
            rows = (
                client.table("user_preferences")
                .select("preferred_model, preferred_mode, personalized_suggestions, last_session_at")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_preferences fallback: %s", exc)
        return {"preferred_mode": "standard", "preferred_model": None}

    async def update_preferences(
        self,
        settings: Any,
        *,
        org_id: str,
        user_id: str,
        preferred_model: str | None = None,
        preferred_mode: str | None = None,
    ) -> dict[str, Any]:
        existing = await self.get_preferences(settings, user_id=user_id)
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "user_id": user_id,
            "org_id": org_id,
            "preferred_model": preferred_model if preferred_model is not None else existing.get("preferred_model"),
            "preferred_mode": preferred_mode if preferred_mode is not None else existing.get("preferred_mode") or "standard",
            "updated_at": now,
        }
        try:
            client = get_supabase_client(settings)
            client.table("user_preferences").upsert(row).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("update_preferences skipped: %s", exc)
        return row

    async def _get_changes_since(self, client: Any, org_id: str) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        failed = 0
        pending_auth = 0
        agent_tasks_completed = 0
        top_agent_id: str | None = None
        top_agent_name: str | None = None
        top_agent_task_count = 0
        try:
            runs = (
                client.table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("status", "failed")
                .gte("created_at", since)
                .execute()
            )
            failed = int(getattr(runs, "count", None) or 0)
        except Exception:  # noqa: BLE001
            pass
        try:
            connectors = (
                client.table("connectors")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("status", "pending_auth")
                .execute()
            )
            pending_auth = int(getattr(connectors, "count", None) or 0)
        except Exception:  # noqa: BLE001
            pass
        try:
            jobs = (
                client.table("agent_jobs")
                .select("id, payload, status, finished_at")
                .eq("org_id", org_id)
                .eq("status", "completed")
                .gte("finished_at", since)
                .execute()
                .data
                or []
            )
            agent_tasks_completed = len(jobs)
            agent_counts: Counter[str] = Counter()
            for job in jobs:
                payload = job.get("payload") or {}
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {}
                if not isinstance(payload, dict):
                    continue
                agent_id = str(payload.get("agent_id") or payload.get("agentId") or "").strip()
                if agent_id:
                    agent_counts[agent_id] += 1
            if agent_counts:
                top_agent_id, top_agent_task_count = agent_counts.most_common(1)[0]
                agent_rows = (
                    client.table("agents")
                    .select("id, name")
                    .eq("org_id", org_id)
                    .eq("id", top_agent_id)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if agent_rows:
                    top_agent_name = str(agent_rows[0].get("name") or "").strip() or None
        except Exception:  # noqa: BLE001
            pass
        return {
            "failed_workflows": failed,
            "pending_auth_connectors": pending_auth,
            "agent_tasks_completed": agent_tasks_completed,
            "top_agent_id": top_agent_id,
            "top_agent_name": top_agent_name,
            "top_agent_task_count": top_agent_task_count,
        }


_intelligence_singleton: UserIntelligenceService | None = None


def get_user_intelligence_service() -> UserIntelligenceService:
    global _intelligence_singleton
    if _intelligence_singleton is None:
        _intelligence_singleton = UserIntelligenceService()
    return _intelligence_singleton
