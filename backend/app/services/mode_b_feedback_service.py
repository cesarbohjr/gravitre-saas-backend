"""Mode B autonomous feedback infrastructure (STA-293): caps, rollback, post-hoc audit, toggle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.marketplace.pack_pricing import DEFAULT_FEEDBACK_MODE, MODE_B_GO_LIVE_REQUIRES_INFRASTRUCTURE
from app.services.feedback_mode_constants import (
    AUDIT_MODE_B_CAP_BLOCKED,
    AUDIT_MODE_B_DISABLED,
    AUDIT_MODE_B_ENABLED,
    AUDIT_MODE_B_MUTATION,
    AUDIT_MODE_B_ROLLBACK,
    CADENCE_OPTIONS,
    CONTENT_TYPE_OPTIONS,
    DEFAULT_MAX_SHIFT_PERCENT_PER_CYCLE,
    DEFAULT_PACK_SLUG,
    EVENT_CAP_BLOCKED,
    EVENT_MODE_DISABLED,
    EVENT_MODE_ENABLED,
    EVENT_MUTATION_APPLIED,
    EVENT_REPLAN_CYCLE,
    EVENT_ROLLBACK,
    FEEDBACK_MODE_A,
    FEEDBACK_MODE_B,
    MUTATION_DIMENSIONS,
    POOR_OUTCOME_WIN_RATE,
    TONE_OPTIONS,
)
from app.services.outcome_attribution_service import get_outcome_attribution_service
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

MutationDimension = Literal["tone", "cadence", "content_type"]


class ModeBFeedbackError(Exception):
    code = "MODE_B_FEEDBACK_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class ModeBCapExceededError(ModeBFeedbackError):
    code = "MODE_B_CAP_EXCEEDED"


class ModeBNotEnabledError(ModeBFeedbackError):
    code = "MODE_B_NOT_ENABLED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cycle_elapsed(cycle_started_at: str | None) -> bool:
    if not cycle_started_at:
        return True
    try:
        started = datetime.fromisoformat(str(cycle_started_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    return _now() - started >= timedelta(days=7)


def _next_option(current: str, options: tuple[str, ...]) -> str:
    if current not in options:
        return options[0]
    idx = options.index(current)
    return options[(idx + 1) % len(options)]


def _shift_percent_for_dimension(dimension: str) -> float:
    if dimension == "tone":
        return 10.0
    if dimension == "cadence":
        return 12.0
    return 8.0


def _read_feedback_profile(config: dict[str, Any]) -> dict[str, str]:
    profile = (config or {}).get("feedbackProfile") or {}
    if not isinstance(profile, dict):
        profile = {}
    return {
        "tone": str(profile.get("tone") or TONE_OPTIONS[0]),
        "cadence": str(profile.get("cadence") or CADENCE_OPTIONS[2]),
        "content_type": str(profile.get("contentType") or profile.get("content_type") or CONTENT_TYPE_OPTIONS[0]),
    }


def _write_feedback_profile(config: dict[str, Any], profile: dict[str, str]) -> dict[str, Any]:
    out = dict(config or {})
    out["feedbackProfile"] = {
        "tone": profile["tone"],
        "cadence": profile["cadence"],
        "contentType": profile["content_type"],
    }
    return out


class ModeBFeedbackService:
    """General-purpose Mode B guardrails + toggle primitive (marketing pack first consumer)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def get_feedback_settings(
        self,
        org_id: str,
        *,
        pack_slug: str = DEFAULT_PACK_SLUG,
    ) -> dict[str, Any]:
        client = self._client()
        row = self._fetch_settings_row(client, org_id, pack_slug)
        if not row:
            return self._default_settings(org_id, pack_slug)
        return self._serialize_settings(row)

    async def set_feedback_mode(
        self,
        org_id: str,
        *,
        feedback_mode: str,
        pack_slug: str = DEFAULT_PACK_SLUG,
        actor_id: str | None = None,
        risk_acknowledged: bool = False,
    ) -> dict[str, Any]:
        mode = str(feedback_mode or FEEDBACK_MODE_A).strip().lower()
        if mode not in {FEEDBACK_MODE_A, FEEDBACK_MODE_B}:
            raise ModeBFeedbackError(f"invalid feedback mode: {feedback_mode}")

        if mode == FEEDBACK_MODE_B:
            if MODE_B_GO_LIVE_REQUIRES_INFRASTRUCTURE and not risk_acknowledged:
                raise ModeBFeedbackError(
                    "Mode B requires explicit risk acknowledgment before enablement",
                    code="MODE_B_RISK_ACK_REQUIRED",
                )

        client = self._client()
        existing = self._fetch_settings_row(client, org_id, pack_slug)
        payload: dict[str, Any] = {
            "org_id": org_id,
            "pack_slug": pack_slug or DEFAULT_PACK_SLUG,
            "feedback_mode": mode,
            "updated_at": _now().isoformat(),
        }
        if mode == FEEDBACK_MODE_B:
            payload["mode_b_risk_acknowledged_at"] = _now().isoformat()
            if actor_id:
                payload["mode_b_risk_acknowledged_by"] = actor_id
        else:
            payload["mode_b_risk_acknowledged_at"] = None
            payload["mode_b_risk_acknowledged_by"] = None

        if existing:
            updated = (
                client.table("org_feedback_settings")
                .update(payload)
                .eq("org_id", org_id)
                .eq("pack_slug", pack_slug or DEFAULT_PACK_SLUG)
                .execute()
            )
            row = (updated.data or [existing])[0]
        else:
            payload.setdefault("max_shift_percent_per_cycle", DEFAULT_MAX_SHIFT_PERCENT_PER_CYCLE)
            payload.setdefault("cycle_shift_total", 0)
            payload.setdefault("cycle_started_at", _now().isoformat())
            inserted = client.table("org_feedback_settings").insert(payload).execute()
            row = (inserted.data or [payload])[0]

        audit_action = AUDIT_MODE_B_ENABLED if mode == FEEDBACK_MODE_B else AUDIT_MODE_B_DISABLED
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id or "",
            action=audit_action,
            resource_type="org_feedback_settings",
            resource_id=f"{org_id}:{pack_slug or DEFAULT_PACK_SLUG}",
            metadata={"feedbackMode": mode, "packSlug": pack_slug or DEFAULT_PACK_SLUG},
        )
        await self.record_autonomous_event(
            org_id,
            event_type=EVENT_MODE_ENABLED if mode == FEEDBACK_MODE_B else EVENT_MODE_DISABLED,
            details={"feedbackMode": mode, "packSlug": pack_slug or DEFAULT_PACK_SLUG},
        )
        return self._serialize_settings(row)

    def assert_cycle_cap_allows_shift(
        self,
        settings_row: dict[str, Any],
        proposed_shift_percent: float,
    ) -> None:
        max_shift = float(settings_row.get("max_shift_percent_per_cycle") or DEFAULT_MAX_SHIFT_PERCENT_PER_CYCLE)
        cycle_total = float(settings_row.get("cycle_shift_total") or 0)
        if _cycle_elapsed(settings_row.get("cycle_started_at")):
            cycle_total = 0.0
        if cycle_total + proposed_shift_percent > max_shift:
            raise ModeBCapExceededError(
                f"behavior shift cap exceeded: {cycle_total + proposed_shift_percent:.1f}% "
                f"> {max_shift:.1f}% per cycle"
            )

    async def apply_autonomous_mutation(
        self,
        org_id: str,
        agent_id: str,
        *,
        dimension: MutationDimension,
        pack_slug: str = DEFAULT_PACK_SLUG,
    ) -> dict[str, Any]:
        if dimension not in MUTATION_DIMENSIONS:
            raise ModeBFeedbackError(f"invalid mutation dimension: {dimension}")

        client = self._client()
        settings_row = self._require_mode_b(client, org_id, pack_slug)
        agent = self._fetch_agent(client, org_id, agent_id)
        profile = _read_feedback_profile(agent.get("config") or {})
        before_value = profile[dimension if dimension != "content_type" else "content_type"]

        options = {
            "tone": TONE_OPTIONS,
            "cadence": CADENCE_OPTIONS,
            "content_type": CONTENT_TYPE_OPTIONS,
        }[dimension]
        after_value = _next_option(before_value, options)
        shift_percent = _shift_percent_for_dimension(dimension)

        try:
            self.assert_cycle_cap_allows_shift(settings_row, shift_percent)
        except ModeBCapExceededError as exc:
            await self.record_autonomous_event(
                org_id,
                event_type=EVENT_CAP_BLOCKED,
                details={"agentId": agent_id, "dimension": dimension, "reason": str(exc)},
            )
            write_audit_event(
                client,
                org_id=org_id,
                actor_id="",
                action=AUDIT_MODE_B_CAP_BLOCKED,
                resource_type="agent",
                resource_id=agent_id,
                metadata={"dimension": dimension, "reason": str(exc)},
            )
            raise

        outcome_service = get_outcome_attribution_service(self.settings)
        outcome_before = await outcome_service.get_agent_outcome_summary(org_id, agent_id)
        win_rate_before = outcome_before.get("winRate")

        config_before = dict(agent.get("config") or {})
        profile[dimension if dimension != "content_type" else "content_type"] = after_value
        config_after = _write_feedback_profile(config_before, profile)

        client.table("agents").update({"config": config_after}).eq("id", agent_id).eq("org_id", org_id).execute()

        cycle_total = float(settings_row.get("cycle_shift_total") or 0)
        if _cycle_elapsed(settings_row.get("cycle_started_at")):
            cycle_total = 0.0
            client.table("org_feedback_settings").update(
                {"cycle_shift_total": 0, "cycle_started_at": _now().isoformat()}
            ).eq("org_id", org_id).eq("pack_slug", pack_slug or DEFAULT_PACK_SLUG).execute()

        client.table("org_feedback_settings").update(
            {"cycle_shift_total": cycle_total + shift_percent}
        ).eq("org_id", org_id).eq("pack_slug", pack_slug or DEFAULT_PACK_SLUG).execute()

        mutation_payload = {
            "dimension": dimension,
            "beforeValue": before_value,
            "afterValue": after_value,
            "shiftPercent": shift_percent,
        }
        inserted = (
            client.table("mode_b_autonomous_mutations")
            .insert(
                {
                    "org_id": org_id,
                    "agent_id": agent_id,
                    "pack_slug": pack_slug or DEFAULT_PACK_SLUG,
                    "dimension": dimension,
                    "before_value": before_value,
                    "after_value": after_value,
                    "shift_percent": shift_percent,
                    "mutation_payload": mutation_payload,
                    "agent_config_before": config_before,
                    "agent_config_after": config_after,
                    "outcome_win_rate_before": win_rate_before,
                    "status": "active",
                }
            )
            .execute()
        )
        mutation = (inserted.data or [{}])[0]
        mutation_id = str(mutation.get("id") or "")

        write_audit_event(
            client,
            org_id=org_id,
            actor_id="",
            action=AUDIT_MODE_B_MUTATION,
            resource_type="agent",
            resource_id=agent_id,
            metadata={"mutationId": mutation_id, **mutation_payload, "autonomous": True},
        )
        await self.record_autonomous_event(
            org_id,
            event_type=EVENT_MUTATION_APPLIED,
            mutation_id=mutation_id or None,
            details={"agentId": agent_id, **mutation_payload},
        )
        return {"mutation": mutation, "agentId": agent_id}

    async def rollback_mutation(
        self,
        org_id: str,
        mutation_id: str,
        *,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        row = (
            client.table("mode_b_autonomous_mutations")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", mutation_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not row:
            raise ModeBFeedbackError("mutation not found", code="MUTATION_NOT_FOUND")
        mutation = row[0]
        if str(mutation.get("status") or "") == "rolled_back":
            raise ModeBFeedbackError("mutation already rolled back", code="ALREADY_ROLLED_BACK")

        agent_id = str(mutation.get("agent_id") or "")
        config_before = mutation.get("agent_config_before") or {}
        client.table("agents").update({"config": config_before}).eq("id", agent_id).eq("org_id", org_id).execute()

        client.table("mode_b_autonomous_mutations").update(
            {"status": "rolled_back", "rolled_back_at": _now().isoformat()}
        ).eq("id", mutation_id).eq("org_id", org_id).execute()

        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id or "",
            action=AUDIT_MODE_B_ROLLBACK,
            resource_type="mode_b_autonomous_mutation",
            resource_id=mutation_id,
            metadata={"agentId": agent_id, "autonomous": actor_id is None},
        )
        await self.record_autonomous_event(
            org_id,
            event_type=EVENT_ROLLBACK,
            mutation_id=mutation_id,
            details={"agentId": agent_id},
        )
        return {"mutationId": mutation_id, "agentId": agent_id, "status": "rolled_back"}

    async def evaluate_and_rollback_underperforming(
        self,
        org_id: str,
        agent_id: str,
        *,
        pack_slug: str = DEFAULT_PACK_SLUG,
    ) -> dict[str, Any]:
        client = self._client()
        self._require_mode_b(client, org_id, pack_slug)
        outcome_service = get_outcome_attribution_service(self.settings)
        summary = await outcome_service.get_agent_outcome_summary(org_id, agent_id)
        if not summary.get("sufficientData"):
            return {"rolledBack": False, "reason": "insufficient_outcome_data"}
        win_rate = float(summary.get("winRate") or 0.0)
        if win_rate >= POOR_OUTCOME_WIN_RATE:
            return {"rolledBack": False, "winRate": win_rate}

        active = (
            client.table("mode_b_autonomous_mutations")
            .select("id")
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not active:
            return {"rolledBack": False, "reason": "no_active_mutation", "winRate": win_rate}

        mutation_id = str(active[0]["id"])
        result = await self.rollback_mutation(org_id, mutation_id)
        client.table("mode_b_autonomous_mutations").update(
            {"outcome_win_rate_after": win_rate}
        ).eq("id", mutation_id).execute()
        return {"rolledBack": True, "winRate": win_rate, **result}

    async def run_replanning_cycle(
        self,
        org_id: str,
        *,
        pack_slug: str = DEFAULT_PACK_SLUG,
    ) -> dict[str, Any]:
        client = self._client()
        self._require_mode_b(client, org_id, pack_slug)
        agents = (
            client.table("agents")
            .select("id, name")
            .eq("org_id", org_id)
            .eq("status", "active")
            .limit(100)
            .execute()
            .data
            or []
        )
        outcome_service = get_outcome_attribution_service(self.settings)
        mutations: list[dict[str, Any]] = []
        rollbacks: list[dict[str, Any]] = []

        for agent in agents:
            agent_id = str(agent.get("id") or "")
            if not agent_id:
                continue
            summary = await outcome_service.get_agent_outcome_summary(org_id, agent_id)
            if not summary.get("sufficientData"):
                continue
            win_rate = float(summary.get("winRate") or 0.0)
            if win_rate < POOR_OUTCOME_WIN_RATE:
                rollback = await self.evaluate_and_rollback_underperforming(
                    org_id, agent_id, pack_slug=pack_slug
                )
                if rollback.get("rolledBack"):
                    rollbacks.append(rollback)
                else:
                    try:
                        mutation = await self.apply_autonomous_mutation(
                            org_id,
                            agent_id,
                            dimension="tone",
                            pack_slug=pack_slug,
                        )
                        mutations.append(mutation)
                    except ModeBCapExceededError:
                        break
                    except ModeBFeedbackError:
                        continue

        await self.record_autonomous_event(
            org_id,
            event_type=EVENT_REPLAN_CYCLE,
            details={
                "packSlug": pack_slug or DEFAULT_PACK_SLUG,
                "mutations": len(mutations),
                "rollbacks": len(rollbacks),
            },
        )
        return {
            "orgId": org_id,
            "packSlug": pack_slug or DEFAULT_PACK_SLUG,
            "mutationsApplied": len(mutations),
            "rollbacks": len(rollbacks),
            "mutationDetails": mutations,
            "rollbackDetails": rollbacks,
        }

    async def record_autonomous_event(
        self,
        org_id: str,
        *,
        event_type: str,
        mutation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        payload = {
            "org_id": org_id,
            "mutation_id": mutation_id,
            "event_type": event_type,
            "details": details or {},
        }
        inserted = client.table("mode_b_autonomous_events").insert(payload).execute()
        return (inserted.data or [payload])[0]

    async def list_autonomous_events(
        self,
        org_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        client = self._client()
        rows = (
            client.table("mode_b_autonomous_events")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )
        return rows

    def _fetch_settings_row(self, client: Any, org_id: str, pack_slug: str) -> dict[str, Any] | None:
        result = (
            client.table("org_feedback_settings")
            .select("*")
            .eq("org_id", org_id)
            .eq("pack_slug", pack_slug or DEFAULT_PACK_SLUG)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return result.data[0]

    def _default_settings(self, org_id: str, pack_slug: str) -> dict[str, Any]:
        return {
            "orgId": org_id,
            "packSlug": pack_slug or DEFAULT_PACK_SLUG,
            "feedbackMode": DEFAULT_FEEDBACK_MODE,
            "maxShiftPercentPerCycle": DEFAULT_MAX_SHIFT_PERCENT_PER_CYCLE,
            "cycleShiftTotal": 0.0,
            "modeBRiskAcknowledgedAt": None,
            "modeBRiskAcknowledgedBy": None,
        }

    def _serialize_settings(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "orgId": row.get("org_id"),
            "packSlug": row.get("pack_slug") or DEFAULT_PACK_SLUG,
            "feedbackMode": row.get("feedback_mode") or FEEDBACK_MODE_A,
            "maxShiftPercentPerCycle": float(row.get("max_shift_percent_per_cycle") or DEFAULT_MAX_SHIFT_PERCENT_PER_CYCLE),
            "cycleShiftTotal": float(row.get("cycle_shift_total") or 0),
            "cycleStartedAt": row.get("cycle_started_at"),
            "modeBRiskAcknowledgedAt": row.get("mode_b_risk_acknowledged_at"),
            "modeBRiskAcknowledgedBy": row.get("mode_b_risk_acknowledged_by"),
        }

    def _require_mode_b(self, client: Any, org_id: str, pack_slug: str) -> dict[str, Any]:
        row = self._fetch_settings_row(client, org_id, pack_slug)
        if not row or str(row.get("feedback_mode") or "") != FEEDBACK_MODE_B:
            raise ModeBNotEnabledError("Mode B is not enabled for this org/pack")
        return row

    def _fetch_agent(self, client: Any, org_id: str, agent_id: str) -> dict[str, Any]:
        result = (
            client.table("agents")
            .select("id, org_id, config")
            .eq("org_id", org_id)
            .eq("id", agent_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise ModeBFeedbackError("agent not found", code="AGENT_NOT_FOUND")
        return result.data[0]


_mode_b_feedback_service: ModeBFeedbackService | None = None


def get_mode_b_feedback_service(settings: Settings | None = None) -> ModeBFeedbackService:
    global _mode_b_feedback_service
    if settings is not None:
        return ModeBFeedbackService(settings=settings)
    if _mode_b_feedback_service is None:
        _mode_b_feedback_service = ModeBFeedbackService()
    return _mode_b_feedback_service
