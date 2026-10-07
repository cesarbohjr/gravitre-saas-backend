"""HubSpot source-of-record evidence reads.

Sync helpers that read a CRM record and normalise it into an *evidence dict*
used by Play outcome measurement (``services/play_outcome_measurement.py``),
webhook outcome capture and pipeline synthesis.

Contract (see shared CONTRACT.md, "Interface A -> B"):
- Every evidence dict has ``system="hubspot"``, ``record_type``, ``record_id``,
  ``observed_at`` (UTC ISO) and ``properties`` (raw HubSpot properties).
- Record fetchers return ``None`` when HubSpot reports 404; transport/auth errors
  raise :class:`HubSpotAPIError`.
- Counts the source cannot establish are ``None``, never a fabricated ``0``.
- Won/lost is resolved from pipeline stage metadata (``isClosed`` + ``probability``),
  falling back to the literal ``closedwon`` / ``closedlost`` ids only when metadata
  is absent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.connectors import hubspot
from app.connectors.hubspot import HubSpotAPIError

DEAL_EVIDENCE_PROPERTIES = [
    "dealname",
    "dealstage",
    "pipeline",
    "amount",
    "deal_currency_code",
    "closedate",
    "createdate",
    "hs_is_closed_won",
    "hs_is_closed",
]
CONTACT_EVIDENCE_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "jobtitle",
    "lifecyclestage",
    "hs_lead_status",
    "createdate",
]
COMPANY_EVIDENCE_PROPERTIES = [
    "name",
    "domain",
    "lifecyclestage",
    "createdate",
    "gravitre_icp_fit",
    "gravitre_qualified_at",
]

_INCOMING_DIRECTIONS = {"INCOMING_EMAIL"}
_OUTGOING_DIRECTIONS = {"EMAIL", "FORWARDED_EMAIL"}
_UNDELIVERED_STATUSES = {"BOUNCED", "FAILED", "SCHEDULED", "SENDING"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_not_found(exc: HubSpotAPIError) -> bool:
    return exc.status_code == 404


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _association_ids(record: dict[str, Any], to_type: str) -> list[str]:
    assoc = record.get("associations") or {}
    bucket = assoc.get(to_type) or assoc.get(to_type.rstrip("s")) or {}
    out: list[str] = []
    for row in bucket.get("results") or []:
        if isinstance(row, dict) and row.get("id") is not None:
            rid = str(row["id"])
            if rid not in out:
                out.append(rid)
    return out


def _base(record_type: str, record_id: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "system": "hubspot",
        "record_type": record_type,
        "record_id": str(record_id),
        "observed_at": _now_iso(),
        "properties": dict(properties or {}),
    }


# ---------------------------------------------------------------------------
# Pipeline stage resolution
# ---------------------------------------------------------------------------


def _pipeline_rows(pipelines_payload: Any) -> list[dict[str, Any]]:
    if isinstance(pipelines_payload, dict):
        rows = pipelines_payload.get("results")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        return []
    if isinstance(pipelines_payload, list):
        return [r for r in pipelines_payload if isinstance(r, dict)]
    return []


def resolve_stage_outcome(pipelines_payload: Any, pipeline_id: str | None, stage_id: str | None) -> str:
    """Return ``"won"`` / ``"lost"`` / ``"open"`` for a deal stage.

    Uses stage ``metadata.isClosed`` + ``metadata.probability`` from
    ``GET /crm/v3/pipelines/deals``. Custom pipelines use numeric stage ids, so
    literal ``closedwon`` / ``closedlost`` is only a fallback when no metadata
    exists for the stage.
    """
    stage = str(stage_id or "").strip()
    if not stage:
        return "open"
    pipe = str(pipeline_id or "").strip()
    candidates: list[dict[str, Any]] = []
    for row in _pipeline_rows(pipelines_payload):
        stages = [s for s in (row.get("stages") or []) if isinstance(s, dict)]
        for s in stages:
            if str(s.get("id") or "") == stage:
                if pipe and str(row.get("id") or "") == pipe:
                    candidates.insert(0, s)
                else:
                    candidates.append(s)
    for s in candidates:
        meta = s.get("metadata") or {}
        is_closed = _truthy(meta.get("isClosed"))
        prob = _to_float(meta.get("probability"))
        if is_closed is None and prob is None:
            continue
        if is_closed:
            if prob is not None and prob >= 1.0:
                return "won"
            if prob is not None and prob <= 0.0:
                return "lost"
            return "open"
        return "open"
    low = stage.lower()
    if low == "closedwon":
        return "won"
    if low == "closedlost":
        return "lost"
    return "open"


# ---------------------------------------------------------------------------
# Record evidence
# ---------------------------------------------------------------------------


def fetch_deal_evidence(
    access_token: str,
    deal_id: str,
    *,
    pipelines: Any = None,
) -> dict[str, Any] | None:
    try:
        record = hubspot.get_crm_object(
            access_token,
            "deals",
            str(deal_id),
            properties=DEAL_EVIDENCE_PROPERTIES,
            associations=["contacts"],
        )
    except HubSpotAPIError as exc:
        if _is_not_found(exc):
            return None
        raise
    if not record:
        return None
    props = record.get("properties") or {}
    if pipelines is None:
        try:
            pipelines = hubspot.list_deal_pipelines(access_token)
        except HubSpotAPIError:
            pipelines = None
    stage = props.get("dealstage")
    pipeline = props.get("pipeline")
    outcome = resolve_stage_outcome(pipelines, pipeline, stage)
    if pipelines is None:
        # No stage metadata available: fall back to HubSpot's computed flags.
        won_flag = _truthy(props.get("hs_is_closed_won"))
        closed_flag = _truthy(props.get("hs_is_closed"))
        if won_flag:
            outcome = "won"
        elif closed_flag and won_flag is False:
            outcome = "lost"
    ev = _base("deal", str(record.get("id") or deal_id), props)
    ev.update(
        {
            "amount": _to_float(props.get("amount")),
            "currency": (str(props.get("deal_currency_code")).upper() if props.get("deal_currency_code") else None),
            "dealstage": stage,
            "pipeline": pipeline,
            "closedate": props.get("closedate"),
            "createdate": props.get("createdate"),
            "stage_outcome": outcome,
            "associated_contact_ids": _association_ids(record, "contacts"),
        }
    )
    return ev


def fetch_contact_evidence(access_token: str, contact_id: str) -> dict[str, Any] | None:
    try:
        record = hubspot.get_crm_object(
            access_token,
            "contacts",
            str(contact_id),
            properties=CONTACT_EVIDENCE_PROPERTIES,
            associations=["companies"],
        )
    except HubSpotAPIError as exc:
        if _is_not_found(exc):
            return None
        raise
    if not record:
        return None
    props = record.get("properties") or {}
    ev = _base("contact", str(record.get("id") or contact_id), props)
    ev.update(
        {
            "lifecyclestage": props.get("lifecyclestage"),
            "hs_lead_status": props.get("hs_lead_status"),
            "email": props.get("email"),
            "createdate": props.get("createdate"),
            "associated_company_ids": _association_ids(record, "companies"),
        }
    )
    return ev


def fetch_company_evidence(access_token: str, company_id: str) -> dict[str, Any] | None:
    try:
        record = hubspot.get_crm_object(
            access_token,
            "companies",
            str(company_id),
            properties=COMPANY_EVIDENCE_PROPERTIES,
        )
    except HubSpotAPIError as exc:
        if _is_not_found(exc):
            return None
        raise
    if not record:
        return None
    props = record.get("properties") or {}
    ev = _base("company", str(record.get("id") or company_id), props)
    ev.update(
        {
            "domain": props.get("domain"),
            "lifecyclestage": props.get("lifecyclestage"),
            "createdate": props.get("createdate"),
            "icp_fit": _to_float(props.get("gravitre_icp_fit")),
            "qualified_at": props.get("gravitre_qualified_at") or None,
        }
    )
    return ev


def _meeting_evidence_from_record(record: dict[str, Any]) -> dict[str, Any]:
    props = record.get("properties") or {}
    ev = _base("meeting", str(record.get("id") or ""), props)
    ev.update(
        {
            "start_time": props.get("hs_meeting_start_time") or props.get("hs_timestamp"),
            "end_time": props.get("hs_meeting_end_time"),
            "outcome": props.get("hs_meeting_outcome"),
            "createdate": props.get("hs_createdate") or record.get("createdAt"),
            "associated_contact_ids": _association_ids(record, "contacts"),
            "associated_deal_ids": _association_ids(record, "deals"),
        }
    )
    return ev


def fetch_meeting_evidence(access_token: str, meeting_id: str) -> dict[str, Any] | None:
    try:
        record = hubspot.get_meeting(access_token, str(meeting_id))
    except HubSpotAPIError as exc:
        if _is_not_found(exc):
            return None
        raise
    if not record:
        return None
    return _meeting_evidence_from_record(record)


def list_meetings_for_contact(access_token: str, contact_id: str) -> list[dict[str, Any]]:
    """Meeting evidence dicts for meetings associated to a contact."""
    assoc = hubspot.list_associations(
        access_token, from_type="contacts", from_id=str(contact_id), to_type="meetings"
    )
    out: list[dict[str, Any]] = []
    for mid in assoc.get("ids") or []:
        ev = fetch_meeting_evidence(access_token, mid)
        if ev is not None:
            out.append(ev)
    return out


def _parse_hs_time(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc)
        except (OverflowError, ValueError):
            return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch_contact_outreach_evidence(
    access_token: str,
    contact_id: str,
    *,
    since_iso: str | None = None,
) -> dict[str, Any]:
    """Outbound/inbound email engagement evidence for a contact.

    When the engagement search is not permitted (403) or otherwise fails with a
    client error, the counts are ``None`` (source could not tell), never ``0``.
    """
    since_dt = _parse_hs_time(since_iso) if since_iso else None
    since_ms = int(since_dt.timestamp() * 1000) if since_dt else None
    base: dict[str, Any] = {
        "system": "hubspot",
        "record_type": "contact_outreach",
        "record_id": str(contact_id),
        "observed_at": _now_iso(),
        "delivered_count": None,
        "first_sent_at": None,
        "reply_count": None,
        "first_reply_at": None,
        "emails": [],
    }
    try:
        payload = hubspot.search_contact_emails(access_token, str(contact_id), since_ms=since_ms)
    except HubSpotAPIError as exc:
        if exc.status_code in {401}:
            raise
        if exc.status_code is not None and 400 <= exc.status_code < 500:
            base["unavailable_reason"] = f"hubspot_{exc.status_code}"
            return base
        raise
    emails: list[dict[str, Any]] = []
    delivered = 0
    replies = 0
    first_sent: datetime | None = None
    first_reply: datetime | None = None
    for row in payload.get("results") or []:
        props = row.get("properties") or {}
        direction = str(props.get("hs_email_direction") or "").upper() or None
        status = str(props.get("hs_email_status") or "").upper() or None
        ts = _parse_hs_time(props.get("hs_timestamp"))
        emails.append(
            {
                "id": str(row.get("id") or ""),
                "direction": direction,
                "timestamp": ts.isoformat() if ts else props.get("hs_timestamp"),
                "status": status,
            }
        )
        if direction in _OUTGOING_DIRECTIONS and status not in _UNDELIVERED_STATUSES:
            delivered += 1
            if ts and (first_sent is None or ts < first_sent):
                first_sent = ts
        elif direction in _INCOMING_DIRECTIONS:
            replies += 1
            if ts and (first_reply is None or ts < first_reply):
                first_reply = ts
    base.update(
        {
            "delivered_count": delivered,
            "reply_count": replies,
            "first_sent_at": first_sent.isoformat() if first_sent else None,
            "first_reply_at": first_reply.isoformat() if first_reply else None,
            "emails": emails,
        }
    )
    if payload.get("truncated"):
        base["truncated"] = True
    return base


def search_deals_all(
    access_token: str,
    *,
    filter_groups: list[dict[str, Any]],
    properties: list[str] | None = None,
    max_records: int = 2000,
) -> list[dict[str, Any]]:
    """Paginated deal search (follows the ``after`` cursor up to ``max_records``)."""
    payload = hubspot.search_crm_objects_all(
        access_token,
        "deals",
        filter_groups=filter_groups,
        properties=properties or DEAL_EVIDENCE_PROPERTIES,
        max_records=max_records,
    )
    return list(payload.get("results") or [])


__all__ = [
    "fetch_company_evidence",
    "fetch_contact_evidence",
    "fetch_contact_outreach_evidence",
    "fetch_deal_evidence",
    "fetch_meeting_evidence",
    "list_meetings_for_contact",
    "resolve_stage_outcome",
    "search_deals_all",
]
