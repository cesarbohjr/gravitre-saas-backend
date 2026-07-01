"""Observed process patterns from workflow execution data."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.ml.feature_extraction import collect_workflow_run_features
from app.workflows.repository import get_supabase_client

CONFORMANCE_NOTE = "Conformance checking against declared processes is PLANNED."


class ProcessMiningService:
    """
    Discovers actual process patterns from workflow_runs + workflow_steps.
    Complements organization_process_inventory (declared) with observed behavior.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def discover_workflow_patterns(
        self,
        org_id: str,
        since_days: int = 30,
    ) -> dict[str, Any]:
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        steps = (
            client.table("workflow_steps")
            .select("run_id, step_name, step_type, status, started_at, completed_at")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .eq("status", "completed")
            .limit(3000)
            .execute()
            .data
            or []
        )
        sequences: dict[str, list[str]] = defaultdict(list)
        for row in steps:
            run_id = str(row.get("run_id") or "")
            name = str(row.get("step_name") or row.get("step_type") or "step")
            sequences[run_id].append(name)

        pattern_counts: Counter[str] = Counter()
        for seq in sequences.values():
            if len(seq) >= 2:
                pattern_counts[" → ".join(seq[:6])] += 1

        patterns = [
            {"sequence": sequence, "occurrences": count}
            for sequence, count in pattern_counts.most_common(15)
        ]
        features = collect_workflow_run_features(
            self.settings,
            org_id,
            since_days=since_days,
            client=client,
        )
        return {
            "status": "ok",
            "advisory_only": True,
            "sinceDays": since_days,
            "workflowRunFeatures": len(features),
            "patterns": patterns,
            "conformanceNote": CONFORMANCE_NOTE,
        }

    async def detect_process_bottlenecks(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        steps = (
            client.table("workflow_steps")
            .select("step_name, step_type, started_at, completed_at")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .eq("status", "completed")
            .limit(3000)
            .execute()
            .data
            or []
        )
        durations: dict[str, list[float]] = defaultdict(list)
        for row in steps:
            started = row.get("started_at")
            completed = row.get("completed_at")
            if not started or not completed:
                continue
            try:
                start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
                ms = max(0.0, (end_dt - start_dt).total_seconds() * 1000)
            except ValueError:
                continue
            key = str(row.get("step_name") or row.get("step_type") or "step")
            durations[key].append(ms)

        bottlenecks = []
        for name, values in durations.items():
            if len(values) < 3:
                continue
            avg_ms = sum(values) / len(values)
            bottlenecks.append(
                {
                    "stepName": name,
                    "sampleSize": len(values),
                    "avgDurationMs": round(avg_ms, 2),
                }
            )
        bottlenecks.sort(key=lambda item: item["avgDurationMs"], reverse=True)
        return {
            "status": "ok",
            "advisory_only": True,
            "bottlenecks": bottlenecks[:15],
        }

    async def get_approval_cycle_analysis(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        rows = (
            client.table("approvals")
            .select("id, status, created_at, resolved_at, entity_type")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .limit(1000)
            .execute()
            .data
            or []
        )
        cycle_ms: list[float] = []
        by_type: Counter[str] = Counter()
        for row in rows:
            by_type[str(row.get("entity_type") or "unknown")] += 1
            created = row.get("created_at")
            resolved = row.get("resolved_at")
            if not created or not resolved:
                continue
            try:
                start_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(resolved).replace("Z", "+00:00"))
                cycle_ms.append(max(0.0, (end_dt - start_dt).total_seconds() * 1000))
            except ValueError:
                continue
        avg_cycle = round(sum(cycle_ms) / len(cycle_ms), 2) if cycle_ms else None
        return {
            "status": "ok",
            "advisory_only": True,
            "approvalCount": len(rows),
            "resolvedCount": len(cycle_ms),
            "avgCycleMs": avg_cycle,
            "byEntityType": dict(by_type),
        }


_process_mining_service: ProcessMiningService | None = None


def get_process_mining_service(settings: Settings | None = None) -> ProcessMiningService:
    global _process_mining_service
    if _process_mining_service is None or settings is not None:
        _process_mining_service = ProcessMiningService(settings)
    return _process_mining_service
