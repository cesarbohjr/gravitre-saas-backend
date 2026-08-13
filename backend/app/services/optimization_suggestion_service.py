"""v10 Optimization Suggestions — evidence-backed, human-gated; never auto-applies changes."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.source_reliability import MIN_OUTCOMES_FOR_SCORING, compute_source_reliability
from app.services.answer_explanation import generate_suggestion_explanation
from app.services.outcome_attribution_service import MIN_SAMPLE_SIZE, get_outcome_attribution_service
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

MIN_SLOW_STEP_RUNS = 8
SLOW_STEP_MULTIPLIER = 2.5
LOW_RELIABILITY_THRESHOLD = 0.4
POOR_OUTCOME_WIN_RATE = 0.35
PREVIEW_TOKEN_TTL_SECONDS = 300
DEFAULT_CACHE_TTL_SECONDS = 300
ONE_CLICK_APPLY_SUGGESTION_TYPE = "slow_step"

ALLOWED_STATUSES = frozenset({"pending_review", "applied", "dismissed"})

PRODUCTION_TABLE_NAMES = (
    "workflows",
    "workflow_defs",
    "workflow_nodes",
    "agents",
    "training_instructions",
    "connectors",
)

APPLY_ALLOWED_PRODUCTION_TABLES = frozenset({"workflow_nodes"})


class OptimizationSuggestionService:
    """Read-only analysis over existing signals; writes only to optimization_suggestions."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def _record_recommendation_outcome(
        self,
        org_id: str,
        suggestion_id: str,
        outcome_event: str,
        *,
        task_type: str | None = None,
    ) -> None:
        try:
            from app.services.outcome_learning_service import get_outcome_learning_service

            await get_outcome_learning_service(self.settings).record_recommendation_outcome(
                org_id=org_id,
                recommendation_id=suggestion_id,
                outcome_event=outcome_event,
                task_type=task_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "recommendation_outcome_skipped id=%s event=%s error=%s",
                suggestion_id,
                outcome_event,
                exc,
            )

    async def detect_suggestions_for_org(self, org_id: str) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []
        suggestions.extend(await self._detect_slow_steps(org_id))
        suggestions.extend(await self._detect_low_reliability_references(org_id))
        suggestions.extend(await self._detect_poor_outcome_patterns(org_id))
        suggestions.extend(await self._detect_post_publish_marketing_underperformance(org_id))
        suggestions.extend(await self._detect_duplicate_steps(org_id))
        suggestions.extend(await self._detect_stalled_deals(org_id))
        suggestions.extend(await self._detect_overdue_invoices(org_id))
        suggestions.extend(await self._detect_support_backlog_growth(org_id))
        suggestions.extend(await self._detect_process_mining_bottlenecks(org_id))
        suggestions.extend(await self._detect_process_sequences(org_id))
        return suggestions

    async def _detect_process_sequences(self, org_id: str) -> list[dict[str, Any]]:
        """SUGGEST-ONLY process sequences — never auto-adopt into inventory."""
        from app.services.process_mining_service import get_process_mining_service

        mining = get_process_mining_service(self.settings)
        result = await mining.suggest_process_sequences(org_id)
        assert result.get("advisory_only") is True
        assert result.get("auto_adopted") is False
        out: list[dict[str, Any]] = []
        for row in result.get("suggestions") or []:
            if row.get("deduped"):
                continue
            out.append(row)
        return out

    async def _detect_process_mining_bottlenecks(self, org_id: str) -> list[dict[str, Any]]:
        from app.services.process_mining_service import get_process_mining_service

        mining = get_process_mining_service(self.settings)
        bottlenecks = await mining.detect_process_bottlenecks(org_id)
        suggestions: list[dict[str, Any]] = []
        for row in bottlenecks.get("bottlenecks") or []:
            step_name = str(row.get("stepName") or row.get("step_name") or "unknown_step")
            evidence = {
                "source": "process_mining_service.detect_process_bottlenecks",
                "step_name": step_name,
                "avg_duration_ms": row.get("avgDurationMs") or row.get("avg_duration_ms"),
                "occurrences": row.get("sampleSize") or row.get("occurrences") or row.get("count"),
            }
            suggestions.append(
                await self._insert_suggestion(
                    org_id,
                    target_entity_type="workflow_node",
                    target_entity_id=step_name,
                    suggestion_type="process_bottleneck",
                    evidence=evidence,
                    suggested_action=(
                        f'Process mining flagged "{step_name}" as a recurring bottleneck. '
                        "Review workflow design before automating further."
                    ),
                    estimated_impact=str(row.get("estimated_impact") or "Reduce end-to-end workflow latency"),
                )
            )
        return suggestions

    async def _detect_slow_steps(self, org_id: str) -> list[dict[str, Any]]:
        client = self._client()
        since = (self._now() - timedelta(days=30)).isoformat()
        steps = (
            client.table("workflow_steps")
            .select("run_id, step_id, step_name, step_type, started_at, completed_at")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .eq("status", "completed")
            .limit(2000)
            .execute()
            .data
            or []
        )
        durations_by_name: dict[str, list[float]] = {}
        for row in steps:
            started = row.get("started_at")
            completed = row.get("completed_at")
            if not started or not completed:
                continue
            try:
                start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
                ms = (end_dt - start_dt).total_seconds() * 1000.0
            except (TypeError, ValueError):
                continue
            if ms <= 0:
                continue
            name = str(row.get("step_name") or row.get("step_id") or "step")
            durations_by_name.setdefault(name, []).append(ms)

        suggestions: list[dict[str, Any]] = []
        for step_name, values in durations_by_name.items():
            if len(values) < MIN_SLOW_STEP_RUNS:
                continue
            baseline = sorted(values)[len(values) // 2]
            recent = values[-10:]
            slow_count = sum(1 for v in recent if v >= baseline * SLOW_STEP_MULTIPLIER)
            if slow_count < max(3, len(recent) // 2):
                continue
            avg_recent = sum(recent) / len(recent)
            evidence = {
                "source": "workflow_steps.duration",
                "step_name": step_name,
                "baseline_ms": baseline,
                "recent_avg_ms": avg_recent,
                "slow_run_count": slow_count,
                "recent_run_count": len(recent),
            }
            estimated = None
            if baseline > 0:
                reduction = max(0.0, 1.0 - (baseline / avg_recent))
                if reduction > 0.05:
                    estimated = f"~{int(reduction * 100)}% reduction in average run duration if step latency returns to baseline"
            suggestions.append(
                await self._insert_suggestion(
                    org_id,
                    target_entity_type="workflow_node",
                    target_entity_id=step_name,
                    suggestion_type="slow_step",
                    evidence=evidence,
                    suggested_action=(
                        f'Step "{step_name}" has taken {avg_recent / baseline:.1f}x longer than baseline '
                        f"in {slow_count} of the last {len(recent)} runs. Consider adding a timeout or caching."
                    ),
                    estimated_impact=estimated,
                )
            )
        return suggestions

    async def _detect_low_reliability_references(self, org_id: str) -> list[dict[str, Any]]:
        client = self._client()
        rows = (
            client.table("rag_chunk_outcomes")
            .select("source_document_id, outcome_helpful")
            .eq("org_id", org_id)
            .not_.is_("outcome_helpful", "null")
            .execute()
            .data
            or []
        )
        totals: dict[str, list[bool]] = {}
        for row in rows:
            doc_id = str(row.get("source_document_id") or "").strip()
            if not doc_id:
                continue
            totals.setdefault(doc_id, []).append(bool(row.get("outcome_helpful")))

        suggestions: list[dict[str, Any]] = []
        for doc_id, outcomes in totals.items():
            reliability = compute_source_reliability(sum(1 for v in outcomes if v), len(outcomes))
            if reliability is None or reliability >= LOW_RELIABILITY_THRESHOLD:
                continue
            evidence = {
                "source": "rag_chunk_outcomes",
                "source_document_id": doc_id,
                "reliability_score": reliability,
                "total_outcomes": len(outcomes),
                "min_outcomes_for_scoring": MIN_OUTCOMES_FOR_SCORING,
            }
            suggestions.append(
                await self._insert_suggestion(
                    org_id,
                    target_entity_type="rag_source_reference",
                    target_entity_id=doc_id,
                    suggestion_type="low_reliability_source",
                    evidence=evidence,
                    suggested_action=(
                        f"RAG source {doc_id} has reliability {reliability:.0%} over {len(outcomes)} scored outcomes. "
                        "Review freshness or reduce reliance in prompts/workflows."
                    ),
                    estimated_impact=None,
                )
            )
        return suggestions

    async def _detect_poor_outcome_patterns(self, org_id: str) -> list[dict[str, Any]]:
        outcome_service = get_outcome_attribution_service(self.settings)
        client = self._client()
        agents = (
            client.table("agents")
            .select("id, name")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        suggestions: list[dict[str, Any]] = []
        for agent in agents:
            agent_id = str(agent.get("id") or "")
            if not agent_id:
                continue
            summary = await outcome_service.get_agent_outcome_summary(org_id, agent_id)
            if not summary.get("sufficientData"):
                continue
            win_rate = float(summary.get("winRate") or 0.0)
            if win_rate >= POOR_OUTCOME_WIN_RATE:
                continue
            evidence = {
                "source": "agent_action_outcomes",
                "agent_id": agent_id,
                "win_rate": win_rate,
                "sample_size": summary.get("sampleSize"),
                "avg_metric_delta": summary.get("avgMetricDelta"),
            }
            suggestions.append(
                await self._insert_suggestion(
                    org_id,
                    target_entity_type="agent_prompt",
                    target_entity_id=agent_id,
                    suggestion_type="poor_outcome_pattern",
                    evidence=evidence,
                    suggested_action=(
                        f"Agent {agent.get('name') or agent_id} shows a {win_rate:.0%} positive outcome rate "
                        f"over {summary.get('sampleSize')} measured actions. Review approach with operators."
                    ),
                    estimated_impact=None,
                )
            )
        return suggestions

    async def _detect_post_publish_marketing_underperformance(
        self,
        org_id: str,
    ) -> list[dict[str, Any]]:
        from app.services.post_publish_marketing_metrics_service import (
            MARKETING_ENTITY_TYPES,
            MARKETING_UNDERPERFORMANCE_DELTA_RATIO,
            MIN_MARKETING_SUGGESTION_SAMPLES,
        )

        client = self._client()
        rows = (
            client.table("agent_action_outcomes")
            .select("*")
            .eq("org_id", org_id)
            .not_.is_("measured_at", "null")
            .limit(1000)
            .execute()
            .data
            or []
        )
        grouped: dict[tuple[str, str, str], list[float]] = {}
        for row in rows:
            entity_type = str(row.get("target_entity_type") or "")
            if entity_type not in MARKETING_ENTITY_TYPES:
                continue
            before = row.get("metric_value_before")
            after = row.get("metric_value_after")
            if before is None or after is None:
                continue
            try:
                before_val = float(before)
                after_val = float(after)
            except (TypeError, ValueError):
                continue
            if before_val <= 0:
                delta_ratio = after_val - before_val
            else:
                delta_ratio = (after_val - before_val) / before_val
            key = (
                entity_type,
                str(row.get("target_entity_id") or ""),
                str(row.get("metric_name") or ""),
            )
            grouped.setdefault(key, []).append(delta_ratio)

        suggestions: list[dict[str, Any]] = []
        for (entity_type, entity_id, metric_name), deltas in grouped.items():
            if len(deltas) < MIN_MARKETING_SUGGESTION_SAMPLES:
                continue
            avg_delta = sum(deltas) / len(deltas)
            if avg_delta >= MARKETING_UNDERPERFORMANCE_DELTA_RATIO:
                continue
            evidence = {
                "source": "post_publish_marketing_metrics",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metric_name": metric_name,
                "avg_delta_ratio": avg_delta,
                "sample_size": len(deltas),
            }
            suggestions.append(
                await self._insert_suggestion(
                    org_id,
                    target_entity_type=entity_type,
                    target_entity_id=entity_id,
                    suggestion_type="post_publish_marketing_underperformance",
                    evidence=evidence,
                    suggested_action=(
                        f"Published {entity_type.replace('_', ' ')} `{entity_id}` shows "
                        f"{avg_delta:.0%} average change in {metric_name} after publish "
                        f"({len(deltas)} samples). Review creative, targeting, or channel mix."
                    ),
                    estimated_impact=None,
                )
            )
        return suggestions

    async def _detect_duplicate_steps(self, org_id: str) -> list[dict[str, Any]]:
        client = self._client()
        workflows = (
            client.table("workflows")
            .select("id, name, nodes")
            .eq("org_id", org_id)
            .limit(100)
            .execute()
            .data
            or []
        )
        suggestions: list[dict[str, Any]] = []
        for wf in workflows:
            nodes = wf.get("nodes") or []
            if not isinstance(nodes, list):
                continue
            signatures: dict[str, list[str]] = {}
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                config = node.get("config") if isinstance(node.get("config"), dict) else {}
                connector_id = str(
                    node.get("connector_id") or config.get("connector_id") or ""
                ).strip()
                action = str(
                    config.get("action")
                    or config.get("tool_type")
                    or node.get("node_type")
                    or node.get("type")
                    or ""
                ).strip()
                if not connector_id and not action:
                    continue
                sig = f"{connector_id}|{action}"
                title = str(node.get("title") or node.get("name") or node.get("id") or "node")
                signatures.setdefault(sig, []).append(title)
            for sig, titles in signatures.items():
                if len(titles) < 2:
                    continue
                evidence = {
                    "source": "workflows.nodes",
                    "workflow_id": wf.get("id"),
                    "signature": sig,
                    "node_titles": titles,
                }
                suggestions.append(
                    await self._insert_suggestion(
                        org_id,
                        target_entity_type="workflow",
                        target_entity_id=str(wf.get("id") or ""),
                        suggestion_type="duplicate_step",
                        evidence=evidence,
                        suggested_action=(
                            f'Workflow "{wf.get("name")}" has {len(titles)} nodes with similar connector/action '
                            f"({sig}). Consider consolidating redundant steps."
                        ),
                        estimated_impact=None,
                    )
                )
        return suggestions

    async def _detect_stalled_deals(self, org_id: str) -> list[dict[str, Any]]:
        """Deals with v8 baselines but no measurement after attribution window (connector-backed signal)."""
        client = self._client()
        cutoff = self._now() - timedelta(days=21)
        rows = (
            client.table("agent_action_outcomes")
            .select("*")
            .eq("org_id", org_id)
            .eq("target_entity_type", "deal")
            .is_("measured_at", "null")
            .lt("action_taken_at", cutoff.isoformat())
            .limit(200)
            .execute()
            .data
            or []
        )
        if len(rows) < MIN_SAMPLE_SIZE:
            return []
        deal_ids = sorted({str(r.get("target_entity_id") or "") for r in rows if r.get("target_entity_id")})
        evidence = {
            "source": "agent_action_outcomes",
            "signal": "stalled_deal_measurement",
            "deal_ids": deal_ids[:10],
            "sample_size": len(rows),
            "confidence_note": (
                "correlational only; stalled status inferred from unmeasured v8 baselines past window"
            ),
        }
        return [
            await self._insert_suggestion(
                org_id,
                target_entity_type="deal",
                target_entity_id=deal_ids[0],
                suggestion_type="stalled_deal",
                evidence=evidence,
                suggested_action=(
                    f"{len(deal_ids)} deal(s) have outcome baselines with no follow-up measurement "
                    f"after the attribution window. Review pipeline stage and owner activity."
                ),
                estimated_impact=None,
            )
        ]

    async def _detect_overdue_invoices(self, org_id: str) -> list[dict[str, Any]]:
        from app.connectors.quickbooks import QuickBooksAPIError, list_invoices
        from app.connectors.quickbooks_oauth import ensure_quickbooks_session
        from app.connectors.repository import get_connector_by_type

        client = self._client()
        conn = get_connector_by_type(client, org_id, "quickbooks", environment_name="default")
        if not conn:
            return []
        cid = str(conn["id"])
        token, _realm, api_base, err = ensure_quickbooks_session(
            client,
            org_id,
            cid,
            self.settings,
            environment_name=str(conn.get("environment") or "default"),
        )
        if err or not token or not api_base:
            logger.debug("overdue_invoice_detector_auth_failed org=%s error=%s", org_id, err)
            return []
        try:
            data = list_invoices(api_base, token, max_results=100)
        except QuickBooksAPIError as exc:
            logger.debug("overdue_invoice_detector_fetch_failed org=%s error=%s", org_id, exc)
            return []

        query_response = data.get("QueryResponse") if isinstance(data, dict) else {}
        invoice_rows = query_response.get("Invoice") if isinstance(query_response, dict) else []
        if isinstance(invoice_rows, dict):
            invoice_rows = [invoice_rows]
        if not isinstance(invoice_rows, list):
            invoice_rows = []
        today = self._now().date()
        overdue: list[dict[str, Any]] = []
        for invoice in invoice_rows:
            if not isinstance(invoice, dict):
                continue
            due_raw = invoice.get("DueDate")
            balance_raw = invoice.get("Balance")
            if not due_raw:
                continue
            try:
                due_date = datetime.fromisoformat(str(due_raw)).date()
                balance = float(balance_raw or 0)
            except (TypeError, ValueError):
                continue
            if balance > 0 and due_date < today:
                overdue.append(
                    {
                        "id": str(invoice.get("Id") or ""),
                        "due_date": str(due_raw),
                        "balance": balance,
                    }
                )
        if not overdue:
            return []
        evidence = {
            "source": "quickbooks.invoices.list",
            "overdue_count": len(overdue),
            "sample_invoices": overdue[:5],
            "confidence_note": "connector read at detection time; balances may change externally",
        }
        return [
            await self._insert_suggestion(
                org_id,
                target_entity_type="invoice",
                target_entity_id=str(overdue[0].get("id") or "unknown"),
                suggestion_type="overdue_invoice",
                evidence=evidence,
                suggested_action=(
                    f"{len(overdue)} QuickBooks invoice(s) are past due with open balances. "
                    "Review collections workflow or payment follow-up."
                ),
                estimated_impact=None,
            )
        ]

    async def _detect_support_backlog_growth(self, org_id: str) -> list[dict[str, Any]]:
        from app.connectors.connector_tool_auth import resolve_zendesk_auth
        from app.connectors.repository import get_connector_by_type
        from app.connectors.zendesk import ZendeskAPIError, list_tickets

        client = self._client()
        conn = get_connector_by_type(client, org_id, "zendesk", environment_name="default")
        if not conn:
            return []
        try:
            subdomain, email, api_token, oauth_token = resolve_zendesk_auth(
                client,
                org_id,
                str(conn["id"]),
                self.settings,
                environment_name=str(conn.get("environment") or "default"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("support_backlog_detector_auth_failed org=%s error=%s", org_id, exc)
            return []
        try:
            open_tickets = list_tickets(
                subdomain,
                email,
                api_token,
                status="open",
                limit=100,
                oauth_access_token=oauth_token,
            )
        except ZendeskAPIError as exc:
            logger.debug("support_backlog_detector_fetch_failed org=%s error=%s", org_id, exc)
            return []

        open_count = len(open_tickets)
        if open_count < 25:
            return []
        evidence = {
            "source": "zendesk.tickets.list",
            "open_ticket_count": open_count,
            "confidence_note": "snapshot at detection time; not a trend unless compared historically",
        }
        return [
            await self._insert_suggestion(
                org_id,
                target_entity_type="support_ticket",
                target_entity_id="backlog",
                suggestion_type="support_backlog_growth",
                evidence=evidence,
                suggested_action=(
                    f"Zendesk shows {open_count} open tickets. Review staffing, SLA risk, and triage automation."
                ),
                estimated_impact=None,
            )
        ]

    async def _insert_suggestion(
        self,
        org_id: str,
        *,
        target_entity_type: str,
        target_entity_id: str,
        suggestion_type: str,
        evidence: dict[str, Any],
        suggested_action: str,
        estimated_impact: str | None,
    ) -> dict[str, Any]:
        client = self._client()
        payload = {
            "org_id": org_id,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
            "suggestion_type": suggestion_type,
            "evidence": evidence,
            "suggested_action": suggested_action,
            "estimated_impact": estimated_impact,
            "status": "pending_review",
        }
        inserted = client.table("optimization_suggestions").insert(payload).execute()
        row = inserted.data[0] if inserted.data else payload
        suggestion_id = str(row.get("id") or "")
        if suggestion_id:
            await self._record_recommendation_outcome(
                org_id,
                suggestion_id,
                "recommendation_created",
                task_type=suggestion_type,
            )
        return row

    async def get_summary(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        rows = (
            client.table("optimization_suggestions")
            .select("suggestion_type, status, estimated_impact")
            .eq("org_id", org_id)
            .eq("status", "pending_review")
            .execute()
            .data
            or []
        )
        by_type: dict[str, int] = {
            "slow_step": 0,
            "low_reliability_source": 0,
            "poor_outcome_pattern": 0,
            "duplicate_step": 0,
            "stalled_deals": 0,
            "overdue_invoices": 0,
        }
        high_impact = 0
        hours_saved = 0.0
        for row in rows:
            stype = str(row.get("suggestion_type") or "")
            key = stype
            if stype == "stalled_deal":
                key = "stalled_deals"
            elif stype == "overdue_invoice":
                key = "overdue_invoices"
            if key in by_type:
                by_type[key] += 1
            impact = str(row.get("estimated_impact") or "")
            if "high" in impact.lower() or "%" in impact:
                high_impact += 1
            if "hour" in impact.lower():
                hours_saved += 1.0
        return {
            "pending_suggestions": len(rows),
            "high_impact_count": high_impact,
            "estimated_hours_saved": round(hours_saved, 2),
            "by_type": by_type,
        }

    async def list_suggestions(
        self,
        org_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        client = self._client()
        query = (
            client.table("optimization_suggestions")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        result = query.range(offset, offset + limit - 1).execute()
        rows = result.data or []
        return {
            "suggestions": [_serialize_suggestion(row) for row in rows],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": int(result.count or len(rows)),
            },
        }

    async def get_suggestion(self, org_id: str, suggestion_id: str) -> dict[str, Any]:
        client = self._client()
        result = (
            client.table("optimization_suggestions")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", suggestion_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise ValueError("Optimization suggestion not found")
        return _serialize_suggestion(result.data[0])

    async def dismiss_suggestion(
        self,
        org_id: str,
        suggestion_id: str,
        *,
        reviewed_by: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        update = {
            "status": "dismissed",
            "reviewed_at": self._now().isoformat(),
        }
        if reviewed_by:
            update["reviewed_by"] = reviewed_by
        if reason:
            evidence_patch = {"dismiss_reason": reason}
            rows = (
                client.table("optimization_suggestions")
                .select("evidence")
                .eq("id", suggestion_id)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                merged = safe_normalize_stored_dict(rows[0], key="evidence")
                merged.update(evidence_patch)
                update["evidence"] = merged
        updated = (
            client.table("optimization_suggestions")
            .update(update)
            .eq("id", suggestion_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not updated.data:
            raise ValueError("Optimization suggestion not found")
        await self._record_recommendation_outcome(org_id, suggestion_id, "recommendation_rejected")
        return _serialize_suggestion(updated.data[0])

    async def _load_suggestion(self, org_id: str, suggestion_id: str) -> dict[str, Any]:
        client = self._client()
        rows = (
            client.table("optimization_suggestions")
            .select("*")
            .eq("id", suggestion_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("Optimization suggestion not found")
        return rows[0]

    async def _find_nodes_for_step_name(
        self,
        org_id: str,
        step_name: str,
    ) -> list[dict[str, Any]]:
        client = self._client()
        rows = (
            client.table("workflow_nodes")
            .select("id, workflow_id, title, name, config, tool_config")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        matches: list[dict[str, Any]] = []
        target = str(step_name or "").strip().lower()
        for row in rows:
            title = str(row.get("title") or "").strip().lower()
            name = str(row.get("name") or "").strip().lower()
            if target and (title == target or name == target):
                matches.append(row)
        return matches

    async def generate_apply_preview(self, org_id: str, suggestion_id: str) -> dict[str, Any]:
        suggestion = await self._load_suggestion(org_id, suggestion_id)
        if suggestion.get("status") != "pending_review":
            raise ValueError("Only pending_review suggestions can be previewed for apply")
        if suggestion.get("suggestion_type") != ONE_CLICK_APPLY_SUGGESTION_TYPE:
            raise ValueError(
                "One-click apply is only available for slow_step suggestions in this release."
            )
        step_name = str(suggestion.get("target_entity_id") or "").strip()
        nodes = await self._find_nodes_for_step_name(org_id, step_name)
        if not nodes:
            raise ValueError(f"No workflow node found matching step name '{step_name}'")
        node = nodes[0]
        config = safe_normalize_stored_dict(node, key="config")
        before_config = dict(config)
        after_config = dict(config)
        after_config["cache_ttl_seconds"] = DEFAULT_CACHE_TTL_SECONDS
        preview_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(preview_token.encode("utf-8")).hexdigest()
        expires_at = (self._now() + timedelta(seconds=PREVIEW_TOKEN_TTL_SECONDS)).isoformat()
        evidence = safe_normalize_stored_dict(suggestion, key="evidence")
        evidence["apply_preview"] = {
            "token_hash": token_hash,
            "expires_at": expires_at,
            "node_id": str(node.get("id") or ""),
            "workflow_id": str(node.get("workflow_id") or ""),
            "before_config": before_config,
            "after_config": after_config,
        }
        client = self._client()
        client.table("optimization_suggestions").update({"evidence": evidence}).eq(
            "id", suggestion_id
        ).eq("org_id", org_id).execute()
        return {
            "suggestionId": suggestion_id,
            "suggestionType": ONE_CLICK_APPLY_SUGGESTION_TYPE,
            "previewToken": preview_token,
            "expiresAt": expires_at,
            "before": {"nodeId": node.get("id"), "config": before_config},
            "after": {"nodeId": node.get("id"), "config": after_config},
            "diffSummary": (
                f"Add cache_ttl_seconds={DEFAULT_CACHE_TTL_SECONDS} to node "
                f"'{node.get('title') or step_name}' config"
            ),
        }

    async def apply_suggestion(
        self,
        org_id: str,
        suggestion_id: str,
        *,
        preview_token: str,
        reviewed_by: str | None,
    ) -> dict[str, Any]:
        suggestion = await self._load_suggestion(org_id, suggestion_id)
        if suggestion.get("suggestion_type") != ONE_CLICK_APPLY_SUGGESTION_TYPE:
            raise ValueError(
                "One-click apply is only available for slow_step suggestions in this release."
            )
        if suggestion.get("status") != "pending_review":
            raise ValueError("Suggestion is not pending review")
        evidence = safe_normalize_stored_dict(suggestion, key="evidence")
        preview = evidence.get("apply_preview") if isinstance(evidence.get("apply_preview"), dict) else {}
        if not preview:
            raise ValueError("Apply preview must be generated before applying")
        expires_at_raw = preview.get("expires_at")
        if not expires_at_raw:
            raise ValueError("Apply preview is missing expiry")
        expires_at = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
        if self._now() > expires_at:
            raise ValueError("Apply preview token has expired")
        token_hash = hashlib.sha256(str(preview_token or "").encode("utf-8")).hexdigest()
        if token_hash != str(preview.get("token_hash") or ""):
            raise ValueError("Invalid apply preview token")
        node_id = str(preview.get("node_id") or "")
        before_config = safe_normalize_stored_dict(preview, key="before_config")
        after_config = safe_normalize_stored_dict(preview, key="after_config")
        if set(after_config.keys()) - set(before_config.keys()) - {"cache_ttl_seconds"}:
            raise ValueError("Previewed change touches more than cache_ttl_seconds")
        if after_config.get("cache_ttl_seconds") != DEFAULT_CACHE_TTL_SECONDS:
            raise ValueError("Previewed cache_ttl_seconds mismatch")
        client = self._client()
        updated_node = (
            client.table("workflow_nodes")
            .update({"config": after_config})
            .eq("id", node_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not updated_node.data:
            raise ValueError("Workflow node not found for apply")
        diff_summary = (
            f"Set cache_ttl_seconds={DEFAULT_CACHE_TTL_SECONDS} on workflow node {node_id}"
        )
        write_audit_event(
            client,
            org_id=org_id,
            action="optimization_suggestion.apply",
            actor_id=reviewed_by or "",
            resource_type="workflow_node",
            resource_id=node_id,
            metadata={
                "suggestion_id": suggestion_id,
                "suggestion_type": ONE_CLICK_APPLY_SUGGESTION_TYPE,
                "before_config": before_config,
                "after_config": after_config,
            },
        )
        updated = (
            client.table("optimization_suggestions")
            .update(
                {
                    "status": "applied",
                    "reviewed_by": reviewed_by,
                    "reviewed_at": self._now().isoformat(),
                    "applied_change_summary": diff_summary,
                }
            )
            .eq("id", suggestion_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not updated.data:
            raise ValueError("Optimization suggestion not found")
        await self._record_recommendation_outcome(org_id, suggestion_id, "recommendation_approved")
        return _serialize_suggestion(updated.data[0])

    async def mark_applied(
        self,
        org_id: str,
        suggestion_id: str,
        *,
        reviewed_by: str | None,
        applied_change_summary: str,
    ) -> dict[str, Any]:
        """Records human action only — does not modify production entities."""
        client = self._client()
        updated = (
            client.table("optimization_suggestions")
            .update(
                {
                    "status": "applied",
                    "reviewed_by": reviewed_by,
                    "reviewed_at": self._now().isoformat(),
                    "applied_change_summary": applied_change_summary,
                }
            )
            .eq("id", suggestion_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not updated.data:
            raise ValueError("Optimization suggestion not found")
        await self._record_recommendation_outcome(org_id, suggestion_id, "recommendation_approved")
        return _serialize_suggestion(updated.data[0])


def _serialize_suggestion(row: dict[str, Any]) -> dict[str, Any]:
    serialized = {
        "id": row.get("id"),
        "targetEntityType": row.get("target_entity_type"),
        "targetEntityId": row.get("target_entity_id"),
        "suggestionType": row.get("suggestion_type"),
        "evidence": row.get("evidence") or {},
        "suggestedAction": row.get("suggested_action"),
        "estimatedImpact": row.get("estimated_impact"),
        "status": row.get("status"),
        "reviewedBy": row.get("reviewed_by"),
        "reviewedAt": row.get("reviewed_at"),
        "appliedChangeSummary": row.get("applied_change_summary"),
        "createdAt": row.get("created_at"),
    }
    serialized["explanation"] = generate_suggestion_explanation(
        {
            "suggestion_type": row.get("suggestion_type"),
            "evidence": row.get("evidence") or {},
            "estimated_impact": row.get("estimated_impact"),
        }
    )
    return serialized


_optimization_suggestion_service: OptimizationSuggestionService | None = None


def get_optimization_suggestion_service(
    settings: Settings | None = None,
) -> OptimizationSuggestionService:
    global _optimization_suggestion_service
    if settings is not None:
        return OptimizationSuggestionService(settings=settings)
    if _optimization_suggestion_service is None:
        _optimization_suggestion_service = OptimizationSuggestionService()
    return _optimization_suggestion_service
