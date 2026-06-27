"""v9 Dependency Impact Estimation — graph traversal, not organizational simulation."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

DEFAULT_LOOKBACK_DAYS = 90

SCOPE_NOTE_BASE = (
    "This report traces direct and one-hop dependency relationships only. It does "
    "not estimate financial, staffing, or revenue impact, and does not account "
    "for workarounds or manual processes not represented in Gravitre."
)

SCOPE_NOTE = SCOPE_NOTE_BASE


def build_scope_note(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> str:
    return (
        f"{SCOPE_NOTE_BASE} The 'observedInExecutionHistory' section reflects actual "
        f"tool calls in the last {lookback_days} days and may miss usage outside that "
        "window or usage that has not occurred recently enough to appear in logs."
    )

ENTITY_CONNECTOR = "connector"
ENTITY_AGENT = "agent"
ENTITY_WORKFLOW = "workflow"

SUPPORTED_ENTITY_TYPES = frozenset({ENTITY_CONNECTOR, ENTITY_AGENT, ENTITY_WORKFLOW})


class DependencyImpactService:
    """Deterministic dependency traversal with mandatory scope_note on every report."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def estimate_removal_impact(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> dict[str, Any]:
        normalized_type = str(entity_type or "").strip().lower()
        if normalized_type not in SUPPORTED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity_type: {entity_type}")

        declared = await self._find_direct_dependents(org_id, normalized_type, entity_id)
        observed: list[dict[str, Any]] = []
        if normalized_type == ENTITY_CONNECTOR:
            observed = await self._find_dynamic_connector_usage(
                org_id,
                entity_id,
                lookback_days=lookback_days,
            )
        indirect = await self._find_one_hop_further(org_id, declared)
        return {
            "entity": {"type": normalized_type, "id": entity_id},
            "directImpact": {
                "declared": declared,
                "observedInExecutionHistory": observed,
            },
            "indirectImpactOneHop": indirect,
            "scopeNote": build_scope_note(lookback_days),
            "lookbackDays": lookback_days,
        }

    async def answer_dependency_question(
        self,
        org_id: str,
        natural_language_question: str,
    ) -> dict[str, Any]:
        entity_type, entity_id, parse_source = await self._resolve_entity_from_question(
            org_id,
            natural_language_question,
        )
        if not entity_type or not entity_id:
            return {
                "parsedEntity": None,
                "parseSource": parse_source,
                "scopeNote": SCOPE_NOTE,
                "message": "Could not identify a connector, agent, or workflow from the question.",
            }
        impact = await self.estimate_removal_impact(org_id, entity_type, entity_id)
        impact["parsedEntity"] = {"type": entity_type, "id": entity_id}
        impact["parseSource"] = parse_source
        return impact

    async def _resolve_entity_from_question(
        self,
        org_id: str,
        question: str,
    ) -> tuple[str | None, str | None, str]:
        text = str(question or "").strip().lower()
        if not text:
            return None, None, "empty"

        client = self._client()
        connectors = (
            client.table("connectors")
            .select("id, type, name, status")
            .eq("org_id", org_id)
            .limit(100)
            .execute()
            .data
            or []
        )
        for row in connectors:
            ctype = str(row.get("type") or "").lower()
            name = str(row.get("name") or "").lower()
            if ctype and (ctype in text or (name and name in text)):
                return ENTITY_CONNECTOR, str(row["id"]), "deterministic_connector_match"

        agents = (
            client.table("agents")
            .select("id, name")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        for row in agents:
            name = str(row.get("name") or "").lower()
            if name and name in text:
                return ENTITY_AGENT, str(row["id"]), "deterministic_agent_match"

        workflows = (
            client.table("workflows")
            .select("id, name")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        for row in workflows:
            name = str(row.get("name") or "").lower()
            if name and name in text:
                return ENTITY_WORKFLOW, str(row["id"]), "deterministic_workflow_match"

        llm_entity = await self._llm_identify_entity_only(org_id, question, connectors, agents, workflows)
        if llm_entity:
            return llm_entity[0], llm_entity[1], "llm_entity_identification_only"
        return None, None, "unresolved"

    async def _llm_identify_entity_only(
        self,
        org_id: str,
        question: str,
        connectors: list[dict[str, Any]],
        agents: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
    ) -> tuple[str, str] | None:
        """LLM selects entity id/type only — never used for impact estimation."""
        _ = org_id
        catalog = {
            "connectors": [
                {"id": r.get("id"), "type": r.get("type"), "name": r.get("name")} for r in connectors
            ],
            "agents": [{"id": r.get("id"), "name": r.get("name")} for r in agents],
            "workflows": [{"id": r.get("id"), "name": r.get("name")} for r in workflows],
        }
        prompt = (
            "Extract ONLY which entity the user is asking about. "
            "Return JSON: {\"entity_type\":\"connector|agent|workflow\",\"entity_id\":\"uuid\"}. "
            "If unknown, return {\"entity_type\":null,\"entity_id\":null}. "
            f"Catalog: {json.dumps(catalog)}\nQuestion: {question}"
        )
        try:
            from app.services.model_router import TaskType, get_model_router

            router = get_model_router()
            response = await router.complete(
                prompt,
                task_type=TaskType.CLASSIFICATION,
                max_tokens=120,
            )
            raw = str(getattr(response, "content", None) or response or "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                return None
            parsed = json.loads(match.group(0))
            entity_type = str(parsed.get("entity_type") or "").lower()
            entity_id = str(parsed.get("entity_id") or "").strip()
            if entity_type in SUPPORTED_ENTITY_TYPES and entity_id:
                return entity_type, entity_id
        except Exception as exc:  # noqa: BLE001
            logger.debug("dependency_llm_parse_failed error=%s", exc)
        return None

    async def _find_direct_dependents(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        client = self._client()
        dependents: list[dict[str, Any]] = []

        if entity_type == ENTITY_CONNECTOR:
            connector = await self._load_connector(client, org_id, entity_id)
            connector_type = str((connector or {}).get("type") or "").lower()

            node_rows = (
                client.table("workflow_nodes")
                .select("id, workflow_id, title, node_type, connector_id")
                .eq("org_id", org_id)
                .eq("connector_id", entity_id)
                .limit(200)
                .execute()
                .data
                or []
            )
            for row in node_rows:
                dependents.append(
                    self._impact_item(
                        entity_type="workflow_node",
                        entity_id=str(row.get("id") or ""),
                        label=str(row.get("title") or row.get("id") or ""),
                        relationship="workflow_nodes.connector_id FK",
                        source={"workflow_id": row.get("workflow_id"), "node_type": row.get("node_type")},
                    )
                )

            agents = (
                client.table("agents")
                .select("id, name, systems")
                .eq("org_id", org_id)
                .limit(300)
                .execute()
                .data
                or []
            )
            for row in agents:
                systems = row.get("systems") or []
                if isinstance(systems, list) and connector_type in {
                    str(item).lower() for item in systems
                }:
                    dependents.append(
                        self._impact_item(
                            entity_type=ENTITY_AGENT,
                            entity_id=str(row.get("id") or ""),
                            label=str(row.get("name") or row.get("id") or ""),
                            relationship="agents.systems includes connector type",
                            source={"connector_type": connector_type},
                        )
                    )

            rel_rows = (
                client.table("org_entity_relationships")
                .select("*")
                .eq("org_id", org_id)
                .eq("target_entity_type", ENTITY_CONNECTOR)
                .eq("target_entity_id", entity_id)
                .limit(100)
                .execute()
                .data
                or []
            )
            for row in rel_rows:
                dependents.append(
                    self._impact_item(
                        entity_type=str(row.get("source_entity_type") or ""),
                        entity_id=str(row.get("source_entity_id") or ""),
                        label=str(row.get("source_entity_id") or ""),
                        relationship=f"org_entity_relationships:{row.get('relationship_type')}",
                        source={"relationship_id": row.get("id")},
                    )
                )

        elif entity_type == ENTITY_AGENT:
            workflows = (
                client.table("workflows")
                .select("id, name, nodes")
                .eq("org_id", org_id)
                .limit(200)
                .execute()
                .data
                or []
            )
            for wf in workflows:
                nodes = wf.get("nodes") or []
                if not isinstance(nodes, list):
                    continue
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    meta = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
                    config = node.get("config") if isinstance(node.get("config"), dict) else {}
                    agent_ref = (
                        meta.get("agent_id")
                        or config.get("agent_id")
                        or config.get("agentId")
                        or node.get("operator_id")
                    )
                    if str(agent_ref or "") == entity_id:
                        dependents.append(
                            self._impact_item(
                                entity_type=ENTITY_WORKFLOW,
                                entity_id=str(wf.get("id") or ""),
                                label=str(wf.get("name") or wf.get("id") or ""),
                                relationship="workflows.nodes references agent",
                                source={"node_id": node.get("id"), "node_type": node.get("node_type")},
                            )
                        )

            rel_rows = (
                client.table("org_entity_relationships")
                .select("*")
                .eq("org_id", org_id)
                .eq("target_entity_type", ENTITY_AGENT)
                .eq("target_entity_id", entity_id)
                .limit(100)
                .execute()
                .data
                or []
            )
            for row in rel_rows:
                dependents.append(
                    self._impact_item(
                        entity_type=str(row.get("source_entity_type") or ""),
                        entity_id=str(row.get("source_entity_id") or ""),
                        label=str(row.get("source_entity_id") or ""),
                        relationship=f"org_entity_relationships:{row.get('relationship_type')}",
                        source={"relationship_id": row.get("id")},
                    )
                )

        elif entity_type == ENTITY_WORKFLOW:
            schedules = (
                client.table("workflow_schedules")
                .select("id, name, workflow_id, enabled")
                .eq("org_id", org_id)
                .eq("workflow_id", entity_id)
                .limit(100)
                .execute()
                .data
                or []
            )
            for row in schedules:
                dependents.append(
                    self._impact_item(
                        entity_type="workflow_schedule",
                        entity_id=str(row.get("id") or ""),
                        label=str(row.get("name") or row.get("id") or ""),
                        relationship="workflow_schedules.workflow_id FK",
                        source={"enabled": row.get("enabled")},
                    )
                )

            installs = (
                client.table("marketplace_installs")
                .select("id, asset_id, installed_entity_type, installed_entity_id, status")
                .eq("org_id", org_id)
                .eq("installed_entity_type", ENTITY_WORKFLOW)
                .eq("installed_entity_id", entity_id)
                .limit(100)
                .execute()
                .data
                or []
            )
            for row in installs:
                dependents.append(
                    self._impact_item(
                        entity_type="marketplace_install",
                        entity_id=str(row.get("id") or ""),
                        label=str(row.get("asset_id") or row.get("id") or ""),
                        relationship="marketplace_installs.installed_entity_id FK",
                        source={"status": row.get("status")},
                    )
                )

        return dependents

    async def _find_one_hop_further(
        self,
        org_id: str,
        direct_dependents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        indirect: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in direct_dependents:
            entity_type = str(item.get("entityType") or "")
            entity_id = str(item.get("entityId") or "")
            if not entity_type or not entity_id:
                continue
            if entity_type not in SUPPORTED_ENTITY_TYPES:
                continue
            key = (entity_type, entity_id)
            if key in seen:
                continue
            seen.add(key)
            hop = await self._find_direct_dependents(org_id, entity_type, entity_id)
            for dep in hop:
                dep["via"] = {"entityType": entity_type, "entityId": entity_id}
                indirect.append(dep)
        return indirect

    async def _find_dynamic_connector_usage(
        self,
        org_id: str,
        connector_id: str,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> list[dict[str, Any]]:
        """
        Derive connector usage from execution logs when not declared statically.
        Sources: agent_decision_transparency_logs.tools_invoked and agent_jobs.result.tool_calls.
        """
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        grouped: dict[tuple[str, str], dict[str, Any]] = {}

        transparency_rows = (
            client.table("agent_decision_transparency_logs")
            .select("id, workflow_run_id, input_context, tools_invoked, created_at")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .limit(1000)
            .execute()
            .data
            or []
        )
        for row in transparency_rows:
            log_id = str(row.get("id") or "")
            context = row.get("input_context") if isinstance(row.get("input_context"), dict) else {}
            agent_id = str(
                context.get("agentId")
                or context.get("agent_id")
                or context.get("operatorId")
                or ""
            ).strip()
            workflow_run_id = str(row.get("workflow_run_id") or "").strip()
            for tool in row.get("tools_invoked") or []:
                if not isinstance(tool, dict):
                    continue
                if str(tool.get("connectorId") or tool.get("connector_id") or "") != connector_id:
                    continue
                entity_type = ENTITY_AGENT if agent_id else "workflow_run"
                entity_id = agent_id or workflow_run_id or log_id
                key = (entity_type, entity_id)
                bucket = grouped.setdefault(
                    key,
                    {
                        "entityType": entity_type,
                        "entityId": entity_id,
                        "label": agent_id or workflow_run_id or log_id,
                        "invocationCount": 0,
                        "relationship": (
                            "agent_decision_transparency_logs.tools_invoked connector usage"
                        ),
                        "source": {
                            "lookbackDays": lookback_days,
                            "transparencyLogIds": [],
                            "agentJobIds": [],
                        },
                    },
                )
                bucket["invocationCount"] += 1
                if log_id and log_id not in bucket["source"]["transparencyLogIds"]:
                    bucket["source"]["transparencyLogIds"].append(log_id)

        job_rows = (
            client.table("agent_jobs")
            .select("id, payload, result, created_at")
            .eq("org_id", org_id)
            .eq("status", "completed")
            .gte("created_at", since)
            .limit(1000)
            .execute()
            .data
            or []
        )
        for row in job_rows:
            job_id = str(row.get("id") or "")
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            agent_id = str(payload.get("agent_id") or payload.get("agentId") or "").strip()
            tool_calls = result.get("tool_calls") or result.get("toolCalls") or []
            if not isinstance(tool_calls, list):
                continue
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                observation = call.get("result") if isinstance(call.get("result"), dict) else {}
                matched_connector = str(
                    observation.get("connector_id")
                    or observation.get("connectorId")
                    or call.get("connector_id")
                    or call.get("connectorId")
                    or ""
                )
                if matched_connector != connector_id:
                    continue
                entity_type = ENTITY_AGENT if agent_id else "agent_job"
                entity_id = agent_id or job_id
                key = (entity_type, entity_id)
                bucket = grouped.setdefault(
                    key,
                    {
                        "entityType": entity_type,
                        "entityId": entity_id,
                        "label": agent_id or job_id,
                        "invocationCount": 0,
                        "relationship": "agent_jobs.result.tool_calls connector usage",
                        "source": {
                            "lookbackDays": lookback_days,
                            "transparencyLogIds": [],
                            "agentJobIds": [],
                        },
                    },
                )
                bucket["invocationCount"] += 1
                if job_id and job_id not in bucket["source"]["agentJobIds"]:
                    bucket["source"]["agentJobIds"].append(job_id)

        return sorted(grouped.values(), key=lambda item: int(item["invocationCount"]), reverse=True)

    async def _load_connector(self, client: Any, org_id: str, connector_id: str) -> dict[str, Any] | None:
        rows = (
            client.table("connectors")
            .select("id, type, name, status")
            .eq("org_id", org_id)
            .eq("id", connector_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    @staticmethod
    def _impact_item(
        *,
        entity_type: str,
        entity_id: str,
        label: str,
        relationship: str,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "entityType": entity_type,
            "entityId": entity_id,
            "label": label,
            "relationship": relationship,
            "source": source,
        }


_dependency_impact_service: DependencyImpactService | None = None


def get_dependency_impact_service(settings: Settings | None = None) -> DependencyImpactService:
    global _dependency_impact_service
    if settings is not None:
        return DependencyImpactService(settings=settings)
    if _dependency_impact_service is None:
        _dependency_impact_service = DependencyImpactService()
    return _dependency_impact_service
