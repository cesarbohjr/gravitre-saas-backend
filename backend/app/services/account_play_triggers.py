"""Phase 8: account evidence proposes a Play; a person decides.

When an account's health (Phase 7) shows a stated at-risk pattern, this files a
*proposal* (Phase 5 ``work_objects.status='proposed'``) naming the Play that
fits, with the dimension evidence attached. It never starts a run, queues an
agent job or contacts a customer: accepting a proposal makes it planned work,
and any customer-facing step still goes through the normal write approval.

Guards:

* one proposal per account, Play and ``COOLDOWN_DAYS`` window (dedupe key), and
  none while the previous window's proposal is younger than the cooldown, so
  the same customer is not put forward for the same outreach twice;
* none while this account already has open work from the same Play.

Off unless ACCOUNT_PLAY_PROPOSALS_ENABLED, WORK_OBJECT_PROPOSALS_ENABLED and
ACCOUNT_HEALTH_ENABLED are all true.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

COOLDOWN_DAYS = 14
MAX_ACCOUNTS_PER_RUN = 20
CLOSED_STATUSES = frozenset({"archived", "completed", "cancelled", "failed"})

# (dimension key, statuses that trigger, Play key). Rules are explicit so the
# proposal can say exactly why it exists.
RULES: tuple[tuple[str, frozenset[str], str], ...] = (
    ("churn_risk_language", frozenset({"at_risk", "watch"}), "customer-rescue"),
    ("sentiment", frozenset({"at_risk"}), "customer-rescue"),
    ("support_friction", frozenset({"at_risk"}), "customer-rescue"),
    ("contact_gap", frozenset({"at_risk"}), "client-risk-radar"),
)
PLAY_TITLES = {
    "customer-rescue": "Review {name} for Customer Rescue",
    "client-risk-radar": "Check in on {name} (Client Risk Radar)",
}


def account_play_proposals_enabled(settings: Any) -> bool:
    return all(
        getattr(settings, flag, False) is True
        for flag in ("account_play_proposals_enabled", "work_object_proposals_enabled", "account_health_enabled")
    )


def matched_plays(health: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Play key -> the dimensions that triggered it."""
    dims = {d["key"]: d for d in health.get("dimensions") or []}
    out: dict[str, list[dict[str, Any]]] = {}
    for key, statuses, play in RULES:
        d = dims.get(key)
        if d and d.get("status") in statuses:
            out.setdefault(play, []).append(d)
    return out


def _window(now: datetime) -> int:
    return int(now.timestamp() // 86400) // COOLDOWN_DAYS


def _key(play: str, entity_id: str, window: int) -> str:
    return f"play:{play}:entity:{entity_id}:w{window}"


def _parse(ts: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _blocked(client: Any, org_id: str, entity_id: str, play: str, now: datetime) -> str | None:
    previous = (
        client.table("work_objects")
        .select("id, created_at")
        .eq("org_id", org_id)
        .eq("external_entity_type", "proposal")
        .eq("external_entity_id", _key(play, entity_id, _window(now) - 1))
        .limit(1)
        .execute()
        .data
        or []
    )
    if previous:
        created = _parse(previous[0].get("created_at"))
        if created is None or now - created < timedelta(days=COOLDOWN_DAYS):
            return "cooldown"
    linked = (
        client.table("work_objects")
        .select("id, status, metadata")
        .eq("org_id", org_id)
        .eq("business_entity_id", entity_id)
        .limit(200)
        .execute()
        .data
        or []
    )
    for row in linked:
        proposal = safe_normalize_stored_dict(safe_normalize_stored_dict(row.get("metadata")), key="proposal")
        if proposal.get("play_key") == play and row.get("status") not in CLOSED_STATUSES:
            return "open_work"
    return None


def propose_for_account(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    health: dict[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    from app.services.work_object_proposals import propose_work_object

    if not account_play_proposals_enabled(settings):
        return []
    now = now or datetime.now(UTC)
    entity = health.get("entity") or {}
    entity_id = str(entity.get("id") or "")
    name = str(entity.get("name") or "this account")
    if not entity_id:
        return []
    results = []
    for play, dims in matched_plays(health).items():
        blocked = _blocked(client, org_id, entity_id, play, now)
        if blocked:
            results.append({"play": play, "skipped": blocked})
            continue
        evidence = [
            {
                "dimension": d["label"],
                "status": d["status"],
                "rule": d["definition"],
                "evidence": d.get("evidence") or [],
                "coverage": d.get("coverage") or {},
            }
            for d in dims
        ]
        reasons = ", ".join(f"{d['label'].lower()} {d['status'].replace('_', ' ')}" for d in dims)
        out = propose_work_object(
            client,
            settings,
            org_id=org_id,
            title=PLAY_TITLES.get(play, "Review {name}").format(name=name),
            dedupe_key=_key(play, entity_id, _window(now)),
            source="account_health",
            evidence=evidence,
            objective=f"{name}: {reasons}. Proposed only; nothing is sent to the customer without approval.",
            department="support",
            object_type="other",
            priority="high" if any(d["status"] == "at_risk" for d in dims) else "medium",
            business_entity_id=entity_id,
            play_key=play,
        )
        results.append({"play": play, **out})
    return results


def run_account_play_proposals(
    client: Any, settings: Any, org_id: str, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Health for the most at-risk accounts, then proposals. Never raises."""
    from app.services.account_health import list_account_health, load_account_health

    if not account_play_proposals_enabled(settings):
        return []
    now = now or datetime.now(UTC)
    out: list[dict[str, Any]] = []
    try:
        listing = list_account_health(client, org_id, limit=MAX_ACCOUNTS_PER_RUN, now=now)
    except Exception as exc:  # noqa: BLE001
        logger.warning("account_play_proposals_list_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return out
    for account in listing.get("accounts") or []:
        if not account.get("atRisk") and not account.get("watch"):
            continue
        entity = {"id": account["entity"]["id"], "display_name": account["entity"]["name"]}
        try:
            health = load_account_health(client, org_id, entity, now=now)
            out.extend(propose_for_account(client, settings, org_id=org_id, health=health, now=now))
        except Exception as exc:  # noqa: BLE001
            logger.warning("account_play_proposal_failed org_id=%s error=%s", org_id, type(exc).__name__)
    return out
