"""Find the person a user means by name in their connected mailbox.

"Send an email to Stephanie" names a person, not an address. This module
looks for Stephanie among the people in the user's own mail, builds one
candidate per address, and returns a clear match, a short list to choose
from, nothing, or "I couldn't check everything". It never sends, changes or
approves anything, and it never searches the public web.

Which account is searched
    The Gmail (or Outlook) account the user named in the request, by its
    address; otherwise the account a send goes from by default (the most
    recently updated connected row, the same one ``get_connector_by_type``
    picks). Only that one account is searched, and the send is pinned to it
    (``connector_id``), so the address book and the sender always agree.
    Every candidate records the account row it came from.

How far the search goes
    A precise Gmail query (``from:/to:/cc:`` on the name, quoted when it has
    two words, promotions and social mail excluded), read in pages of
    ``PAGE_SIZE`` up to ``MAX_PAGES`` pages / ``MAX_MESSAGES`` messages and
    the ``LOOKUP_BUDGET_S`` time budget. Only the From, To, Cc, Date and
    list headers of each hit are read, never bodies. If the matches run out
    before a cap, the search is complete; if a cap or the budget stops it
    first, the status is ``incomplete`` and Gravitre asks instead of
    asserting a unique match.

Noise
    The user's own addresses, no-reply and role senders, list relays
    ("Stephanie via Team"), and senders seen only on newsletters, list mail
    or promotions never become candidates.

Drafts
    The Gmail connector has no ``drafts.list``. A draft is visible only when
    ``messages.list`` returns a DRAFT-labelled message that matches the
    query, so draft coverage is incidental and is not claimed. A draft shows
    an address was typed, never that a message was sent: an address seen
    only in drafts is offered for confirmation, never resolved on its own.

Freshness
    Candidates kept between turns carry when they were found and the account
    row's ``updated_at``. They are looked up again when older than
    ``CANDIDATE_TTL_S``, when the account was reconnected or removed, and
    they are dropped when a read fails for permission reasons.

A display name is a lead, not proof of identity: the approval prompt shows
the address, the user approves that address, and approval binding plus
write preflight check it again before anything is sent.
"""
from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from dataclasses import replace as _replace
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.services.object_resolution import (
    CANDIDATE_TTL_S,
    FILE_VERIFY_TTL_S,
    Account,
    FileRequest,
    MailRow,
    Resolution,
    ResolutionCandidate,
    ResolutionStatus,
    connected_accounts,
    decide,
    extract_file_request,
    file_args,
    file_question,
    is_fresh,
    join_or,
    name_matches,
    parse_addresses,
    participants_from_rows,
    pick_from,
    read_failure_reason,
    resolve_file,
    resolve_outlook_participant,
    select_account,
    stale_reason,
    tokens,
    unavailable,
    vendor_label,
    verify_file_access,
)

logger = get_logger(__name__)

# The shared contract, under the names the email flow has always used.
RecipientCandidate = ResolutionCandidate
RecipientResolution = Resolution

__all__ = [
    "CANDIDATES_KEY",
    "CANDIDATE_TTL_S",
    "FILE_KEY",
    "Grounding",
    "RecipientCandidate",
    "RecipientResolution",
    "ResolutionStatus",
    "apply_resolution_to_stage",
    "candidates_from_messages",
    "extract_recipient_name",
    "ground_email_recipient",
    "pick_candidate",
    "resolution_from_candidates",
    "resolution_question",
    "resolve_email_recipient",
    "stored_candidates",
]

# Gmail lookup bounds: pages of ids, messages whose headers are read, time.
PAGE_SIZE = 25
MAX_PAGES = 3
MAX_MESSAGES = 60
LOOKUP_BUDGET_S = 4.0
_HARD_TIMEOUT_S = LOOKUP_BUDGET_S + 1.5
_HEADERS = ("From", "To", "Cc", "Date", "List-Unsubscribe", "List-Id", "Precedence", "Auto-Submitted")
_BULK_LABELS = frozenset({"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS", "CATEGORY_UPDATES"})

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NAME = r"([A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,2})"
_NAME_CUE_RES = (
    re.compile(
        r"\b(?i:e-?mail|message|write\s+to|reply\s+to|send\s+(?:an?\s+)?(?:e-?mail|message|note|email)\s+to|"
        r"send\s+it\s+to|send\s+(?:this|that)\s+to|to)\s+" + _NAME
    ),
    # "Send Stephanie the budget spreadsheet", "send Stephanie an email"
    re.compile(r"\b(?i:send|forward)\s+" + _NAME + r"\s+(?i:the|an?|my|our|this|that)\b"),
)
# Capitalised words that are not people.
_NOT_A_NAME = frozenset(
    {
        "Gmail", "Outlook", "Google", "Microsoft", "Slack", "HubSpot", "Salesforce", "Me", "Myself",
        "Everyone", "All", "The", "My", "Our", "Them", "Him", "Her", "It", "This", "That", "Monday",
        "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Today", "Tomorrow",
        "Gravitre", "Team", "Support", "Sales", "Marketing", "I", "You", "We",
        # Replies that are not names ("Thanks!", "Sorry.", "Yes").
        "Thanks", "Thank", "Yes", "Yeah", "Yep", "No", "Nope", "Okay", "Ok", "Sorry", "Sure",
        "Great", "Cool", "Perfect", "Hi", "Hello", "Hey", "Please", "Wait", "Stop", "Cancel",
        "Actually", "Never", "Send", "Draft", "Email", "Subject", "Message", "Body", "Done",
        "Fine", "Good", "Nice", "Awesome", "Again", "Try", "Hold", "Later", "Now", "Both",
        "Correct", "Right", "Drive", "OneDrive",
    }
)
_BARE_NAME_RE = re.compile(r"^\s*(?:it'?s\s+|to\s+)?" + _NAME + r"\s*[.!]?\s*$")


