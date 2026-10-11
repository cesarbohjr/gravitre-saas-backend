"""Find the person, record, list or file a user names, in their own accounts.

One contract for every source. A lookup returns a ``Resolution``:

* ``resolved``: exactly one candidate, the search covered enough to say so,
  and the evidence is real (not only a draft).
* ``ambiguous``: more than one candidate, or one that needs the user's
  confirmation (seen only in a draft). Gravitre asks; it never picks.
* ``not_found``: the search completed and nothing matched.
* ``incomplete``: the search stopped early (page cap, time budget, a page
  that failed, more results than one page holds). Never treated as unique:
  Gravitre asks rather than asserts.
* ``unavailable``: the source is not connected, the read failed, or the
  capability does not exist yet. ``reason`` says which, so the reply can be
  honest ("I can't search HubSpot lists yet").

Each ``ResolutionCandidate`` keeps where it came from: the source, the
account (integration row) that was searched, the object type and id, an
access flag, when it was found, and the evidence. Lookups only read through
existing connector read actions (``tool_service`` executors); nothing here
writes, and nothing searches the public web.
"""
from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from email.utils import getaddresses
from typing import Any, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ResolutionStatus = Literal["resolved", "ambiguous", "not_found", "incomplete", "unavailable"]

# Cached candidates older than this are looked up again before use.
CANDIDATE_TTL_S = 15 * 60
# A file's access is read again before the approval prompt when older than this.
FILE_VERIFY_TTL_S = 5 * 60
# Budget for one non-Gmail lookup (all of its reads together).
OBJECT_LOOKUP_BUDGET_S = 4.0
# One page of search results; a full page means more may exist.
SEARCH_PAGE_SIZE = 25

# Read errors that mean the account itself can no longer be read.
_PERMISSION_CODES = frozenset(
    {
        "permission_denied",
        "auth_expired",
        "missing_scope",
        "connector_not_connected",
        "auth_invalid",
        "not_configured",
        "permission_blocked",
    }
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolutionCandidate:
    """One thing the user might mean, with where and how it was found."""

    name: str
    address: str = ""
    source: str = ""
    # The integration row (``connectors.id``) that was searched. Empty when
    # the vendor's default connection answered and no row id was visible.
    account: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    object_type: str = "person"
    # Record or file id. For a mail participant the address is the id.
    object_id: str = ""
    account_label: str = ""
    # "ok": a read of this object succeeded for this account; "denied": it
    # failed; "unknown": not checked.
    access: str = "unknown"
    resolved_at: float = 0.0
    # The account row's ``updated_at`` when it was searched; a reconnect
    # changes it and makes the candidate stale.
    account_stamp: str = ""

    @property
    def domain(self) -> str:
        return self.address.rsplit("@", 1)[-1].lower() if "@" in self.address else ""

    @property
    def key(self) -> str:
        return (self.object_id or self.address).lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "source": self.source,
            "account": self.account,
            "evidence": dict(self.evidence),
            "object_type": self.object_type,
            "object_id": self.object_id or self.address,
            "account_label": self.account_label,
            "access": self.access,
            "resolved_at": self.resolved_at,
            "account_stamp": self.account_stamp,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> ResolutionCandidate | None:
        if not isinstance(raw, dict) or not (raw.get("address") or raw.get("object_id")):
            return None
        evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
        try:
            resolved_at = float(raw.get("resolved_at") or 0.0)
        except (TypeError, ValueError):
            resolved_at = 0.0
        return cls(
            name=str(raw.get("name") or ""),
            address=str(raw.get("address") or ""),
            source=str(raw.get("source") or ""),
            account=str(raw.get("account") or ""),
            evidence=dict(evidence),
            object_type=str(raw.get("object_type") or "person"),
            object_id=str(raw.get("object_id") or raw.get("address") or ""),
            account_label=str(raw.get("account_label") or ""),
            access=str(raw.get("access") or "unknown"),
            resolved_at=resolved_at,
            account_stamp=str(raw.get("account_stamp") or ""),
        )


@dataclass
class Resolution:
    status: ResolutionStatus
    query: str
    candidates: list[ResolutionCandidate] = field(default_factory=list)
    source: str = "gmail"
    latency_ms: int = 0
    object_type: str = "person"
    # Why the status is what it is ("page_cap", "permission", "not_connected",
    # "capability_missing", "draft_only", ...).
    reason: str = ""
    # How far the search got: pages, messages or rows read, whether the
    # result set was exhausted, what was excluded as noise.
    coverage: dict[str, Any] = field(default_factory=dict)
    accounts: list[str] = field(default_factory=list)
    # Connector reads this lookup made.
    calls: int = 0

    @property
    def chosen(self) -> ResolutionCandidate | None:
        return self.candidates[0] if self.status == "resolved" and self.candidates else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "source": self.source,
            "object_type": self.object_type,
            "reason": self.reason,
            "candidates": [c.to_dict() for c in self.candidates],
            "coverage": dict(self.coverage),
            "accounts": list(self.accounts),
            "calls": self.calls,
            "latency_ms": self.latency_ms,
        }


