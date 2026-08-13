"""Observed process patterns from workflow execution data."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from app.config import Settings, get_settings
from app.ml.feature_extraction import collect_workflow_run_features
from app.workflows.repository import get_supabase_client

CONFORMANCE_NOTE = "Conformance compares observed workflow sequences to declared process inventory."
SCOPE_NOTE = (
    "Process mining derives health and efficiency scores from observed workflow_runs "
    "and workflow_steps only. Business impact hours are estimated from timing data; "
    "cost_estimate is null without financial connector data."
)
MIN_RUNS = 10


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
            "auto_adopted": False,
            "sinceDays": since_days,
            "workflowRunFeatures": len(features),
            "patterns": patterns,
            "conformanceNote": CONFORMANCE_NOTE,
        }

    async def suggest_process_sequences(
        self,
        org_id: str,
        *,
        since_days: int = 30,
        min_occurrences: int = 3,
        department: str = "Operations",
    ) -> dict[str, Any]:
        """Mine observed sequences → optimization_suggestions (pending_review, process_sequence).

        SUGGEST-ONLY: never writes organization_process_inventory or auto-adopts
        sequences as governing reality. Always advisory_only=True.
        """
        discovered = await self.discover_workflow_patterns(org_id, since_days=since_days)
        client = self._client()
        created: list[dict[str, Any]] = []
        for pattern in discovered.get("patterns") or []:
            occurrences = int(pattern.get("occurrences") or 0)
            sequence = str(pattern.get("sequence") or "").strip()
            if not sequence or occurrences < min_occurrences:
                continue
            steps = [s.strip() for s in sequence.split("→") if s.strip()]
            evidence = {
                "source": "process_mining_service.suggest_process_sequences",
                "sequence": sequence,
                "steps": steps,
                "occurrences": occurrences,
                "since_days": since_days,
                "department": department,
                "advisory_only": True,
                "auto_adopted": False,
            }
            suggested_action = (
                f'Observed process sequence "{sequence}" ({occurrences} times). '
                "Review and accept to copy into organization_process_inventory. "
                "Not governing reality until an admin accepts."
            )
            # Dedup pending suggestions for same sequence
            existing = (
                client.table("optimization_suggestions")
                .select("id,status")
                .eq("org_id", org_id)
                .eq("suggestion_type", "process_sequence")
                .eq("target_entity_id", sequence[:200])
                .eq("status", "pending_review")
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing:
                created.append({**existing[0], "deduped": True, "advisory_only": True})
                continue
            row = {
                "org_id": org_id,
                "target_entity_type": "process_sequence",
                "target_entity_id": sequence[:200],
                "suggestion_type": "process_sequence",
                "evidence": evidence,
                "suggested_action": suggested_action,
                "estimated_impact": "Document observed process for conformance (advisory)",
                "status": "pending_review",
            }
            inserted = client.table("optimization_suggestions").insert(row).execute()
            if inserted.data:
                created.append({**inserted.data[0], "advisory_only": True, "auto_adopted": False})
        return {
            "status": "ok",
            "advisory_only": True,
            "auto_adopted": False,
            "suggestions_created": len([r for r in created if not r.get("deduped")]),
            "suggestions": created,
            "note": (
                "Process-mining suggestions are pending_review only. "
                "Admin accept copies into organization_process_inventory; never auto-adopted."
            ),
        }

    async def accept_process_sequence_suggestion(
        self,
        org_id: str,
        suggestion_id: str,
        *,
        reviewed_by: str | None = None,
        department: str | None = None,
        process_name: str | None = None,
    ) -> dict[str, Any]:
        """Admin accept: copy process_sequence suggestion into organization_process_inventory.

        Explicit human gate — never called automatically from mining.
        """
        client = self._client()
        rows = (
            client.table("optimization_suggestions")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", suggestion_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("Optimization suggestion not found")
        suggestion = rows[0]
        if str(suggestion.get("suggestion_type") or "") != "process_sequence":
            raise ValueError("Suggestion is not a process_sequence type")
        if str(suggestion.get("status") or "") != "pending_review":
            raise ValueError("Suggestion is not pending_review")

        evidence = suggestion.get("evidence") if isinstance(suggestion.get("evidence"), dict) else {}
        steps = evidence.get("steps") or []
        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split("→") if s.strip()]
        sequence = str(evidence.get("sequence") or suggestion.get("target_entity_id") or "")
        if not steps and sequence:
            steps = [s.strip() for s in sequence.split("→") if s.strip()]
        dept = (department or evidence.get("department") or "Operations").strip() or "Operations"
        name = (process_name or f"Observed: {sequence[:80]}").strip()

        inventory_row = {
            "org_id": org_id,
            "department": dept,
            "process_name": name,
            "process_owner": reviewed_by,
            "admin_entered_by": reviewed_by,
            "declared_steps": steps,
            "automation_level": "manual",
        }
        inv = client.table("organization_process_inventory").insert(inventory_row).execute()
        if not inv.data:
            raise ValueError("Failed to copy suggestion into organization_process_inventory")

        update = {
            "status": "applied",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "applied_change_summary": (
                f"Admin accepted process_sequence into organization_process_inventory "
                f"id={inv.data[0].get('id')} (advisory inventory entry; not auto-governed)."
            ),
        }
        if reviewed_by:
            update["reviewed_by"] = reviewed_by
        updated = (
            client.table("optimization_suggestions")
            .update(update)
            .eq("id", suggestion_id)
            .eq("org_id", org_id)
            .execute()
        )
        return {
            "status": "ok",
            "advisory_only": True,
            "auto_adopted": False,
            "suggestion": (updated.data or [suggestion])[0],
            "inventoryEntry": inv.data[0],
            "note": (
                "Accepted into organization_process_inventory as declared reference. "
                "Still advisory_only — not auto-governing agent operating model."
            ),
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

    async def calculate_process_health_score(
        self,
        org_id: str,
        process_name: str | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        runs = (
            client.table("workflow_runs")
            .select("id, status, workflow_name")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .limit(1000)
            .execute()
            .data
            or []
        )
        if process_name:
            runs = [r for r in runs if str(r.get("workflow_name") or "") == process_name]
        if len(runs) < MIN_RUNS:
            return {
                "status": "insufficient_data",
                "processName": process_name,
                "runCount": len(runs),
                "minRuns": MIN_RUNS,
                "scope_note": SCOPE_NOTE,
                "advisory_only": True,
            }
        completed = sum(1 for r in runs if str(r.get("status") or "") == "completed")
        failed = sum(1 for r in runs if str(r.get("status") or "") == "failed")
        health = completed / max(1, len(runs))
        penalty = failed / max(1, len(runs)) * 0.5
        score = round(max(0.0, min(1.0, health - penalty)), 4)
        return {
            "status": "ok",
            "processName": process_name,
            "healthScore": score,
            "runCount": len(runs),
            "completedCount": completed,
            "failedCount": failed,
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def calculate_workflow_efficiency_score(
        self,
        org_id: str,
        workflow_id: str,
    ) -> dict[str, Any]:
        client = self._client()
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        steps = (
            client.table("workflow_steps")
            .select("started_at, completed_at")
            .eq("org_id", org_id)
            .eq("workflow_id", workflow_id)
            .gte("created_at", since)
            .eq("status", "completed")
            .limit(2000)
            .execute()
            .data
            or []
        )
        durations: list[float] = []
        for row in steps:
            started = row.get("started_at")
            completed = row.get("completed_at")
            if not started or not completed:
                continue
            try:
                start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
                durations.append(max(0.0, (end_dt - start_dt).total_seconds() * 1000))
            except ValueError:
                continue
        if len(durations) < 3:
            return {
                "status": "insufficient_data",
                "workflowId": workflow_id,
                "sampleSize": len(durations),
                "scope_note": SCOPE_NOTE,
                "advisory_only": True,
            }
        actual_avg = mean(durations)
        theoretical_min = min(durations)
        efficiency = round(min(1.0, theoretical_min / actual_avg if actual_avg else 0.0), 4)
        return {
            "status": "ok",
            "workflowId": workflow_id,
            "efficiencyScore": efficiency,
            "avgDurationMs": round(actual_avg, 2),
            "theoreticalMinMs": round(theoretical_min, 2),
            "contributingFactors": [
                f"{len(durations)} completed steps sampled",
                "Efficiency = theoretical minimum / average cycle time",
            ],
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def calculate_department_efficiency_score(
        self,
        org_id: str,
        department: str,
    ) -> dict[str, Any]:
        client = self._client()
        inventory = (
            client.table("organization_process_inventory")
            .select("workflow_id, process_name")
            .eq("org_id", org_id)
            .eq("department", department)
            .execute()
            .data
            or []
        )
        scores: list[float] = []
        for row in inventory:
            wf_id = str(row.get("workflow_id") or "")
            if not wf_id:
                continue
            result = await self.calculate_workflow_efficiency_score(org_id, wf_id)
            if result.get("status") == "ok":
                scores.append(float(result.get("efficiencyScore") or 0))
        if not scores:
            return {
                "status": "insufficient_data",
                "department": department,
                "scope_note": SCOPE_NOTE,
                "advisory_only": True,
            }
        return {
            "status": "ok",
            "department": department,
            "efficiencyScore": round(mean(scores), 4),
            "workflowCount": len(scores),
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def estimate_business_impact(
        self,
        org_id: str,
        inefficiency: dict,
    ) -> dict[str, Any]:
        avg_ms = float(inefficiency.get("avgDurationMs") or 0)
        sample = int(inefficiency.get("sampleSize") or inefficiency.get("occurrences") or 0)
        hours = round((avg_ms * sample) / 3_600_000, 2) if avg_ms and sample else 0.0
        connectors = (
            self._client()
            .table("connectors")
            .select("type, status")
            .eq("org_id", org_id)
            .eq("status", "connected")
            .execute()
            .data
            or []
        )
        financial_types = {"stripe", "quickbooks", "xero", "netsuite", "finance"}
        has_financial = any(str(c.get("type") or "").lower() in financial_types for c in connectors)
        return {
            "hoursEstimate": hours,
            "costEstimate": None if not has_financial else "requires_financial_connector_mapping",
            "sampleSize": sample,
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def get_process_intelligence_summary(self, org_id: str) -> dict[str, Any]:
        health = await self.calculate_process_health_score(org_id)
        bottlenecks = await self.detect_process_bottlenecks(org_id)
        impacts = []
        for bottleneck in (bottlenecks.get("bottlenecks") or [])[:5]:
            impacts.append(await self.estimate_business_impact(org_id, bottleneck))
        departments = (
            self._client()
            .table("organization_process_inventory")
            .select("department")
            .eq("org_id", org_id)
            .execute()
            .data
            or []
        )
        dept_names = sorted({str(r.get("department") or "") for r in departments if r.get("department")})
        dept_scores = {}
        for dept in dept_names[:8]:
            dept_scores[dept] = await self.calculate_department_efficiency_score(org_id, dept)
        return {
            "processHealthScores": [health],
            "departmentEfficiencyScores": dept_scores,
            "topBottlenecks": bottlenecks.get("bottlenecks") or [],
            "businessImpactEstimates": impacts,
            "lastComputed": datetime.now(timezone.utc).isoformat(),
            "scope_note": SCOPE_NOTE,
            "advisory_only": True,
        }

    async def mine_connector_activity(
        self,
        org_id: str,
        connector: str,
        since_days: int = 30,
    ) -> list[dict]:
        client = self._client()
        connected = (
            client.table("connectors")
            .select("id, type, status")
            .eq("org_id", org_id)
            .eq("status", "connected")
            .execute()
            .data
            or []
        )
        if not any(str(c.get("type") or "").lower() == connector.lower() for c in connected):
            return []
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        rows = (
            client.table("mcp_tool_executions")
            .select("tool_name, status, duration_ms, created_at")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .ilike("tool_name", f"%{connector}%")
            .limit(500)
            .execute()
            .data
            or []
        )
        if not rows:
            return []
        total = len(rows)
        failures = sum(1 for r in rows if str(r.get("status") or "") in {"failed", "error"})
        failure_rate = failures / max(1, total)
        signals: list[dict] = []
        if failure_rate >= 0.2:
            signals.append(
                {
                    "signal": "high_failure_rate",
                    "connector": connector,
                    "failureRate": round(failure_rate, 4),
                    "sampleSize": total,
                    "advisory_only": True,
                }
            )
        slow = [float(r.get("duration_ms") or 0) for r in rows if r.get("duration_ms")]
        if slow and mean(slow) > 5000:
            signals.append(
                {
                    "signal": "timeout_cluster",
                    "connector": connector,
                    "avgDurationMs": round(mean(slow), 2),
                    "advisory_only": True,
                }
            )
        return signals

    async def check_process_conformance(
        self,
        org_id: str,
        *,
        since_days: int = 30,
    ) -> dict[str, Any]:
        """Compare observed workflow sequences against declared organization_process_inventory."""
        client = self._client()
        observed = await self.discover_workflow_patterns(org_id, since_days=since_days)
        declared = (
            client.table("organization_process_inventory")
            .select("process_name, workflow_id, declared_steps, department")
            .eq("org_id", org_id)
            .limit(100)
            .execute()
            .data
            or []
        )
        observed_patterns = {
            str(row.get("sequence") or ""): int(row.get("occurrences") or 0)
            for row in observed.get("patterns") or []
        }
        results: list[dict[str, Any]] = []
        for process in declared:
            steps = process.get("declared_steps") or []
            if isinstance(steps, list):
                declared_seq = " → ".join(str(step) for step in steps[:6])
            else:
                declared_seq = str(steps)
            if not declared_seq:
                continue
            best_match = max(
                (
                    (seq, count, self._sequence_alignment(declared_seq, seq))
                    for seq, count in observed_patterns.items()
                ),
                key=lambda item: item[2],
                default=(None, 0, 0.0),
            )
            seq, count, alignment = best_match
            results.append(
                {
                    "process_name": process.get("process_name"),
                    "workflow_id": process.get("workflow_id"),
                    "declared_sequence": declared_seq,
                    "best_observed_sequence": seq,
                    "observed_occurrences": count,
                    "alignment_score": round(alignment, 4),
                    "conformance_status": "aligned" if alignment >= 0.75 else "deviation",
                    "advisory_only": True,
                }
            )
        return {
            "status": "ok",
            "advisory_only": True,
            "sinceDays": since_days,
            "declared_process_count": len(declared),
            "conformance_results": results,
            "conformanceNote": CONFORMANCE_NOTE,
        }

    @staticmethod
    def _sequence_alignment(declared: str, observed: str) -> float:
        from difflib import SequenceMatcher

        if not declared or not observed:
            return 0.0
        return SequenceMatcher(None, declared.lower(), observed.lower()).ratio()


_process_mining_service: ProcessMiningService | None = None


def get_process_mining_service(settings: Settings | None = None) -> ProcessMiningService:
    global _process_mining_service
    if _process_mining_service is None or settings is not None:
        _process_mining_service = ProcessMiningService(settings)
    return _process_mining_service