# ---------------------------------------------------------------------------
# Reading the request
# ---------------------------------------------------------------------------


def extract_recipient_name(message: str, *, bare_ok: bool = False) -> str | None:
    """The person named as the recipient ("email Stephanie" -> "Stephanie").

    ``bare_ok`` accepts a reply that is only a name ("Stephanie Khan."),
    which is how people answer "Who should it go to?".
    """
    text = (message or "").strip()
    if not text or _EMAIL_RE.search(text):
        return None
    candidates: list[str] = []
    for pattern in _NAME_CUE_RES:
        candidates.extend(m.group(1) for m in pattern.finditer(text))
    if bare_ok:
        m = _BARE_NAME_RE.match(text)
        if m:
            candidates.append(m.group(1))
    for raw in candidates:
        words = [w for w in raw.split() if w not in _NOT_A_NAME]
        # Stop at a non-name word ("Stephanie On" from "to Stephanie On Gmail").
        name_words: list[str] = []
        for word in raw.split():
            if word in _NOT_A_NAME or word.lower() in {"on", "at", "in", "about", "with", "and"}:
                break
            name_words.append(word)
        if name_words and words:
            return " ".join(name_words)
    return None


def _name_matches(query: str, display: str, address: str) -> bool:
    return name_matches(query, display, address)


# ---------------------------------------------------------------------------
# Building candidates from message headers
# ---------------------------------------------------------------------------


def _header_map(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
    out: dict[str, str] = {}
    for row in payload.get("headers") or []:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"]).lower()] = str(row.get("value") or "")
    return out


def _is_bulk(headers: dict[str, str], labels: set[str]) -> bool:
    if labels & _BULK_LABELS:
        return True
    if headers.get("list-unsubscribe") or headers.get("list-id"):
        return True
    if headers.get("precedence", "").strip().lower() in {"bulk", "list", "junk"}:
        return True
    auto = headers.get("auto-submitted", "").strip().lower()
    return bool(auto) and auto != "no"


def gmail_rows(messages: list[dict[str, Any]]) -> list[MailRow]:
    rows: list[MailRow] = []
    for msg in messages:
        headers = _header_map(msg)
        labels = set(msg.get("labelIds") or [])
        kind = "draft" if "DRAFT" in labels else ("sent" if "SENT" in labels else "received")
        rows.append(
            MailRow(
                sender=parse_addresses(headers.get("from", "")),
                to=parse_addresses(headers.get("to", "")),
                cc=parse_addresses(headers.get("cc", "")),
                kind=kind,
                date=headers.get("date", ""),
                bulk=kind == "received" and _is_bulk(headers, labels),
            )
        )
    return rows


def candidates_from_messages(
    query: str,
    messages: list[dict[str, Any]],
    *,
    account: str | Account = "",
    own: set[str] | None = None,
    excluded: dict[str, int] | None = None,
) -> list[RecipientCandidate]:
    """One candidate per matching address, with how it was seen."""
    acct = account if isinstance(account, Account) else None
    cands, dropped = participants_from_rows(query, gmail_rows(messages), source="gmail", account=acct, own=own)
    if isinstance(account, str) and account:
        cands = [_replace(c, account=account) for c in cands]
    if excluded is not None:
        excluded.update(dropped)
    return cands


def resolution_from_candidates(
    query: str,
    candidates: list[RecipientCandidate],
    *,
    complete: bool = True,
    reason: str = "",
    source: str = "gmail",
) -> RecipientResolution:
    return decide(query, candidates, complete=complete, source=source, object_type="person", reason=reason)


# ---------------------------------------------------------------------------
# What Gravitre says
# ---------------------------------------------------------------------------


def _labels(candidates: list[RecipientCandidate]) -> list[str]:
    """Names, plus the domain only where two candidates share a name."""
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.name.lower()] = counts.get(c.name.lower(), 0) + 1
    labels: list[str] = []
    for c in candidates:
        if counts[c.name.lower()] > 1 or "@" in c.name:
            labels.append(f"{c.name} at {c.domain}" if "@" not in c.name else c.address)
        else:
            labels.append(c.name)
    return labels