def decide(
    query: str,
    candidates: list[ResolutionCandidate],
    *,
    complete: bool,
    source: str,
    object_type: str,
    reason: str = "",
    exact: Callable[[ResolutionCandidate], bool] | None = None,
) -> Resolution:
    """The one rule every source shares for turning candidates into a status."""
    if not candidates:
        return Resolution(
            status="not_found" if complete else "incomplete",
            query=query,
            source=source,
            object_type=object_type,
            reason="" if complete else (reason or "coverage"),
        )
    if exact is not None and len(candidates) > 1:
        exacts = [c for c in candidates if exact(c)]
        if len(exacts) == 1 and complete:
            # The user said the whole name of exactly one of them.
            return Resolution(
                status="resolved", query=query, candidates=exacts, source=source, object_type=object_type
            )
    if len(candidates) > 1:
        return Resolution(
            status="ambiguous",
            query=query,
            candidates=candidates[:4],
            source=source,
            object_type=object_type,
            reason=reason,
            coverage={"total_candidates": len(candidates)},
        )
    only = candidates[0]
    if not complete:
        return Resolution(
            status="incomplete",
            query=query,
            candidates=[only],
            source=source,
            object_type=object_type,
            reason=reason or "coverage",
        )
    if only.evidence.get("draft_only"):
        return Resolution(
            status="ambiguous",
            query=query,
            candidates=[only],
            source=source,
            object_type=object_type,
            reason="draft_only",
        )
    return Resolution(status="resolved", query=query, candidates=[only], source=source, object_type=object_type)


def unavailable(query: str, *, source: str, object_type: str, reason: str) -> Resolution:
    return Resolution(status="unavailable", query=query, source=source, object_type=object_type, reason=reason)


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


def is_fresh(candidate: ResolutionCandidate, *, now: float | None = None, ttl_s: float = CANDIDATE_TTL_S) -> bool:
    if candidate.resolved_at <= 0:
        return False
    return ((now if now is not None else time.time()) - candidate.resolved_at) <= ttl_s


@dataclass(frozen=True)
class Account:
    """A connected account (one ``connectors`` row) a lookup can search."""

    id: str
    vendor: str
    label: str
    stamp: str = ""
    emails: tuple[str, ...] = ()


def connected_accounts(
    client: Any,
    org_id: str,
    vendor: str,
    *,
    environment_name: str = "production",
) -> list[Account]:
    """Usable rows for ``vendor``, most recently updated first.

    That order is the one ``get_connector_by_type`` uses, so the first row is
    the account a send goes from when none is named.
    """
    try:
        from app.connectors.constants import ACTIVE_CONNECTOR_STATUSES
        from app.connectors.repository import list_connectors
        from app.intelligence_packs.shared.auth_mode import connector_type_lookup_keys

        keys = set(connector_type_lookup_keys(vendor))
        rows = [
            r
            for r in list_connectors(client, org_id, environment_name)
            if str(r.get("type") or "").lower() in keys
            and str(r.get("status") or "").lower() in ACTIVE_CONNECTOR_STATUSES
        ]
    except Exception as exc:  # noqa: BLE001
        logger.info("object_resolution_accounts_unreadable vendor=%s error=%s", vendor, type(exc).__name__)
        return []
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    out: list[Account] = []
    for row in rows:
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        emails = tuple(
            sorted(
                {
                    str(cfg.get(k)).strip().lower()
                    for k in ("email", "account_email", "google_email", "user_email", "mailbox")
                    if cfg.get(k) and "@" in str(cfg.get(k))
                }
            )
        )
        label = (
            (emails[0] if emails else "")
            or str(cfg.get("display_name") or cfg.get("account_name") or cfg.get("name") or "").strip()
            or f"{vendor_label(vendor)} account"
        )
        out.append(
            Account(
                id=str(row.get("id") or ""),
                vendor=vendor,
                label=label,
                stamp=str(row.get("updated_at") or ""),
                emails=emails,
            )
        )
    return out


def select_account(accounts: list[Account], message: str) -> tuple[Account | None, str]:
    """The account the user named, else the default one; and how it was chosen."""
    if not accounts:
        return None, "vendor_default"
    low = (message or "").lower()
    for account in accounts:
        if any(email in low for email in account.emails):
            return account, "named"
    for account in accounts:
        label = account.label.lower()
        if label and "@" not in label and re.search(rf"\b{re.escape(label)}\b", low):
            return account, "named"
    return accounts[0], "default"


def stale_reason(
    candidate: ResolutionCandidate,
    accounts: list[Account] | None,
    *,
    now: float | None = None,
) -> str:
    """Why a cached candidate can no longer be used, or "" when it can."""
    if not is_fresh(candidate, now=now):
        return "expired"
    if accounts is None or not candidate.account:
        return ""
    row = next((a for a in accounts if a.id == candidate.account), None)
    if row is None:
        return "account_removed"
    if candidate.account_stamp and row.stamp and row.stamp != candidate.account_stamp:
        return "account_changed"
    return ""


def read_failure_reason(error_code: str | None) -> str:
    code = str(error_code or "").strip().lower()
    if code in _PERMISSION_CODES or "auth" in code or "permission" in code or "scope" in code:
        return "permission"
    if "rate" in code:
        return "rate_limited"
    return "error"


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if t]


def name_matches(query: str, display: str, address: str = "") -> bool:
    """Every word of the query starts a word of the display name or address."""
    want = tokens(query)
    if not want:
        return False
    have = tokens(display) + tokens(address.split("@", 1)[0])
    return all(any(h == w or (len(w) >= 3 and h.startswith(w)) for h in have) for w in want)


_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "last": -1}
_FILLER = {
    "the", "one", "at", "please", "her", "him", "them", "its", "it", "s", "on", "in", "from", "file",
    "use", "that", "this", "i", "mean", "meant", "go", "with", "a", "an", "list", "segment",
}
_YES_PART = (
    r"(?:yes|yeah|yep|yup|correct|right|sure|ok(?:ay)?|please|that'?s (?:her|him|them|it|the one|right|correct)|"
    r"that one|use (?:that|it)(?: one)?|(?:she|he|it)'?s the one)"
)
_YES_RE = re.compile(rf"(?i)^\s*{_YES_PART}(?:[\s,.!]+{_YES_PART})*[\s.!]*$")


