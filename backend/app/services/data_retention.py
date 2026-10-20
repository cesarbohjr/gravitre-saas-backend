"""Audit-log and telemetry retention: bounded, oldest-first deletes with a receipt.

Off unless AUDIT_RETENTION_DAYS or TELEMETRY_RETENTION_DAYS is above 0 (0 keeps rows
forever). AUDIT_RETENTION_DRY_RUN (default true) only counts what would go and writes
the receipt. Needs migration 20261020081535_storage_retention_metering.sql (and its parts).

Compliance rules, enforced here and again in the SQL functions:

* Floors: audit_logs / audit_events are kept at least 365 days (a year of audit
  evidence for SOC2 exports, ``compliance_service.build_soc2_evidence_bundle``);
  model_calls 400 days (agent ROI reports read up to 366 days); ai_pipeline_latency
  and cognitive_turn_traces 30 days. A configured value below the floor is raised to
  it and the receipt says so.
* Legal hold: an org with an unreleased ``org_legal_holds`` row is skipped entirely.
  If the holds cannot be read, nothing is deleted (fail closed).
* Approval trail: audit rows whose action mentions an approval or a rejection are
  never deleted.
* guardrail_events is not pruned (security evidence).

Archive (AUDIT_RETENTION_ARCHIVE_ENABLED, audit tables only): each batch is read,
written as gzipped JSONL to the private bucket AUDIT_RETENTION_ARCHIVE_BUCKET under
``<org_id>/<table>/<cutoff date>/<run id>-<n>.jsonl.gz``, and only after the upload
succeeds are exactly those rows deleted. A failed upload stops that org and table.

One run at a time: the receipt row is the lease (a partial unique index allows a
single ``running`` receipt); runs left ``running`` for 6 hours are marked abandoned.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

AUDIT_TABLES: tuple[str, ...] = ("audit_logs", "audit_events")
AUDIT_MIN_DAYS = 365
# table -> minimum days kept. guardrail_events is deliberately absent.
TELEMETRY_FLOORS: dict[str, int] = {
    "model_calls": 400,
    "ai_pipeline_latency": 30,
    "cognitive_turn_traces": 30,
}
MAX_BATCH = 10000
STALE_RUN_HOURS = 6


@dataclass(frozen=True)
class RetentionTarget:
    table: str
    days: int
    configured_days: int
    archive: bool


def retention_plan(settings: Any) -> list[RetentionTarget]:
    """Tables to prune with their effective age; [] when retention is off."""
    plan: list[RetentionTarget] = []
    audit_days = int(getattr(settings, "audit_retention_days", 0) or 0)
    telemetry_days = int(getattr(settings, "telemetry_retention_days", 0) or 0)
    archive = getattr(settings, "audit_retention_archive_enabled", False) is True
    if audit_days > 0:
        for table in AUDIT_TABLES:
            plan.append(RetentionTarget(table, max(audit_days, AUDIT_MIN_DAYS), audit_days, archive))
    if telemetry_days > 0:
        for table, floor in TELEMETRY_FLOORS.items():
            plan.append(RetentionTarget(table, max(telemetry_days, floor), telemetry_days, False))
    return plan


def _active_legal_holds(client: Any) -> set[str]:
    res = client.table("org_legal_holds").select("org_id").is_("released_at", "null").execute()
    return {str(r["org_id"]) for r in (res.data or []) if r.get("org_id")}


def _start_receipt(client: Any, *, dry_run: bool, settings_doc: dict[str, Any], now: datetime) -> str | None:
    stale = (now - timedelta(hours=STALE_RUN_HOURS)).isoformat()
    client.table("data_retention_runs").update(
        {"status": "abandoned", "finished_at": now.isoformat(), "error": "lease expired"}
    ).eq("status", "running").lt("started_at", stale).execute()
    try:
        res = (
            client.table("data_retention_runs")
            .insert({"dry_run": dry_run, "status": "running", "settings": settings_doc})
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 - unique index: another run holds the lease
        logger.info("data_retention_skipped reason=run_in_progress error=%s", type(exc).__name__)
        return None
    rows = res.data or []
    return str(rows[0]["id"]) if rows else None


def _finish_receipt(client: Any, run_id: str, **fields: Any) -> None:
    fields["finished_at"] = datetime.now(UTC).isoformat()
    try:
        client.table("data_retention_runs").update(fields).eq("id", run_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("data_retention_receipt_update_failed run_id=%s error=%s", run_id, type(exc).__name__)


def _archive_rows(
    client: Any, bucket: str, *, org_id: str, table: str, cutoff: datetime, run_id: str, seq: int,
    rows: list[dict[str, Any]],
) -> str:
    body = "".join(json.dumps(r, default=str, sort_keys=True) + "\n" for r in rows).encode("utf-8")
    path = f"{org_id}/{table}/{cutoff.date().isoformat()}/{run_id}-{seq:05d}.jsonl.gz"
    client.storage.from_(bucket).upload(
        path,
        gzip.compress(body),
        file_options={"content-type": "application/gzip", "upsert": "false"},
    )
    return path


def run_data_retention(client: Any, settings: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """One retention pass. Returns the receipt document (also stored in data_retention_runs)."""
    plan = retention_plan(settings)
    if not plan:
        return {"status": "off"}
    now = now or datetime.now(UTC)
    dry_run = getattr(settings, "audit_retention_dry_run", True) is not False
    batch = max(1, min(int(getattr(settings, "audit_retention_batch_size", 2000) or 2000), MAX_BATCH))
    budget = max(1, int(getattr(settings, "audit_retention_max_batches_per_run", 500) or 500))
    bucket = (getattr(settings, "audit_retention_archive_bucket", "") or "audit-archive").strip()

    try:
        held = _active_legal_holds(client)
    except Exception as exc:  # noqa: BLE001 - fail closed: no hold list, no deletes
        logger.warning("data_retention_aborted reason=legal_holds_unreadable error=%s", type(exc).__name__)
        return {"status": "failed", "error": "legal_holds_unreadable"}

    settings_doc = {
        "dryRun": dry_run,
        "batchSize": batch,
        "maxBatches": budget,
        "archive": any(t.archive for t in plan),
        "tables": {
            t.table: {"days": t.days, "configuredDays": t.configured_days, "raisedToFloor": t.days > t.configured_days}
            for t in plan
        },
        "legalHoldOrgs": len(held),
    }
    run_id = _start_receipt(client, dry_run=dry_run, settings_doc=settings_doc, now=now)
    if run_id is None:
        return {"status": "skipped", "reason": "run_in_progress"}

    details: dict[str, dict[str, Any]] = {}
    totals: dict[str, int] = {"matched": 0, "deleted": 0, "archivedObjects": 0}
    batches_used = 0
    status = "completed"
    error: str | None = None
    try:
        for target in plan:
            cutoff = now - timedelta(days=target.days)
            res = client.rpc(
                "data_retention_candidates", {"p_table": target.table, "p_cutoff": cutoff.isoformat()}
            ).execute()
            candidates = [
                (str(r["org_id"]), int(r.get("row_count") or 0))
                for r in (res.data or [])
                if r.get("org_id") and str(r["org_id"]) not in held
            ]
            table_doc: dict[str, Any] = {"cutoff": cutoff.isoformat(), "orgs": {}}
            details[target.table] = table_doc
            for org_id, matched in candidates:
                totals["matched"] += matched
                org_doc: dict[str, Any] = {"matched": matched}
                table_doc["orgs"][org_id] = org_doc
                if dry_run:
                    continue
                deleted = 0
                archived: list[str] = []
                while batches_used < budget:
                    batches_used += 1
                    if target.archive:
                        rows_res = client.rpc(
                            "data_retention_fetch_batch",
                            {"p_table": target.table, "p_org_id": org_id, "p_cutoff": cutoff.isoformat(),
                             "p_batch": batch},
                        ).execute()
                        rows = [r for r in (rows_res.data or []) if isinstance(r, dict)]
                        if not rows:
                            break
                        try:
                            archived.append(
                                _archive_rows(client, bucket, org_id=org_id, table=target.table, cutoff=cutoff,
                                              run_id=run_id, seq=len(archived) + 1, rows=rows)
                            )
                        except Exception as exc:  # noqa: BLE001 - never delete what was not archived
                            org_doc["archiveError"] = type(exc).__name__
                            status = "partial"
                            logger.warning(
                                "data_retention_archive_failed table=%s org_id=%s error=%s",
                                target.table, org_id, type(exc).__name__,
                            )
                            break
                        n = int(
                            client.rpc(
                                "data_retention_delete_batch",
                                {"p_table": target.table, "p_org_id": org_id, "p_cutoff": cutoff.isoformat(),
                                 "p_batch": len(rows), "p_ids": [str(r["id"]) for r in rows]},
                            ).execute().data
                            or 0
                        )
                        deleted += n
                        if len(rows) < batch:
                            break
                    else:
                        n = int(
                            client.rpc(
                                "data_retention_delete_batch",
                                {"p_table": target.table, "p_org_id": org_id, "p_cutoff": cutoff.isoformat(),
                                 "p_batch": batch},
                            ).execute().data
                            or 0
                        )
                        deleted += n
                        if n < batch:
                            break
                else:
                    status = "partial"  # budget used up; the next run continues oldest first
                org_doc["deleted"] = deleted
                if archived:
                    org_doc["archived"] = archived
                totals["deleted"] += deleted
                totals["archivedObjects"] += len(archived)
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = f"{type(exc).__name__}: {str(exc)[:200]}"
        logger.warning("data_retention_failed run_id=%s error=%s", run_id, error)

    totals["batches"] = batches_used
    _finish_receipt(client, run_id, status=status, totals=totals, details=details, error=error)
    logger.info(
        "data_retention_run run_id=%s dry_run=%s status=%s matched=%s deleted=%s archived=%s",
        run_id, dry_run, status, totals["matched"], totals["deleted"], totals["archivedObjects"],
    )
    return {"runId": run_id, "dryRun": dry_run, "status": status, "totals": totals, "details": details,
            "settings": settings_doc, "error": error}