_COUNT_WORDS = {2: "two", 3: "three", 4: "four"}


def _where(resolution: RecipientResolution) -> str:
    return vendor_label(resolution.source) if resolution.source in {"gmail", "microsoft365"} else "Gmail"


def resolution_question(resolution: RecipientResolution, *, still_needs_message: bool = True) -> str:
    query = resolution.query
    first = query.split()[0] if query.split() else query
    where = _where(resolution)
    if resolution.status == "resolved" and resolution.chosen is not None:
        found = (
            f"Got it, {resolution.chosen.name}."
            if resolution.source == "choice"
            else f"I found {resolution.chosen.name} in your {where} correspondence."
        )
        return f"{found} What would you like to say?" if still_needs_message else found
    if resolution.status == "ambiguous" and resolution.reason == "draft_only" and resolution.candidates:
        only = resolution.candidates[0]
        return (
            f"The only {query} I found is {only.address}, and only in an unsent draft, "
            "so I can't confirm it. Should I use that address?"
        )
    if resolution.status == "ambiguous":
        total = int(resolution.coverage.get("total_candidates") or len(resolution.candidates))
        shown = _join_or(_labels(resolution.candidates))
        if total > len(resolution.candidates):
            return f"I found {total} {first}s. The ones you write to most are {shown}. Which one, or what's the last name?"
        count = _COUNT_WORDS.get(len(resolution.candidates), str(len(resolution.candidates)))
        return f"I found {count} {first}s: {shown}. Which one?"
    if resolution.status == "incomplete" and resolution.candidates:
        only = resolution.candidates[0]
        return (
            f"I found {only.name} ({only.address}), but I couldn't check all of your mail, "
            f"so there may be another {first}. Is that who you mean?"
        )
    if resolution.status == "incomplete":
        return (
            f"I couldn't find {query} in the part of your {where} I could check. "
            "Do you have the email address, or another name I should look for?"
        )
    if resolution.status == "not_found":
        return (
            f"I couldn't find {query} in this mailbox. Is there another name I should "
            "look for, or do you have the email address?"
        )
    if resolution.status == "unavailable" and resolution.reason == "permission":
        return (
            f"I don't have permission to read your {where} right now (it may need reconnecting), "
            f"so I can't look up {query}. What's the email address?"
        )
    if resolution.status == "unavailable" and resolution.reason in {"error", "time_budget", "rate_limited"}:
        return f"I couldn't search your {where} just now, so I can't look up {query}. What's the email address?"
    return ""


def _join_or(items: list[str]) -> str:
    return join_or(items)


def pick_candidate(reply: str, candidates: list[RecipientCandidate]) -> RecipientCandidate | None:
    """The candidate a reply points at ("Khan", "the second one", an address, "yes")."""
    return pick_from(reply, candidates)


# ---------------------------------------------------------------------------
# The Gmail lookup
# ---------------------------------------------------------------------------


def gmail_query(name: str) -> str:
    """Participants named ``name``, without promotions or social mail."""
    quoted = f'"{name}"' if " " in name.strip() else name.strip()
    return f"(from:{quoted} OR to:{quoted} OR cc:{quoted}) -category:promotions -category:social"


# Kept for callers of the earlier name.
_gmail_query = gmail_query


@dataclass
class _Scan:
    messages: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False
    reason: str = ""
    pages: int = 0
    listed: int = 0
    calls: int = 0
    connector_id: str = ""


