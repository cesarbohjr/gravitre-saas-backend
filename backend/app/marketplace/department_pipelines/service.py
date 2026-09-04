"""Resolve department pipeline definitions + live stage status for an org."""
from __future__ import annotations

from typing import Any, Literal

from app.marketplace.department_pipelines.catalog import (
    DepartmentPipelineSpec,
    StageStatus,
    get_department_pipeline,
    list_department_pipelines,
    serialize_pipeline,
)
from app.services.department_signal_scoring_service import (
    get_department_signal_scoring_service,
)
from app.services.sync_back_policy_service import get_sync_back_policy

StageStatusLiteral = Literal["not_started", "in_progress", "completed", "blocked", "skipped"]


class DepartmentPipelineService:
    def list_catalog(self) -> list[dict[str, Any]]:
        return [serialize_pipeline(p) for p in list_department_pipelines()]

    def get_pipeline_view(
        self,
        client: Any,
        *,
        org_id: str,
        pipeline_id: str | None = None,
        department: str | None = None,
        org_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        spec = get_department_pipeline(pipeline_id, department=department)
        if spec is None:
            return None
        sync_policy = get_sync_back_policy(org_settings, department=spec.department)
        stages = self._resolve_stage_statuses(client, org_id=org_id, spec=spec)
        installed_packs = self._installed_pack_ids(client, org_id=org_id)
        pack_ready = bool(
            spec.default_intelligence_pack_id and spec.default_intelligence_pack_id in installed_packs
        ) or bool(
            spec.default_department_pack_slug
            and any(spec.default_department_pack_slug in str(x) for x in installed_packs)
        )
        signal_scoring = get_department_signal_scoring_service().score_department(
            org_id,
            client=client,
            department=spec.department,
            limit=3,
        )
        source_audit = get_department_signal_scoring_service().audit_sources(
            org_id,
            client=client,
            department=spec.department,
        )
        return {
            **serialize_pipeline(spec),
            "syncBackPolicy": sync_policy,
            "connectAndGoReady": pack_ready,
            "installedPackHints": sorted(installed_packs)[:12],
            "stageStatuses": stages,
            "signalScoring": signal_scoring,
            "signalSourceAudit": source_audit,
        }

    def _installed_pack_ids(self, client: Any, *, org_id: str) -> set[str]:
        out: set[str] = set()
        try:
            rows = (
                client.table("marketplace_installs")
                .select("asset_slug, metadata")
                .eq("org_id", org_id)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            return out
        for row in rows:
            slug = str(row.get("asset_slug") or "").strip()
            if slug:
                out.add(slug)
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            for key in ("packId", "pack_id", "intelligencePackId"):
                val = str(meta.get(key) or "").strip()
                if val:
                    out.add(val)
        return out

    def _resolve_stage_statuses(
        self,
        client: Any,
        *,
        org_id: str,
        spec: DepartmentPipelineSpec,
    ) -> list[dict[str, Any]]:
        wo_counts = self._work_object_counts(client, org_id=org_id, work_object_type=spec.work_object_type)
        run_counts = self._recent_run_counts(client, org_id=org_id, department=spec.department)
        statuses: list[dict[str, Any]] = []
        any_activity = wo_counts.get("total", 0) > 0 or run_counts > 0
        for idx, stage in enumerate(spec.stages):
            status: StageStatusLiteral = "not_started"
            detail = ""
            if stage.requires_new_capability:
                status = "blocked" if stage.capability_kind == "gap" else "skipped"
                detail = stage.gap_note or "Requires capability not yet built."
            elif wo_counts.get("completed", 0) > 0 and stage.stage_id == spec.sync_milestone_stage_id:
                status = "completed"
                detail = f"{wo_counts.get('completed', 0)} WorkObject(s) completed."
            elif wo_counts.get("in_progress", 0) > 0 and idx <= 2:
                status = "in_progress"
                detail = f"{wo_counts.get('in_progress', 0)} active WorkObject(s)."
            elif any_activity and idx == 0:
                status = "in_progress"
                detail = "Org activity detected for this department."
            statuses.append(
                {
                    "stageId": stage.stage_id,
                    "label": stage.label,
                    "status": status,
                    "detail": detail,
                    "requiresNewCapability": stage.requires_new_capability,
                }
            )
        return statuses

    def _work_object_counts(
        self,
        client: Any,
        *,
        org_id: str,
        work_object_type: str,
    ) -> dict[str, int]:
        out = {"total": 0, "in_progress": 0, "completed": 0}
        try:
            rows = (
                client.table("work_objects")
                .select("status")
                .eq("org_id", org_id)
                .eq("object_type", work_object_type)
                .limit(500)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            return out
        out["total"] = len(rows)
        for row in rows:
            st = str(row.get("status") or "").lower()
            if st == "completed":
                out["completed"] += 1
            elif st in {"in_progress", "planned", "awaiting_approval", "identified"}:
                out["in_progress"] += 1
        return out

    def _recent_run_counts(self, client: Any, *, org_id: str, department: str) -> int:
        try:
            resp = (
                client.table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0