def candidate_words(candidate: ResolutionCandidate) -> list[str]:
    words = tokens(candidate.name) + tokens(candidate.address.split("@", 1)[0]) + tokens(candidate.domain)
    for key in ("folder", "path", "company", "modified_label", "source_label"):
        value = candidate.evidence.get(key)
        if value:
            words += tokens(str(value))
    return words


def pick_from(reply: str, candidates: list[ResolutionCandidate]) -> ResolutionCandidate | None:
    """The candidate a reply points at ("Khan", "the second one", an address, "yes")."""
    text = (reply or "").strip()
    if not text or not candidates:
        return None
    emails = [e.lower() for e in _EMAIL_RE.findall(text)]
    if emails:
        return next((c for c in candidates if c.address.lower() in emails), None)
    if len(candidates) == 1 and _YES_RE.match(text):
        return candidates[0]
    low = text.lower()
    m = re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|last)\b", low)
    if m:
        try:
            return candidates[_ORDINALS[m.group(1)]]
        except IndexError:
            return None
    words = [w for w in tokens(text) if w not in _FILLER]
    if not words:
        return None
    hits = [c for c in candidates if all(w in candidate_words(c) for w in words)]
    return hits[0] if len(hits) == 1 else None


def join_or(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# ---------------------------------------------------------------------------
# Mail participants (shared by Gmail and Outlook)
# ---------------------------------------------------------------------------

# Senders that are machines or roles, never a person to write to: a no-reply
# marker anywhere in the local part ("comments-noreply"), or a role word that
# starts it ("notifications+abc", "newsletter").
_NO_REPLY_RE = re.compile(
    r"(?:^|[-_.+])(?:no[-_.]?reply|do[-_.]?not[-_.]?reply|donotreply)(?:[-_.+]|$)|"
    r"^(?:mailer[-_.]?daemon|postmaster|bounces?|notifications?|notify|alerts?|newsletters?|news|"
    r"digest|updates|marketing|automated|system|unsubscribe)(?:[-+._].*)?$",
    re.IGNORECASE,
)
# "Stephanie Khan via Acme Team <team@lists.acme.example>": a list relaying her.
_VIA_RE = re.compile(r"\bvia\b", re.IGNORECASE)


@dataclass
class MailRow:
    """One message's participants, already parsed, vendor-neutral."""

    sender: list[tuple[str, str]]
    to: list[tuple[str, str]]
    cc: list[tuple[str, str]]
    kind: str  # "sent" | "received" | "draft"
    date: str = ""
    bulk: bool = False


def parse_addresses(value: str) -> list[tuple[str, str]]:
    return [(d.strip(), a.strip()) for d, a in getaddresses([value or ""]) if a and "@" in a]


def participants_from_rows(
    query: str,
    rows: list[MailRow],
    *,
    source: str,
    account: Account | None = None,
    own: set[str] | None = None,
    now: float | None = None,
) -> tuple[list[ResolutionCandidate], dict[str, int]]:
    """One candidate per matching address, and what was left out as noise."""
    own_addresses = {a.lower() for a in (own or set())}
    if account is not None:
        own_addresses |= set(account.emails)
    for row in rows:
        if row.kind in {"sent", "draft"}:
            own_addresses |= {addr.lower() for _d, addr in row.sender}
    excluded: dict[str, int] = {"own": 0, "no_reply": 0, "list_relay": 0, "bulk_only": 0}
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        for header, people in (("from", row.sender), ("to", row.to), ("cc", row.cc)):
            for display, addr in people:
                low = addr.lower()
                if not name_matches(query, display, addr):
                    continue
                if low in own_addresses:
                    excluded["own"] += 1
                    continue
                if _NO_REPLY_RE.search(low.split("@", 1)[0]):
                    excluded["no_reply"] += 1
                    continue
                if display and _VIA_RE.search(display):
                    excluded["list_relay"] += 1
                    continue
                entry = seen.setdefault(
                    low,
                    {
                        "address": addr,
                        "names": {},
                        "sent": 0,
                        "received": 0,
                        "draft": 0,
                        "bulk": 0,
                        "last_seen": "",
                    },
                )
                if display:
                    entry["names"][display] = entry["names"].get(display, 0) + 1
                if row.bulk and row.kind == "received":
                    entry["bulk"] += 1
                else:
                    entry[row.kind] += 1
                if row.date and not entry["last_seen"]:
                    entry["last_seen"] = row.date
    stamp = now if now is not None else time.time()
    out: list[ResolutionCandidate] = []
    for entry in seen.values():
        real = entry["sent"] + entry["received"]
        if real == 0 and entry["draft"] == 0:
            # Seen only on newsletters, promotions or list mail.
            excluded["bulk_only"] += 1
            continue
        names = entry["names"]
        name = max(names, key=names.get) if names else entry["address"].split("@", 1)[0]
        out.append(
            ResolutionCandidate(
                name=name,
                address=entry["address"],
                source=source,
                account=account.id if account else "",
                account_label=account.label if account else "",
                account_stamp=account.stamp if account else "",
                object_type="person",
                object_id=entry["address"],
                resolved_at=stamp,
                evidence={
                    "sent": entry["sent"],
                    "received": entry["received"],
                    "draft": entry["draft"],
                    "bulk": entry["bulk"],
                    "draft_only": real == 0,
                    "last_seen": entry["last_seen"],
                    "query": query,
                },
            )
        )
    # People the user wrote to first, then people who wrote; draft-only last.
    out.sort(
        key=lambda c: (
            -(2 * c.evidence.get("sent", 0) + c.evidence.get("received", 0)),
            -c.evidence.get("draft", 0),
        )
    )
    return out, excluded


# ---------------------------------------------------------------------------
# Running reads
# ---------------------------------------------------------------------------


class _Reads:
    """Read actions through ``invoke_tool``, counted."""

    def __init__(self, *, org_id: str, client: Any, settings: Any, user_id: str | None, conversation_id: str | None):
        from app.services.sealed_read_execution import attributable_read_actor_id
        from app.services.tool_types import ToolContext

        self.ctx = ToolContext(
            settings=settings,
            client=client,
            org_id=org_id,
            actor_id=attributable_read_actor_id(user_id) or "object-resolution",
            environment_name="production",
            conversation_id=conversation_id or None,
        )
        self.calls = 0

    def run(self, action: str, params: dict[str, Any]) -> Any:
        from app.services.tool_service import invoke_tool

        self.calls += 1
        return invoke_tool(self.ctx, action, dict(params))


async def _bounded(fn: Callable[[], Resolution], *, query: str, source: str, object_type: str) -> Resolution:
    started = time.perf_counter()
    try:
        resolution = await asyncio.wait_for(asyncio.to_thread(fn), timeout=OBJECT_LOOKUP_BUDGET_S)
    except TimeoutError:
        resolution = unavailable(query, source=source, object_type=object_type, reason="time_budget")
    except Exception as exc:  # noqa: BLE001
        logger.info("object_resolution_failed source=%s error=%s", source, type(exc).__name__)
        resolution = unavailable(query, source=source, object_type=object_type, reason="error")
    resolution.latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "object_resolution source=%s type=%s status=%s reason=%s candidates=%d calls=%d latency_ms=%d",
        source,
        object_type,
        resolution.status,
        resolution.reason,
        len(resolution.candidates),
        resolution.calls,
        resolution.latency_ms,
    )
    return resolution