class _LookupFailed(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _scan_gmail_sync(
    name: str,
    *,
    account: Account | None,
    deadline: float,
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    task_state: dict[str, Any] | None,
    user_id: str | None,
    conversation_id: str | None,
) -> _Scan:
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
    from app.services.sealed_read_execution import (
        attributable_read_actor_id,
        invoke_sealed_f1_read,
    )
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    step = ExecutionStep(
        step_id="resolve_recipient",
        title="Find recipient in Gmail",
        kind="read",
        connector_id="gmail",
        capability_id="email.messages.read",
        action_key="gmail.messages.list",
    )
    plan = ExecutionPlan(
        plan_id=str(uuid4()),
        summary="Find recipient in Gmail",
        objective=f"Find {name} in Gmail",
        steps=[step],
        source="recipient_resolution",
        capability_id="email.messages.read",
    )
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=attributable_read_actor_id(user_id) or "recipient-resolution",
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
        conversation_id=conversation_id or None,
    )
    scan = _Scan()
    pin = {"connector_id": account.id} if account else {}
    ids: list[str] = []
    page_token = ""
    query = gmail_query(name)
    for page in range(MAX_PAGES):
        if time.monotonic() > deadline:
            scan.reason = "time_budget"
            break
        args: dict[str, Any] = {**pin, "q": query, "max_results": PAGE_SIZE}
        if page_token:
            args["page_token"] = page_token
        listed, _proof, _obs = invoke_sealed_f1_read(
            ctx=ctx,
            action_key="gmail.messages.list",
            user_message=f"Find {name} in Gmail",
            task_state=task_state or {},
            connected_integrations=connected,
            plan=plan,
            step=step,
            proposed_args=args,
            capability_id=plan.capability_id,
        )
        scan.calls += 1
        if not listed.success:
            if page == 0:
                raise _LookupFailed(str(listed.error_code or "gmail_list_failed"))
            scan.reason = "page_failed"
            break
        scan.pages += 1
        scan.connector_id = scan.connector_id or str(getattr(listed, "connector_id", "") or "")
        data = listed.data if isinstance(listed.data, dict) else {}
        for row in data.get("messages") or []:
            if isinstance(row, dict) and row.get("id") and str(row["id"]) not in ids:
                ids.append(str(row["id"]))
        page_token = str(data.get("nextPageToken") or "")
        if not page_token:
            scan.complete = True
            break
        if len(ids) >= MAX_MESSAGES:
            scan.reason = "message_cap"
            break
    else:
        scan.reason = "page_cap"
    scan.listed = len(ids)
    if len(ids) > MAX_MESSAGES:
        ids = ids[:MAX_MESSAGES]
        scan.complete = False
        scan.reason = scan.reason or "message_cap"

    get_ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=ctx.actor_id,
        environment_name="production",
        conversation_id=conversation_id or None,
    )
    get_pin = {"connector_id": account.id} if account else (
        {"connector_id": scan.connector_id} if scan.connector_id else {}
    )

    def _headers_of(message_id: str) -> dict[str, Any] | None:
        got = invoke_tool(
            get_ctx,
            "gmail.messages.get",
            {**get_pin, "message_id": message_id, "format": "metadata", "metadata_headers": list(_HEADERS)},
        )
        body = got.data if got.success and isinstance(got.data, dict) else {}
        message = body.get("message") if isinstance(body.get("message"), dict) else body
        return message if isinstance(message, dict) and message else None

    # Headers only, fetched side by side, inside what is left of the budget.
    pool = ThreadPoolExecutor(max_workers=6)
    try:
        futures = [pool.submit(_headers_of, mid) for mid in ids]
        scan.calls += len(futures)
        done, not_done = wait(futures, timeout=max(0.0, deadline - time.monotonic()))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    fetched = [f.result() for f in futures if f in done and f.exception() is None]
    scan.messages = [m for m in fetched if m]
    if not_done or len(scan.messages) < len(ids):
        scan.complete = False
        scan.reason = scan.reason or ("time_budget" if not_done else "header_read_failed")
    return scan


async def resolve_email_recipient(
    name: str,
    *,
    org_id: str,
    client: Any,
    settings: Any,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
    account: Account | None = None,
) -> RecipientResolution:
    """Look the name up in one connected Gmail account. Read-only; never raises."""
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    if "gmail" not in connected or not name.strip():
        return unavailable(name, source="gmail", object_type="person", reason="not_connected")
    started = time.perf_counter()
    deadline = time.monotonic() + LOOKUP_BUDGET_S
    try:
        scan = await asyncio.wait_for(
            asyncio.to_thread(
                _scan_gmail_sync,
                name,
                account=account,
                deadline=deadline,
                org_id=org_id,
                client=client,
                settings=settings,
                connected=connected,
                task_state=task_state,
                user_id=user_id,
                conversation_id=conversation_id,
            ),
            timeout=_HARD_TIMEOUT_S,
        )
    except _LookupFailed as exc:
        reason = read_failure_reason(exc.code)
        logger.info("recipient_resolution_unavailable source=gmail reason=%s", reason)
        res = unavailable(name, source="gmail", object_type="person", reason=reason)
        res.latency_ms = int((time.perf_counter() - started) * 1000)
        res.calls = 1
        return res
    except Exception as exc:  # noqa: BLE001
        logger.info("recipient_resolution_unavailable source=gmail error=%s", type(exc).__name__)
        res = unavailable(
            name,
            source="gmail",
            object_type="person",
            reason="time_budget" if isinstance(exc, TimeoutError) else "error",
        )
        res.latency_ms = int((time.perf_counter() - started) * 1000)
        return res
    acct = account
    if acct is None and scan.connector_id:
        acct = Account(id=scan.connector_id, vendor="gmail", label="")
    excluded: dict[str, int] = {}
    cands = candidates_from_messages(name, scan.messages, account=acct or "", excluded=excluded)
    resolution = resolution_from_candidates(name, cands, complete=scan.complete, reason=scan.reason)
    resolution.latency_ms = int((time.perf_counter() - started) * 1000)
    resolution.calls = scan.calls
    resolution.accounts = [account.label] if account else []
    resolution.coverage.update(
        {
            "complete": scan.complete,
            "reason": scan.reason,
            "pages": scan.pages,
            "messages_listed": scan.listed,
            "messages_read": len(scan.messages),
            "excluded": excluded,
            "drafts": "incidental",
        }
    )
    logger.info(
        "recipient_resolution status=%s reason=%s candidates=%d pages=%d messages=%d calls=%d latency_ms=%d",
        resolution.status,
        resolution.reason,
        len(resolution.candidates),
        scan.pages,
        len(scan.messages),
        scan.calls,
        resolution.latency_ms,
    )
    return resolution


