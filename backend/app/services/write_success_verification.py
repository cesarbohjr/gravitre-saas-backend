"""Phase 3 — catalog-wide declared write success verification (F6 generalized).

Every mutating ActionSpec must declare how success is independently confirmed.
Follow-up reads reuse F6 settle/retry. Chat path schedules verification AFTER
the user-visible response is produced so TTFT is not blocked.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.services.catalog_write_authority import catalog_action_requires_write_approval
from app.services.collection_population_verify import (
    POPULATION_ACTIONS,
    apply_population_verify_to_status,
    is_population_write_action,
)

logger = logging.getLogger(__name__)

VerificationMode = Literal[
    "follow_up_membership",
    "follow_up_entity_get",
    "accepted_async",
]

_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "connectors"
    / "action_catalog"
    / "data"
    / "success_verification_catalog.json"
)

# Known membership write → follow-up read (F6 class).
_MEMBERSHIP_FOLLOW_UPS: dict[str, str] = {
    "apollo.lists.add": "apollo.lists.list",
    "hubspot.lists.add_contact": "hubspot.lists.get",
    "marketo.lists.add_to_static_list": "marketo.lists.get_leads",
}


@dataclass(frozen=True)
class SuccessVerification:
    action: str
    mode: VerificationMode
    read_action: str | None = None
    assert_field: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"action": self.action, "mode": self.mode}
        if self.read_action:
            out["read_action"] = self.read_action
        if self.assert_field:
            out["assert_field"] = self.assert_field
        if self.reason:
            out["reason"] = self.reason
        return out


def _mutating_specs() -> list[Any]:
    return [
        s
        for s in all_catalog_action_specs()
        if catalog_action_requires_write_approval(
            kind=s.kind,
            destructive=bool(s.destructive),
            requires_approval=bool(s.requires_approval),
            scopes=s.scopes,
        )
    ]


def _infer_entity_get(action: str, all_ids: set[str]) -> str | None:
    """Best-effort sibling GET for create/update writes (vendor.resource.get)."""
    parts = action.split(".")
    if len(parts) < 3:
        return None
    vendor, resource, verb = parts[0], parts[1], parts[-1]
    if verb not in {
        "create",
        "update",
        "upsert",
        "patch",
        "add",
        "add_contact",
        "add_member",
        "add_contacts",
        "send",
        "post",
        "post_message",
    }:
        return None
    candidates = [
        f"{vendor}.{resource}.get",
        f"{vendor}.{resource}.retrieve",
        f"{vendor}.{resource}.read",
    ]
    for cand in candidates:
        if cand in all_ids:
            return cand
    return None


def build_default_verification(action: str, *, all_ids: set[str] | None = None) -> SuccessVerification:
    key = str(action or "").strip().lower()
    ids = all_ids if all_ids is not None else {s.id.lower() for s in all_catalog_action_specs()}
    if key in POPULATION_ACTIONS or key in _MEMBERSHIP_FOLLOW_UPS:
        return SuccessVerification(
            action=key,
            mode="follow_up_membership",
            read_action=_MEMBERSHIP_FOLLOW_UPS.get(key),
            assert_field="membership_count",
            reason="F6 collection population membership proof",
        )
    sibling = _infer_entity_get(key, ids)
    if sibling:
        return SuccessVerification(
            action=key,
            mode="follow_up_entity_get",
            read_action=sibling,
            assert_field="id",
            reason="Sibling GET must return the written entity id/field",
        )
    return SuccessVerification(
        action=key,
        mode="accepted_async",
        reason=(
            "No catalog sibling GET declared for independent confirmation; "
            "outcome stays accepted_async until a follow-up read is wired"
        ),
    )


@lru_cache(maxsize=1)
def success_verification_catalog() -> dict[str, dict[str, Any]]:
    if not _DATA_PATH.is_file():
        return {}
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    actions = raw.get("actions") if isinstance(raw.get("actions"), dict) else raw
    return {str(k).lower(): v for k, v in (actions or {}).items() if isinstance(v, dict)}


def resolve_success_verification(action: str) -> SuccessVerification:
    key = str(action or "").strip().lower()
    row = success_verification_catalog().get(key)
    if row:
        mode = str(row.get("mode") or "accepted_async")
        if mode not in {"follow_up_membership", "follow_up_entity_get", "accepted_async"}:
            mode = "accepted_async"
        return SuccessVerification(
            action=key,
            mode=mode,  # type: ignore[arg-type]
            read_action=(str(row["read_action"]) if row.get("read_action") else None),
            assert_field=(str(row["assert_field"]) if row.get("assert_field") else None),
            reason=(str(row["reason"]) if row.get("reason") else None),
        )
    return build_default_verification(key)


def coverage_report() -> dict[str, Any]:
    specs = _mutating_specs()
    cat = success_verification_catalog()
    by_mode: dict[str, int] = {}
    missing: list[str] = []
    examples: dict[str, list[dict[str, Any]]] = {
        "follow_up_membership": [],
        "follow_up_entity_get": [],
        "accepted_async": [],
    }
    for spec in specs:
        key = spec.id.lower()
        if key not in cat:
            missing.append(key)
            ver = build_default_verification(key)
        else:
            ver = resolve_success_verification(key)
        by_mode[ver.mode] = by_mode.get(ver.mode, 0) + 1
        bucket = examples.get(ver.mode)
        if bucket is not None and len(bucket) < 8:
            bucket.append(ver.as_dict())
    total = len(specs)
    declared = total - len(missing)
    return {
        "mutating_action_count": total,
        "declared_count": declared if cat else 0,
        "catalog_path_exists": _DATA_PATH.is_file(),
        "coverage_pct": round(100.0 * (declared / total), 2) if total and cat else 0.0,
        "full_coverage": bool(cat) and not missing,
        "missing_count": len(missing),
        "missing_sample": missing[:20],
        "by_mode": by_mode,
        "examples": examples,
        "population_actions": sorted(POPULATION_ACTIONS),
    }


def generate_success_verification_catalog() -> dict[str, Any]:
    """Build complete catalog for all mutating actions (generator / CI seed)."""
    all_ids = {s.id.lower() for s in all_catalog_action_specs()}
    actions: dict[str, dict[str, Any]] = {}
    for spec in _mutating_specs():
        ver = build_default_verification(spec.id, all_ids=all_ids)
        actions[ver.action] = {
            k: v for k, v in ver.as_dict().items() if k != "action"
        }
    payload = {
        "version": 1,
        "generated_by": "write_success_verification.generate_success_verification_catalog",
        "mutating_action_count": len(actions),
        "actions": actions,
    }
    _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DATA_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    success_verification_catalog.cache_clear()
    return payload


def schedule_write_success_verification(
    *,
    client: Any,
    org_id: str,
    run_id: str | None,
    invoke_action: str,
    result_data: dict[str, Any] | None,
    settings: Any,
    ctx: Any = None,
    environment_name: str = "production",
) -> None:
    """Fire-and-forget post-stream verification (must not block TTFT)."""
    if not run_id or not is_population_write_action(invoke_action):
        # Phase 3: membership class runs async settle; entity_get reserved for later adapters.
        return
    if ctx is None:
        return

    def _work() -> None:
        try:
            status, effect, verify = apply_population_verify_to_status(
                status="completed",
                invoke_action=invoke_action,
                result_data=result_data,
                client=client,
                org_id=org_id,
                settings=settings,
                environment_name=environment_name,
                ctx=ctx,
            )
            if verify is None:
                return
            from app.workflows.repository import merge_run_parameters, update_run

            # Stamp verify evidence always. Never terminalize an in-flight multi-step
            # execute — mid-step writes (e.g. apollo.lists.add) used to mark the whole
            # run ``completed`` while later agent/Clay/HubSpot steps were still pending.
            current_status = ""
            try:
                row = (
                    client.table("workflow_runs")
                    .select("status")
                    .eq("id", run_id)
                    .limit(1)
                    .execute()
                )
                current_status = str(((row.data or [{}])[0] or {}).get("status") or "")
            except Exception:  # noqa: BLE001
                current_status = ""

            merge_run_parameters(
                client,
                run_id,
                {
                    "outcome_effect": effect or ("created" if verify.verified else verify.effect),
                    "population_verify": {
                        "verified": verify.verified,
                        "effect": verify.effect,
                        "membership_count": verify.membership_count,
                        "detail": verify.detail,
                        "async": True,
                    },
                },
            )
            if current_status in {"running", "pending_approval", "queued", "paused", "approved"}:
                logger.info(
                    "async_write_success_verify_params_only run_id=%s action=%s "
                    "current_status=%s verified=%s detail=%s",
                    run_id,
                    invoke_action,
                    current_status,
                    verify.verified,
                    verify.detail,
                )
                return

            update_run(client, run_id, status)
            logger.info(
                "async_write_success_verify run_id=%s action=%s verified=%s detail=%s",
                run_id,
                invoke_action,
                verify.verified,
                verify.detail,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "async_write_success_verify_failed run_id=%s action=%s err=%s",
                run_id,
                invoke_action,
                exc,
            )

    try:
        loop = asyncio.get_running_loop()

        async def _ago() -> None:
            await asyncio.to_thread(_work)

        loop.create_task(_ago())
    except RuntimeError:
        threading.Thread(target=_work, name="write-success-verify", daemon=True).start()