def _data(result: Any) -> dict[str, Any]:
    data = getattr(result, "data", None)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Capabilities: what can be searched today
# ---------------------------------------------------------------------------

_SOURCE_LABELS = {
    "gmail": "Gmail",
    "microsoft365": "Outlook",
    "outlook": "Outlook",
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "apollo": "Apollo",
    "constant_contact": "Constant Contact",
    "mailchimp": "Mailchimp",
    "klaviyo": "Klaviyo",
    "google_drive": "Google Drive",
    "onedrive": "OneDrive",
    "notion": "Notion",
    "confluence": "Confluence",
    "slack": "Slack",
    "dropbox": "Dropbox",
    "pipedrive": "Pipedrive",
}


def vendor_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source.replace("_", " ").title())


# (object type, source) -> (state, read action or reason). "supported" rows
# have a resolver below; every other row answers "unavailable" honestly.
CAPABILITIES: dict[tuple[str, str], tuple[str, str]] = {
    ("person", "gmail"): ("supported", "gmail.messages.list + gmail.messages.get (metadata)"),
    ("person", "microsoft365"): ("supported", "microsoft365.mail.messages.list ($search) + microsoft365.users.get"),
    ("contact", "hubspot"): ("supported", "hubspot.contacts.search"),
    ("contact", "salesforce"): ("supported", "salesforce.contacts.search"),
    ("contact", "pipedrive"): ("proposed", "pipedrive.persons.search exists; no resolver yet"),
    ("contact", "apollo"): ("proposed", "apollo.contacts.search exists; no resolver yet"),
    ("list", "apollo"): ("supported", "apollo.lists.list (name matched here)"),
    ("list", "constant_contact"): ("supported", "constant_contact.contact_lists.list (name matched here)"),
    ("segment", "constant_contact"): ("supported", "constant_contact.segments.list (name matched here)"),
    ("list", "hubspot"): ("unavailable", "only hubspot.lists.get by id; no list search"),
    ("segment", "hubspot"): ("unavailable", "no segment read action"),
    ("list", "mailchimp"): ("unavailable", "mailchimp.audiences.list is not verified (path suspected wrong)"),
    ("list", "klaviyo"): ("unavailable", "not integrated"),
    ("file", "google_drive"): ("supported", "google_drive.search_files + google_drive.get_file_metadata"),
    ("file", "microsoft365"): ("supported", "microsoft365.search_files + microsoft365.get_file_metadata (OneDrive)"),
    ("file", "notion"): ("proposed", "notion.search_files exists; no resolver yet"),
    ("file", "confluence"): ("proposed", "confluence.search_files exists; no resolver yet"),
    ("file", "slack"): ("proposed", "slack.search_files exists; no resolver yet"),
    ("file", "dropbox"): ("unavailable", "not integrated"),
}

_TYPE_WORDS = {"person": "people", "contact": "contacts", "list": "lists", "segment": "segments", "file": "files"}


def capability(object_type: str, source: str) -> tuple[str, str]:
    return CAPABILITIES.get((object_type, source), ("unavailable", "no read action"))


def cant_search_yet(object_type: str, source: str) -> str:
    """The honest line for a lookup Gravitre cannot do."""
    return f"I can't search {vendor_label(source)} {_TYPE_WORDS.get(object_type, object_type + 's')} yet."


# ---------------------------------------------------------------------------
# Outlook participants
# ---------------------------------------------------------------------------

OUTLOOK_PAGE = 50