# ---------------------------------------------------------------------------
# Staging: shared by the chat connector turn and the ReAct write gate
# ---------------------------------------------------------------------------

# Email sends that look a recipient up, and the mailbox each one searches.
_EMAIL_SENDS = {"gmail.messages.send": "gmail", "microsoft365.mail.send": "microsoft365"}
CANDIDATES_KEY = "recipient_candidates"
# The file a send carries: {"query", "kind", "status", "candidates", "chosen"}.
FILE_KEY = "file_resolution"

_SKIP_FILE_RE = re.compile(r"(?i)\b(?:without (?:it|the file|an? attachment)|skip (?:it|the file)|no file|leave it out|never ?mind the file)\b")


@dataclass
class Grounding:
    """What one turn's lookups found for an email send."""

    recipient: Resolution | None = None
    file: Resolution | None = None
    # The value to store under ``FILE_KEY`` (None leaves it as it was).
    file_state: dict[str, Any] | None = None
    # A sentence to say before the approval prompt (e.g. a file left out).
    notice: str = ""

    @property
    def status(self) -> str:
        if self.recipient is not None:
            return self.recipient.status
        if self.file is not None:
            return self.file.status
        return "unavailable"

    @property
    def calls(self) -> int:
        return (self.recipient.calls if self.recipient else 0) + (self.file.calls if self.file else 0)


def _known_addresses(message: str, task_state: dict[str, Any] | None) -> set[str]:
    """Addresses the user typed or confirmed: the only ones a write may use as given."""
    from app.services.parameter_ledger import get_ledger

    state = task_state if isinstance(task_state, dict) else {}
    texts = [message or "", *[str(m) for m in (state.get("recent_user_messages") or [])]]
    found = {e.lower() for text in texts for e in _EMAIL_RE.findall(text)}
    for slot in get_ledger(state).slots.values():
        found.update(e.lower() for e in _EMAIL_RE.findall(str(getattr(slot, "value", "") or "")))
    found.update(c.address.lower() for c in stored_candidates(state))
    return found


def _collecting(state: dict[str, Any]) -> bool:
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    return str(pending.get("status") or "") == "awaiting_params"


def stored_candidates(task_state: dict[str, Any] | None) -> list[RecipientCandidate]:
    """Candidates offered for the email still collecting its details.

    Kept beside the pending task rather than inside it: resuming a draft
    rebuilds ``pending_task`` from the ledger. Freshness is checked by the
    caller (``stale_reason``), which knows the connected accounts.
    """
    state = task_state if isinstance(task_state, dict) else {}
    if not _collecting(state):
        return []
    out = [RecipientCandidate.from_dict(raw) for raw in (state.get(CANDIDATES_KEY) or [])]
    return [c for c in out if c is not None]


def stored_file_state(task_state: dict[str, Any] | None) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    raw = state.get(FILE_KEY)
    if not isinstance(raw, dict) or not raw or not _collecting(state):
        return {}
    return dict(raw)


def open_choice_candidates(task_state: dict[str, Any] | None) -> list[ResolutionCandidate]:
    """Whatever Gravitre last asked the user to choose between, person or file."""
    people = stored_candidates(task_state)
    if people:
        return people
    fstate = stored_file_state(task_state)
    if fstate.get("chosen"):
        return []
    files = [ResolutionCandidate.from_dict(raw) for raw in (fstate.get("candidates") or [])]
    return [c for c in files if c is not None]


def reply_answers_open_choice(message: str, task_state: dict[str, Any] | None) -> bool:
    """True when a reply picks one of the offered people or files (so it is not a subject)."""
    return pick_from(message, open_choice_candidates(task_state)) is not None


def _strip_account_addresses(message: str, accounts: list[Account]) -> str:
    text = message or ""
    for account in accounts:
        for email in account.emails:
            text = re.sub(rf"(?i)\s*(?:from|on|using|with)?\s*(?:my\s+)?{re.escape(email)}", "", text)
    return text


async def _lookup(
    vendor: str,
    name: str,
    *,
    account: Account | None,
    message: str,
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    task_state: dict[str, Any] | None,
    user_id: str | None,
    conversation_id: str | None,
) -> Resolution:
    if vendor == "microsoft365":
        return await resolve_outlook_participant(
            name,
            org_id=org_id,
            client=client,
            settings=settings,
            connected=connected,
            message=message,
            user_id=user_id,
            conversation_id=conversation_id,
        )
    return await resolve_email_recipient(
        name,
        org_id=org_id,
        client=client,
        settings=settings,
        connected_integrations=connected,
        task_state=task_state,
        user_id=user_id,
        conversation_id=conversation_id,
        account=account,
    )


def _choice(picked: ResolutionCandidate, *, object_type: str = "person") -> Resolution:
    return Resolution(status="resolved", query=picked.name, candidates=[picked], source="choice", object_type=object_type)


async def _ground_recipient(
    vendor: str,
    args: dict[str, Any],
    message: str,
    task_state: dict[str, Any] | None,
    *,
    accounts: list[Account],
    account: Account | None,
    how: str,
    lookup_kwargs: dict[str, Any],
) -> Resolution | None:
    state = task_state if isinstance(task_state, dict) else {}
    current = str(args.get("to") or "").strip()
    known = _known_addresses(message, task_state)
    if current and current.lower() in known:
        if account is not None and how == "named":
            args.setdefault("connector_id", account.id)
        return None

    def _settle(picked: ResolutionCandidate) -> None:
        args["to"] = picked.address
        if picked.account and accounts:
            # Send from the mailbox that was searched (Gmail or Outlook).
            args["connector_id"] = picked.account

    stored = stored_candidates(task_state)
    if not current and stored:
        fresh = [c for c in stored if not stale_reason(c, accounts or None)]
        if fresh and len(fresh) == len(stored):
            picked = pick_from(message, fresh)
            if picked is not None:
                _settle(picked)
                return _choice(picked)
        else:
            # Found too long ago, or the account changed since: look again
            # before using any of them.
            why = next((stale_reason(c, accounts or None) for c in stored if stale_reason(c, accounts or None)), "")
            query = str(stored[0].evidence.get("query") or stored[0].name)
            logger.info("recipient_candidates_revalidated reason=%s", why)
            again = await _lookup(vendor, query, account=account, **lookup_kwargs)
            if again.status == "resolved" and again.chosen is not None or again.candidates:
                picked = pick_from(message, again.candidates)
                if picked is not None:
                    _settle(picked)
                    return _choice(picked)
            again.reason = again.reason or f"revalidated:{why}"
            if again.status != "unavailable":
                return again

    name = extract_recipient_name(_strip_account_addresses(message, accounts), bare_ok=not current)
    if name is None and current:
        # The model filled an address the user never gave; look for the
        # person the conversation named instead.
        for earlier in reversed(list(state.get("recent_user_messages") or [])[-3:]):
            name = extract_recipient_name(str(earlier))
            if name:
                break
    if name is None:
        return None
    resolution = await _lookup(vendor, name, account=account, **lookup_kwargs)
    if resolution.status == "resolved" and resolution.chosen is not None:
        if current and current.lower() != resolution.chosen.address.lower():
            logger.info("recipient_model_address_replaced source=%s", vendor)
        _settle(resolution.chosen)
        return resolution
    if current:
        # Never send to an address nobody typed and the mailbox can't back up.
        logger.info("recipient_model_address_dropped status=%s", resolution.status)
    args.pop("to", None)
    args.pop("email", None)
    return resolution


def _file_needs_verify(chosen: ResolutionCandidate) -> bool:
    try:
        verified = float(chosen.evidence.get("verified_at") or 0.0)
    except (TypeError, ValueError):
        verified = 0.0
    return chosen.access != "ok" or (time.time() - verified) > FILE_VERIFY_TTL_S


def _send_complete(args: dict[str, Any]) -> bool:
    return all(str(args.get(k) or "").strip() for k in ("to", "subject")) and bool(
        str(args.get("body") or args.get("text") or args.get("message") or "").strip()
    )