def _graph_people(raw: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in raw if isinstance(raw, list) else [raw]:
        email = item.get("emailAddress") if isinstance(item, dict) else None
        if isinstance(email, dict) and "@" in str(email.get("address") or ""):
            out.append((str(email.get("name") or ""), str(email.get("address"))))
    return out


def outlook_rows(messages: list[dict[str, Any]], own: set[str]) -> list[MailRow]:
    rows: list[MailRow] = []
    for msg in messages:
        sender = _graph_people(msg.get("from"))
        if msg.get("isDraft"):
            kind = "draft"
        elif any(a.lower() in own for _d, a in sender):
            kind = "sent"
        else:
            kind = "received"
        bulk = str(msg.get("inferenceClassification") or "").lower() == "other" and kind == "received"
        rows.append(
            MailRow(
                sender=sender,
                to=_graph_people(msg.get("toRecipients") or []),
                cc=_graph_people(msg.get("ccRecipients") or []),
                kind=kind,
                date=str(msg.get("receivedDateTime") or msg.get("sentDateTime") or ""),
                bulk=bulk,
            )
        )
    return rows


async def resolve_outlook_participant(
    name: str,
    *,
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    message: str = "",
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> Resolution:
    """People named ``name`` in the user's Outlook mail (headers only)."""
    if "microsoft365" not in connected and "outlook" not in connected:
        return unavailable(name, source="microsoft365", object_type="person", reason="not_connected")
    accounts = connected_accounts(client, org_id, "microsoft365")
    account, _how = select_account(accounts, message)

    def _run() -> Resolution:
        reads = _Reads(org_id=org_id, client=client, settings=settings, user_id=user_id, conversation_id=conversation_id)
        pin = {"connector_id": account.id} if account else {}
        own: set[str] = set(account.emails) if account else set()
        me = reads.run("microsoft365.users.get", {**pin})
        if getattr(me, "success", False):
            user = _data(me).get("user") if isinstance(_data(me).get("user"), dict) else _data(me)
            for key in ("mail", "userPrincipalName"):
                if "@" in str(user.get(key) or ""):
                    own.add(str(user[key]).lower())
        listed = reads.run(
            "microsoft365.mail.messages.list",
            {**pin, "search": f"participants:{name}", "top": OUTLOOK_PAGE},
        )
        if not getattr(listed, "success", False):
            res = unavailable(
                name,
                source="microsoft365",
                object_type="person",
                reason=read_failure_reason(getattr(listed, "error_code", None)),
            )
            res.calls = reads.calls
            return res
        data = _data(listed)
        messages = [m for m in (data.get("value") or []) if isinstance(m, dict)]
        complete = not data.get("@odata.nextLink")
        cands, excluded = participants_from_rows(
            name, outlook_rows(messages, own), source="microsoft365", account=account, own=own
        )
        res = decide(name, cands, complete=complete, source="microsoft365", object_type="person", reason="page_cap")
        res.calls = reads.calls
        res.accounts = [account.label] if account else []
        res.coverage.update(
            {"complete": complete, "messages_read": len(messages), "pages": 1, "excluded": excluded}
        )
        return res

    return await _bounded(_run, query=name, source="microsoft365", object_type="person")


# ---------------------------------------------------------------------------
# CRM contacts
# ---------------------------------------------------------------------------


async def resolve_crm_contact(
    name: str,
    *,
    source: str,
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> Resolution:
    """A contact record named ``name`` in HubSpot or Salesforce."""
    state, _detail = capability("contact", source)
    if state != "supported":
        return unavailable(name, source=source, object_type="contact", reason="capability_missing")
    if source not in connected:
        return unavailable(name, source=source, object_type="contact", reason="not_connected")
    accounts = connected_accounts(client, org_id, source)
    account = accounts[0] if accounts else None

    def _run() -> Resolution:
        reads = _Reads(org_id=org_id, client=client, settings=settings, user_id=user_id, conversation_id=conversation_id)
        pin = {"connector_id": account.id} if account else {}
        rows: list[tuple[str, str, str, dict[str, Any]]] = []
        complete = False
        if source == "hubspot":
            got = reads.run(
                "hubspot.contacts.search",
                {**pin, "query": name, "limit": 10, "properties": ["firstname", "lastname", "email", "company"]},
            )
            if getattr(got, "success", False):
                data = _data(got)
                contacts = [c for c in (data.get("contacts") or []) if isinstance(c, dict)]
                for c in contacts:
                    props = c.get("properties") if isinstance(c.get("properties"), dict) else {}
                    display = " ".join(str(props.get(k) or "").strip() for k in ("firstname", "lastname")).strip()
                    rows.append((str(c.get("id") or ""), display, str(props.get("email") or ""), {"company": props.get("company") or ""}))
                total = int(data.get("total") or len(contacts))
                complete = total <= len(contacts)
        else:
            got = reads.run("salesforce.contacts.search", {**pin, "name": name, "limit": SEARCH_PAGE_SIZE})
            if getattr(got, "success", False):
                results = _data(got).get("results") if isinstance(_data(got).get("results"), dict) else {}
                records = [r for r in (results.get("records") or []) if isinstance(r, dict)]
                for r in records:
                    rows.append((str(r.get("Id") or ""), str(r.get("Name") or ""), str(r.get("Email") or ""), {"account_id": r.get("AccountId") or ""}))
                total = int(results.get("totalSize") or len(records))
                complete = bool(results.get("done", True)) and total <= len(records)
        if not getattr(got, "success", False):
            res = unavailable(
                name,
                source=source,
                object_type="contact",
                reason=read_failure_reason(getattr(got, "error_code", None)),
            )
            res.calls = reads.calls
            return res
        now = time.time()
        cands = [
            ResolutionCandidate(
                name=display or address,
                address=address,
                source=source,
                account=account.id if account else str(getattr(got, "connector_id", "") or ""),
                account_label=account.label if account else "",
                account_stamp=account.stamp if account else "",
                object_type="contact",
                object_id=record_id,
                access="ok",
                resolved_at=now,
                evidence={**extra, "query": name},
            )
            for record_id, display, address, extra in rows
            if record_id and name_matches(name, display, address)
        ]
        res = decide(
            name,
            cands,
            complete=complete,
            source=source,
            object_type="contact",
            reason="page_cap",
            exact=lambda c: c.name.lower() == name.lower(),
        )
        res.calls = reads.calls
        res.coverage.update({"complete": complete, "rows_read": len(rows)})
        return res

    return await _bounded(_run, query=name, source=source, object_type="contact")


# ---------------------------------------------------------------------------
# Lists and segments
# ---------------------------------------------------------------------------

_LIST_ACTIONS = {
    ("list", "apollo"): ("apollo.lists.list", "labels", "id"),
    ("list", "constant_contact"): ("constant_contact.contact_lists.list", "lists", "list_id"),
    ("segment", "constant_contact"): ("constant_contact.segments.list", "segments", "segment_id"),
}
_LIST_STOP = {"list", "lists", "segment", "segments", "audience", "the", "my", "our"}


def _list_query_words(query: str) -> list[str]:
    return [w for w in tokens(query) if w not in _LIST_STOP]


async def resolve_list(
    name: str,
    *,
    source: str,
    object_type: str = "list",
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> Resolution:
    """A list or segment named ``name``. The vendors list them all; names are matched here."""
    spec = _LIST_ACTIONS.get((object_type, source))
    if spec is None:
        return unavailable(name, source=source, object_type=object_type, reason="capability_missing")
    if source not in connected:
        return unavailable(name, source=source, object_type=object_type, reason="not_connected")
    action, rows_key, id_key = spec
    accounts = connected_accounts(client, org_id, source)
    account = accounts[0] if accounts else None
    want = _list_query_words(name)

    def _run() -> Resolution:
        reads = _Reads(org_id=org_id, client=client, settings=settings, user_id=user_id, conversation_id=conversation_id)
        pin = {"connector_id": account.id} if account else {}
        params = {**pin, "limit": 500} if source == "constant_contact" else {**pin}
        got = reads.run(action, params)
        if not getattr(got, "success", False):
            res = unavailable(
                name, source=source, object_type=object_type, reason=read_failure_reason(getattr(got, "error_code", None))
            )
            res.calls = reads.calls
            return res
        data = _data(got)
        rows = [r for r in (data.get(rows_key) or []) if isinstance(r, dict)]
        links = data.get("_links") if isinstance(data.get("_links"), dict) else {}
        complete = not links.get("next")
        now = time.time()
        cands = []
        for row in rows:
            title = str(row.get("name") or "").strip()
            have = tokens(title)
            if not title or not want or not all(any(h == w or (len(w) >= 3 and h.startswith(w)) for h in have) for w in want):
                continue
            count = row.get("membership_count", row.get("cached_count", row.get("contact_count")))
            cands.append(
                ResolutionCandidate(
                    name=title,
                    source=source,
                    account=account.id if account else str(getattr(got, "connector_id", "") or ""),
                    account_label=account.label if account else "",
                    account_stamp=account.stamp if account else "",
                    object_type=object_type,
                    object_id=str(row.get(id_key) or row.get("id") or ""),
                    access="ok",
                    resolved_at=now,
                    evidence={"members": count, "query": name},
                )
            )
        res = decide(
            name,
            cands,
            complete=complete,
            source=source,
            object_type=object_type,
            reason="page_cap",
            exact=lambda c: _list_query_words(c.name) == want,
        )
        res.calls = reads.calls
        res.coverage.update({"complete": complete, "rows_read": len(rows)})
        return res

    return await _bounded(_run, query=name, source=source, object_type=object_type)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

FILE_SOURCES = ("google_drive", "microsoft365")
_FILE_ACTIONS = {
    "google_drive": ("google_drive.search_files", "google_drive.get_file_metadata"),
    "microsoft365": ("microsoft365.search_files", "microsoft365.get_file_metadata"),
}
_KIND_WORDS = {
    "spreadsheet": "spreadsheet",
    "sheet": "spreadsheet",
    "sheets": "spreadsheet",
    "excel": "spreadsheet",
    "workbook": "spreadsheet",
    "csv": "spreadsheet",
    "doc": "document",
    "docs": "document",
    "document": "document",
    "deck": "presentation",
    "slides": "presentation",
    "presentation": "presentation",
    "pdf": "pdf",
    "file": "",
    "attachment": "",
}
_KIND_MIME = {
    "spreadsheet": ("spreadsheet", "excel", "csv", ".sheet"),
    "document": ("document", "word", "msword"),
    "presentation": ("presentation", "powerpoint"),
    "pdf": ("pdf",),
}
_KIND_EXT = {
    "spreadsheet": (".xlsx", ".xls", ".csv", ".ods"),
    "document": (".docx", ".doc", ".odt"),
    "presentation": (".pptx", ".ppt", ".key"),
    "pdf": (".pdf",),
}
_KIND_RE = "|".join(sorted(_KIND_WORDS, key=len, reverse=True))
_NAME = r"[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,2}"
_FILE_RES = (
    # "Send Stephanie the budget spreadsheet"
    re.compile(
        rf"\b(?:send|email|e-mail|forward|share)\s+{_NAME}\s+(?:the|my|our|this|that|a)\s+(?P<phrase>.+?)\s*[.!?]*$",
        re.IGNORECASE,
    ),
    # "Send the budget spreadsheet to Stephanie"
    re.compile(
        rf"\b(?:send|email|e-mail|forward)\s+(?:the|my|our|this|that|a)\s+(?P<phrase>.+?)\s+to\s+{_NAME}\b",
        re.IGNORECASE,
    ),
    # "... and attach the budget spreadsheet"
    re.compile(r"\b(?:attach|include|link(?:\s+to)?)\s+(?:the|my|our|this|that|a)\s+(?P<phrase>.+?)\s*[.!?]*$", re.IGNORECASE),
)


@dataclass(frozen=True)
class FileRequest:
    phrase: str  # "budget spreadsheet"
    query: str  # "budget"
    kind: str  # "spreadsheet", "document", ... or ""


def extract_file_request(message: str) -> FileRequest | None:
    """The file a send asks for ("the budget spreadsheet"), only when a file word says so."""
    text = (message or "").strip()
    for pattern in _FILE_RES:
        m = pattern.search(text)
        if not m:
            continue
        phrase = re.split(r"\s+(?:on|from|in|via|by)\s+(?:my\s+)?(?:gmail|outlook|e-?mail)\b", m.group("phrase"), flags=re.IGNORECASE)[0]
        phrase = phrase.strip(" .!?,")
        words = phrase.split()
        kind_words = [w for w in words if w.lower() in _KIND_WORDS]
        if not kind_words:
            continue
        kind = next((_KIND_WORDS[w.lower()] for w in kind_words if _KIND_WORDS[w.lower()]), "")
        query = " ".join(w for w in words if w.lower() not in _KIND_WORDS).strip()
        if not query or query.lower() in {"email", "message", "note"}:
            continue
        return FileRequest(phrase=phrase, query=query, kind=kind)
    return None


def _kind_fits(kind: str, name: str, mime: str) -> bool:
    if not kind:
        return True
    low_mime = (mime or "").lower()
    if any(part in low_mime for part in _KIND_MIME.get(kind, ())):
        return True
    return (name or "").lower().endswith(_KIND_EXT.get(kind, ()))


def _modified_label(raw: str) -> str:
    value = (raw or "")[:10]
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not m:
        return ""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{months[month - 1]} {day}, {year}" if 1 <= month <= 12 else ""


def _folder_of(path: str, name: str) -> str:
    text = (path or "").strip().rstrip("/")
    if not text or text == name:
        return ""
    if ":" in text:
        text = text.split(":", 1)[1]
    parts = [p for p in text.split("/") if p and p != name]
    return parts[-1] if parts else ""


async def resolve_file(
    request: FileRequest,
    *,
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> Resolution:
    """Files whose name matches the request, across connected Drive and OneDrive."""
    sources = [s for s in FILE_SOURCES if s in connected]
    if not sources:
        return unavailable(request.phrase, source="files", object_type="file", reason="not_connected")
    accounts = {s: connected_accounts(client, org_id, s) for s in sources}

    def _run() -> Resolution:
        reads = _Reads(org_id=org_id, client=client, settings=settings, user_id=user_id, conversation_id=conversation_id)
        now = time.time()
        cands: list[ResolutionCandidate] = []
        complete = True
        failures: list[str] = []
        scanned = 0
        for source in sources:
            account = (accounts.get(source) or [None])[0]
            pin = {"connector_id": account.id} if account else {}
            search_action, _meta = _FILE_ACTIONS[source]
            got = reads.run(search_action, {**pin, "query": request.query, "page_size": SEARCH_PAGE_SIZE})
            if not getattr(got, "success", False):
                failures.append(read_failure_reason(getattr(got, "error_code", None)))
                continue
            hits = [h for h in (_data(got).get("files") or []) if isinstance(h, dict)]
            scanned += len(hits)
            if len(hits) >= SEARCH_PAGE_SIZE:
                complete = False  # a full page: more may match
            for hit in hits:
                title = str(hit.get("name") or "")
                if not name_matches(request.query, title):
                    continue  # matched on content only; the user named a title
                if not _kind_fits(request.kind, title, str(hit.get("mime_type") or "")):
                    continue
                file_id = str(hit.get("file_id") or "")
                if not file_id:
                    continue
                cands.append(
                    ResolutionCandidate(
                        name=title,
                        source=source,
                        account=account.id if account else str(getattr(got, "connector_id", "") or ""),
                        account_label=account.label if account else "",
                        account_stamp=account.stamp if account else "",
                        object_type="file",
                        object_id=file_id,
                        resolved_at=now,
                        evidence={
                            "mime_type": hit.get("mime_type") or "",
                            "modified_at": hit.get("modified_at") or "",
                            "modified_label": _modified_label(str(hit.get("modified_at") or "")),
                            "folder": _folder_of(str(hit.get("path") or ""), title),
                            "web_link": hit.get("web_link") or "",
                            "drive_id": hit.get("drive_id") or "",
                            "source_label": vendor_label("onedrive" if source == "microsoft365" else source),
                            "query": request.phrase,
                            "kind": request.kind,
                        },
                    )
                )
        if failures and len(failures) == len(sources):
            res = unavailable(request.phrase, source="files", object_type="file", reason=failures[0])
            res.calls = reads.calls
            return res
        if failures:
            complete = False
        cands.sort(key=lambda c: str(c.evidence.get("modified_at") or ""), reverse=True)
        res = decide(request.phrase, cands, complete=complete, source="files", object_type="file", reason="page_cap")
        res.calls = reads.calls
        res.coverage.update({"complete": complete, "rows_read": scanned, "sources": list(sources)})
        return res

    return await _bounded(_run, query=request.phrase, source="files", object_type="file")


def verify_file_access_sync(
    candidate: ResolutionCandidate,
    *,
    org_id: str,
    client: Any,
    settings: Any,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> tuple[ResolutionCandidate, int]:
    """Read the file's metadata with the account it was found in.

    Returns the candidate with ``access`` set ("ok" or "denied") and fresher
    metadata, and the number of reads made.
    """
    actions = _FILE_ACTIONS.get(candidate.source)
    if actions is None:
        return replace(candidate, access="denied"), 0
    reads = _Reads(org_id=org_id, client=client, settings=settings, user_id=user_id, conversation_id=conversation_id)
    params: dict[str, Any] = {"file_id": candidate.object_id}
    if candidate.account:
        params["connector_id"] = candidate.account
    if candidate.evidence.get("drive_id"):
        params["drive_id"] = candidate.evidence["drive_id"]
    try:
        got = reads.run(actions[1], params)
    except Exception as exc:  # noqa: BLE001
        logger.info("file_access_check_failed source=%s error=%s", candidate.source, type(exc).__name__)
        return replace(candidate, access="denied"), reads.calls
    if not getattr(got, "success", False):
        return replace(candidate, access="denied", evidence={**candidate.evidence, "denied": read_failure_reason(getattr(got, "error_code", None))}), reads.calls
    meta = _data(got).get("file") if isinstance(_data(got).get("file"), dict) else {}
    if meta.get("file_id") and str(meta.get("file_id")) != candidate.object_id:
        return replace(candidate, access="denied"), reads.calls
    evidence = dict(candidate.evidence)
    for key in ("web_link", "modified_at", "mime_type"):
        if meta.get(key):
            evidence[key] = meta[key]
    evidence["verified_at"] = time.time()
    return replace(candidate, access="ok", evidence=evidence), reads.calls


async def verify_file_access(candidate: ResolutionCandidate, **kwargs: Any) -> tuple[ResolutionCandidate, int]:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(verify_file_access_sync, candidate, **kwargs), timeout=OBJECT_LOOKUP_BUDGET_S
        )
    except Exception:  # noqa: BLE001
        return replace(candidate, access="denied"), 1


def file_labels(candidates: list[ResolutionCandidate]) -> list[str]:
    """Names, plus what tells same-named files apart (date, folder, source)."""
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.name.lower()] = counts.get(c.name.lower(), 0) + 1
    sources = {c.source for c in candidates}
    out = []
    for c in candidates:
        bits = []
        if counts[c.name.lower()] > 1:
            if c.evidence.get("folder"):
                bits.append(f"in {c.evidence['folder']}")
            if c.evidence.get("modified_label"):
                bits.append(f"modified {c.evidence['modified_label']}")
        if len(sources) > 1:
            bits.append(f"on {c.evidence.get('source_label') or vendor_label(c.source)}")
        out.append(f"{c.name} ({', '.join(bits)})" if bits else c.name)
    return out


def file_question(resolution: Resolution) -> str:
    phrase = resolution.query
    if resolution.status == "ambiguous":
        count = len(resolution.candidates)
        many = {2: "two", 3: "three", 4: "four"}.get(count, str(count))
        return f'I found {many} files that match "{phrase}": {join_or(file_labels(resolution.candidates))}. Which one?'
    if resolution.status == "incomplete" and resolution.candidates:
        only = resolution.candidates[0]
        return (
            f"The closest file I found is {only.name}, but I couldn't check all of your files, "
            "so there may be another. Is that the one?"
        )
    if resolution.status == "incomplete":
        return f'I couldn\'t find "{phrase}" among the files I could check. What is the file called?'
    if resolution.status == "not_found":
        return f'I couldn\'t find a file called "{phrase}" in your connected files. What is it called?'
    if resolution.status == "unavailable":
        if resolution.reason == "not_connected":
            return "I can't search your files from here yet, so I can't include it. Connect Google Drive or OneDrive to do that."
        if resolution.reason == "permission":
            return "I don't have permission to search your files right now, so I can't include it."
        return "I couldn't search your files just now, so I can't include it."
    return ""


# ---------------------------------------------------------------------------
# Carrying a file into a send, and checking it again before execution
# ---------------------------------------------------------------------------

FILE_ARG_KEYS = ("file_id", "file_source", "file_account", "file_name", "file_link")


def file_args(candidate: ResolutionCandidate) -> dict[str, str]:
    """What a staged send carries for a chosen file: its id, not just its title."""
    args = {
        "file_id": candidate.object_id,
        "file_source": candidate.source,
        "file_name": candidate.name,
        "file_link": str(candidate.evidence.get("web_link") or ""),
    }
    if candidate.account:
        args["file_account"] = candidate.account
    return {k: v for k, v in args.items() if v}


def body_with_file_link(body: str, params: dict[str, Any]) -> str:
    """The message body with the approved file's link appended (sends here cannot attach)."""
    link = str(params.get("file_link") or "").strip()
    if not link or link in body:
        return body
    name = str(params.get("file_name") or "File").strip()
    return f"{body.rstrip()}\n\n{name}: {link}"


def file_approval_line(args: dict[str, Any]) -> str:
    name = str(args.get("file_name") or "").strip()
    if not name or not args.get("file_id"):
        return ""
    where = vendor_label("onedrive" if args.get("file_source") == "microsoft365" else str(args.get("file_source") or ""))
    return f"{name} on {where}, added as a link (attachments aren't supported yet)"


def revalidate_bound_targets(ctx: Any, args: dict[str, Any]) -> str:
    """Right before an approved send runs: is the chosen file still readable?

    Returns "" when everything the send points at still checks out, or the
    sentence to show instead of sending. Reads only.
    """
    file_id = str((args or {}).get("file_id") or "").strip()
    if not file_id:
        return ""
    candidate = ResolutionCandidate(
        name=str(args.get("file_name") or "the file"),
        source=str(args.get("file_source") or ""),
        account=str(args.get("file_account") or ""),
        object_type="file",
        object_id=file_id,
    )
    checked, _calls = verify_file_access_sync(
        candidate,
        org_id=str(getattr(ctx, "org_id", "") or ""),
        client=getattr(ctx, "client", None),
        settings=getattr(ctx, "settings", None),
        user_id=str(getattr(ctx, "actor_id", "") or "") or None,
        conversation_id=getattr(ctx, "conversation_id", None),
    )
    if checked.access == "ok":
        return ""
    logger.info("send_target_revalidation_failed object_type=file source=%s", candidate.source)
    return (
        f"I can't open {candidate.name} with your {vendor_label('onedrive' if candidate.source == 'microsoft365' else candidate.source)} "
        "account anymore, so I didn't send the email. Nothing was sent."
    )