async def _ground_file(
    args: dict[str, Any],
    message: str,
    task_state: dict[str, Any] | None,
    *,
    grounding: Grounding,
    lookup_kwargs: dict[str, Any],
) -> None:
    """Find, confirm and check the file a send carries; put its id in the args."""
    fstate = stored_file_state(task_state)
    request = extract_file_request(message)
    file_kwargs = {k: lookup_kwargs[k] for k in ("org_id", "client", "settings", "user_id", "conversation_id")}
    connected = list(lookup_kwargs["connected"])
    if not any(s in connected for s in ("google_drive", "microsoft365")):
        try:
            from app.connectors.connector_availability_service import (
                list_executable_integrations,
            )

            connected += [
                str(v).lower()
                for v in list_executable_integrations(file_kwargs["client"], file_kwargs["org_id"], file_kwargs["settings"])
            ]
        except Exception as exc:  # noqa: BLE001
            logger.info("file_sources_unreadable error=%s", type(exc).__name__)

    async def _choose(candidate: ResolutionCandidate, *, via_choice: bool) -> None:
        checked, calls = await verify_file_access(candidate, **file_kwargs)
        if checked.access != "ok":
            res = unavailable(candidate.name, source="files", object_type="file", reason="permission")
            res.calls = calls
            grounding.file = res
            grounding.file_state = {"status": "unavailable", "reason": "permission", "query": candidate.name}
            for key in ("file_id", "file_source", "file_account", "file_name", "file_link"):
                args.pop(key, None)
            return
        args.update(file_args(checked))
        res = Resolution(
            status="resolved",
            query=candidate.name,
            candidates=[checked],
            source="choice" if via_choice else "files",
            object_type="file",
        )
        res.calls = calls
        grounding.file = res
        grounding.file_state = {"status": "resolved", "query": candidate.evidence.get("query") or candidate.name, "chosen": checked.to_dict()}

    async def _search(req: FileRequest) -> None:
        res = await resolve_file(req, connected=connected, **file_kwargs)
        if res.status == "resolved" and res.chosen is not None:
            searched = res.calls
            await _choose(res.chosen, via_choice=False)
            if grounding.file is not None:
                grounding.file.calls += searched
            return
        grounding.file = res
        grounding.file_state = {
            "status": res.status,
            "reason": res.reason,
            "query": req.phrase,
            "search": req.query,
            "kind": req.kind,
            "candidates": [c.to_dict() for c in res.candidates],
        }

    if request is not None and request.phrase != fstate.get("query"):
        await _search(request)
        return
    if not fstate:
        return
    status = str(fstate.get("status") or "")
    if status in {"unavailable", "skipped"}:
        return
    chosen = ResolutionCandidate.from_dict(fstate.get("chosen")) if fstate.get("chosen") else None
    if chosen is not None:
        if _send_complete(args) and _file_needs_verify(chosen):
            # About to show the approval prompt: the file must still open.
            checked, _calls = await verify_file_access(chosen, **file_kwargs)
            if checked.access != "ok":
                for key in ("file_id", "file_source", "file_account", "file_name", "file_link"):
                    args.pop(key, None)
                grounding.file_state = {"status": "unavailable", "reason": "permission", "query": chosen.name}
                grounding.notice = f"I can't open {chosen.name} anymore, so I've left it out of the email."
                return
            chosen = checked
            grounding.file_state = {**fstate, "chosen": checked.to_dict()}
        args.update({k: v for k, v in file_args(chosen).items() if not args.get(k)})
        return
    if _SKIP_FILE_RE.search(message or ""):
        grounding.file_state = {"status": "skipped", "query": fstate.get("query") or ""}
        return
    offered = [c for c in (ResolutionCandidate.from_dict(raw) for raw in (fstate.get("candidates") or [])) if c]
    if offered:
        if not all(is_fresh(c, ttl_s=CANDIDATE_TTL_S) for c in offered):
            # Offered too long ago: search again, then take the reply.
            phrase = str(fstate.get("query") or "")
            req = FileRequest(phrase=phrase, query=str(fstate.get("search") or phrase), kind=str(fstate.get("kind") or ""))
            res = await resolve_file(req, connected=connected, **file_kwargs)
            offered = res.candidates
        picked = pick_from(message, offered)
        if picked is not None:
            await _choose(picked, via_choice=True)
        elif offered:
            # Not answered yet (it may have waited behind the recipient
            # question): ask it now.
            grounding.file = Resolution(
                status=status if status in _OPEN_QUESTION else "ambiguous",
                query=str(fstate.get("query") or ""),
                candidates=offered,
                source="files",
                object_type="file",
            )
            grounding.file_state = {**fstate, "candidates": [c.to_dict() for c in offered]}
        return
    if status in {"not_found", "incomplete"}:
        # "What is it called?" answered with a title.
        reply = (message or "").strip().strip(".!?")
        if reply and len(reply.split()) <= 6 and not _EMAIL_RE.search(reply):
            kind = str(fstate.get("kind") or "")
            words = [w for w in reply.split() if w.lower() not in {"it's", "its", "called", "the", "it", "is"}]
            if words:
                await _search(FileRequest(phrase=" ".join(words), query=" ".join(words), kind=kind))


async def ground_email_recipient(
    plan: Any,
    message: str,
    task_state: dict[str, Any] | None,
    *,
    org_id: str,
    client: Any,
    settings: Any,
    connected_integrations: list[str] | None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> tuple[Any, Grounding | None]:
    """Fill or check an email's recipient (and any file it carries) from the user's own accounts.

    Returns the plan (recipient set, cleared or untouched; file id added or
    not) and what the lookups found, if any ran. A recipient the user never
    typed and the mailbox cannot back up is cleared, so the turn asks instead
    of sending to a guessed address.
    """
    invoke = str(getattr(plan, "invoke_action", "") or "")
    vendor = _EMAIL_SENDS.get(invoke)
    if vendor is None:
        return plan, None
    args = dict(getattr(plan, "args", None) or {})
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    accounts = connected_accounts(client, org_id, vendor) if vendor in connected else []
    account, how = select_account(accounts, message)
    lookup_kwargs = {
        "message": message,
        "org_id": org_id,
        "client": client,
        "settings": settings,
        "connected": connected,
        "task_state": task_state,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }
    grounding = Grounding()
    grounding.recipient = await _ground_recipient(
        vendor,
        args,
        message,
        task_state,
        accounts=accounts,
        account=account,
        how=how,
        lookup_kwargs=lookup_kwargs,
    )
    await _ground_file(args, message, task_state, grounding=grounding, lookup_kwargs=lookup_kwargs)
    if grounding.recipient is None and grounding.file is None and grounding.file_state is None and not grounding.notice:
        if args != dict(getattr(plan, "args", None) or {}):
            return _replace(plan, args=args), None
        return plan, None
    return _replace(plan, args=args), grounding


_OPEN_QUESTION = frozenset({"ambiguous", "not_found", "incomplete"})


def _file_line(res: Resolution) -> tuple[str, bool]:
    """What to say about the file, and whether it is a question."""
    if res.status == "resolved" and res.chosen is not None:
        chosen = res.chosen
        where = chosen.evidence.get("source_label") or vendor_label(chosen.source)
        lead = f"Got it, {chosen.name}." if res.source == "choice" else f"I found {chosen.name} on {where}."
        line = (
            f"{lead} I can't attach files to emails from here yet, so I'll add a link to it; "
            "the recipient needs access to open it."
        )
        return line, False
    text = file_question(res)
    return text, res.status in _OPEN_QUESTION


def apply_resolution_to_stage(
    staged: tuple[Any, dict[str, Any]] | None,
    resolution: Grounding | Resolution | None,
) -> tuple[Any, dict[str, Any]] | None:
    """Say what the lookups found, and keep what the next reply may choose from.

    At most one question per turn: an open question about the recipient comes
    first; the file's question waits for the next turn.
    """
    if staged is None or resolution is None:
        return staged
    grounding = resolution if isinstance(resolution, Grounding) else Grounding(recipient=resolution)
    clarification, patch = staged
    patch = dict(patch)
    pending = patch.get("pending_task") if isinstance(patch.get("pending_task"), dict) else {}
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    args = params.get("args") if isinstance(params.get("args"), dict) else {}
    needs_message = not str(args.get("body") or args.get("message") or "").strip()
    parts: list[str] = []
    asked = False
    rec = grounding.recipient
    if rec is not None:
        if rec.status == "resolved":
            parts.append(resolution_question(rec, still_needs_message=False))
            patch[CANDIDATES_KEY] = []
        elif rec.status == "unavailable":
            patch[CANDIDATES_KEY] = []
            line = resolution_question(rec)
            if line:
                parts.append(line)
                asked = True
        else:
            patch[CANDIDATES_KEY] = [c.to_dict() for c in rec.candidates]
            parts.append(resolution_question(rec))
            asked = True
    if grounding.file_state is not None:
        patch[FILE_KEY] = grounding.file_state
    if grounding.file is not None:
        line, is_question = _file_line(grounding.file)
        if is_question and asked:
            pass  # one question per turn; this one is kept for the next reply
        elif line:
            parts.append(line)
            asked = asked or is_question
    if grounding.notice:
        parts.append(grounding.notice)
    if not parts:
        return clarification, patch
    if not asked:
        parts.append("What would you like to say?" if needs_message else str(clarification.message or "").strip())
    text = " ".join(p for p in parts if p).strip()
    return _replace(clarification, message=text), patch


def approval_notice(grounding: Grounding | Resolution | None) -> str | None:
    """A sentence to put before the approval prompt, if the lookups left one."""
    if isinstance(grounding, Grounding):
        notice = grounding.notice
        if not notice and grounding.file is not None and grounding.file.status == "unavailable":
            notice = file_question(grounding.file)
        return notice or None
    return None


# Re-exported for callers that only import this module.
__all__ += ["approval_notice", "open_choice_candidates", "reply_answers_open_choice", "tokens"]
