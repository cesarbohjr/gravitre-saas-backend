"""Find the person a user means by name in their connected mailbox.

"Send an email to Stephanie" names a person, not an address. This module
looks for Stephanie among the people in the user's own Gmail (senders,
recipients and drafts), builds one candidate per address, and returns a
clear match, a short list to choose from, or nothing. It never sends,
changes or approves anything, and it never searches the public web.

A display name is a lead, not proof of identity: the address is what the
approval prompt shows, and the user approves that address. A draft shows an
address was typed, never that a message was sent.
"""
from __future__ import annotations

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from email.utils import getaddresses
from typing import Any, Literal
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

ResolutionStatus = Literal["resolved", "ambiguous", "not_found", "unavailable"]

# Messages whose headers are read per lookup, and the whole lookup's budget.
MAX_MESSAGES = 12
LOOKUP_BUDGET_S = 4.0
_HEADERS = ("From", "To", "Cc", "Date")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NAME = r"([A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,2})"
_NAME_CUE_RES = (
    re.compile(
        r"\b(?i:e-?mail|message|write\s+to|reply\s+to|send\s+(?:an?\s+)?(?:e-?mail|message|note|email)\s+to|"
        r"send\s+it\s+to|send\s+(?:this|that)\s+to|to)\s+" + _NAME
    ),
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
    }
)
_BARE_NAME_RE = re.compile(r"^\s*(?:it'?s\s+|to\s+)?" + _NAME + r"\s*[.!]?\s*$")


@dataclass(frozen=True)
class RecipientCandidate:
    name: str
    address: str
    source: str
    account: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def domain(self) -> str:
        return self.address.rsplit("@", 1)[-1].lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "source": self.source,
            "account": self.account,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> RecipientCandidate | None:
        if not isinstance(raw, dict) or not raw.get("address"):
            return None
        evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
        return cls(
            name=str(raw.get("name") or ""),
            address=str(raw.get("address") or ""),
            source=str(raw.get("source") or ""),
            account=str(raw.get("account") or ""),
            evidence=dict(evidence),
        )


@dataclass
class RecipientResolution:
    status: ResolutionStatus
    query: str
    candidates: list[RecipientCandidate] = field(default_factory=list)
    source: str = "gmail"
    latency_ms: int = 0

    @property
    def chosen(self) -> RecipientCandidate | None:
        return self.candidates[0] if self.status == "resolved" and self.candidates else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "query": self.query,
            "source": self.source,
            "candidates": [c.to_dict() for c in self.candidates],
            "latency_ms": self.latency_ms,
        }


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


def _tokens(value: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (value or "").lower()) if t]


def _name_matches(query: str, display: str, address: str) -> bool:
    """Every word of the query starts a word of the display name or address."""
    want = _tokens(query)
    if not want:
        return False
    have = _tokens(display) + _tokens(address.split("@", 1)[0])
    return all(any(h == w or (len(w) >= 3 and h.startswith(w)) for h in have) for w in want)


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


def candidates_from_messages(
    query: str,
    messages: list[dict[str, Any]],
    *,
    account: str = "",
) -> list[RecipientCandidate]:
    """One candidate per matching address, with how it was seen."""
    own: set[str] = set()
    for msg in messages:
        labels = set(msg.get("labelIds") or [])
        if labels & {"SENT", "DRAFT"}:
            for _name, addr in getaddresses([_header_map(msg).get("from", "")]):
                if addr:
                    own.add(addr.lower())
    seen: dict[str, dict[str, Any]] = {}
    for msg in messages:
        headers = _header_map(msg)
        labels = set(msg.get("labelIds") or [])
        kind = "draft" if "DRAFT" in labels else ("sent" if "SENT" in labels else "received")
        for header in ("from", "to", "cc"):
            for display, addr in getaddresses([headers.get(header, "")]):
                addr = (addr or "").strip()
                if not addr or "@" not in addr or addr.lower() in own:
                    continue
                if not _name_matches(query, display, addr):
                    continue
                row = seen.setdefault(
                    addr.lower(),
                    {"address": addr, "names": {}, "sent": 0, "received": 0, "draft": 0, "last_seen": ""},
                )
                if display:
                    row["names"][display] = row["names"].get(display, 0) + 1
                row[kind] += 1
                date = headers.get("date", "")
                if date and not row["last_seen"]:
                    row["last_seen"] = date
    out: list[RecipientCandidate] = []
    for row in seen.values():
        names = row["names"]
        name = max(names, key=names.get) if names else row["address"].split("@", 1)[0]
        out.append(
            RecipientCandidate(
                name=name,
                address=row["address"],
                source="gmail",
                account=account,
                evidence={
                    "sent": row["sent"],
                    "received": row["received"],
                    "draft": row["draft"],
                    "last_seen": row["last_seen"],
                },
            )
        )
    # Real correspondence first; an address only ever typed into a draft last.
    out.sort(
        key=lambda c: (
            -(c.evidence.get("sent", 0) + c.evidence.get("received", 0)),
            -c.evidence.get("draft", 0),
        )
    )
    return out


def resolution_from_candidates(query: str, candidates: list[RecipientCandidate]) -> RecipientResolution:
    if not candidates:
        return RecipientResolution(status="not_found", query=query)
    if len(candidates) == 1:
        return RecipientResolution(status="resolved", query=query, candidates=candidates)
    return RecipientResolution(status="ambiguous", query=query, candidates=candidates[:4])


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


def _join_or(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


_COUNT_WORDS = {2: "two", 3: "three", 4: "four"}


def resolution_question(resolution: RecipientResolution, *, still_needs_message: bool = True) -> str:
    query = resolution.query
    if resolution.status == "resolved" and resolution.chosen is not None:
        found = (
            f"Got it, {resolution.chosen.name}."
            if resolution.source == "choice"
            else f"I found {resolution.chosen.name} in your Gmail correspondence."
        )
        return f"{found} What would you like to say?" if still_needs_message else found
    if resolution.status == "ambiguous":
        first = query.split()[0]
        count = _COUNT_WORDS.get(len(resolution.candidates), str(len(resolution.candidates)))
        return f"I found {count} {first}s: {_join_or(_labels(resolution.candidates))}. Which one?"
    if resolution.status == "not_found":
        return (
            f"I couldn't find {query} in this mailbox. Is there another name I should "
            "look for, or do you have the email address?"
        )
    return ""


def pick_candidate(reply: str, candidates: list[RecipientCandidate]) -> RecipientCandidate | None:
    """The candidate a reply points at ("Khan", "the second one", an address)."""
    text = (reply or "").strip()
    if not text or not candidates:
        return None
    emails = [e.lower() for e in _EMAIL_RE.findall(text)]
    if emails:
        return next((c for c in candidates if c.address.lower() in emails), None)
    ordinals = {"first": 0, "1st": 0, "one": 0, "second": 1, "2nd": 1, "two": 1, "third": 2, "3rd": 2, "last": -1}
    low = text.lower()
    m = re.search(r"\b(first|1st|second|2nd|third|3rd|last)\b", low)
    if m:
        idx = ordinals[m.group(1)]
        try:
            return candidates[idx]
        except IndexError:
            return None
    words = [w for w in _tokens(text) if w not in {"the", "one", "at", "please", "her", "him", "them", "its", "it", "s"}]
    if not words:
        return None
    hits = [
        c
        for c in candidates
        if all(w in _tokens(c.name) + _tokens(c.address.split("@", 1)[0]) + _tokens(c.domain) for w in words)
    ]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------------------
# The lookup
# ---------------------------------------------------------------------------


def _gmail_query(name: str) -> str:
    quoted = f'"{name}"' if " " in name else name
    return f"from:{quoted} OR to:{quoted} OR cc:{quoted}"


def _search_gmail_sync(
    name: str,
    *,
    org_id: str,
    client: Any,
    settings: Any,
    connected: list[str],
    task_state: dict[str, Any] | None,
    user_id: str | None,
    conversation_id: str | None,
) -> tuple[list[dict[str, Any]], str]:
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
    listed, proof, _obs = invoke_sealed_f1_read(
        ctx=ctx,
        action_key="gmail.messages.list",
        user_message=f"Find {name} in Gmail",
        task_state=task_state or {},
        connected_integrations=connected,
        plan=plan,
        step=step,
        proposed_args={"q": _gmail_query(name), "max_results": MAX_MESSAGES},
        capability_id=plan.capability_id,
    )
    if not listed.success:
        raise RuntimeError(listed.error_code or "gmail_list_failed")
    account = str((getattr(proof, "resource", None) or {}).get("name") or "")
    data = listed.data if isinstance(listed.data, dict) else {}
    ids = [str(row.get("id")) for row in (data.get("messages") or []) if isinstance(row, dict) and row.get("id")]
    get_ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=ctx.actor_id,
        environment_name="production",
        conversation_id=conversation_id or None,
    )
    def _headers_of(message_id: str) -> dict[str, Any] | None:
        got = invoke_tool(
            get_ctx,
            "gmail.messages.get",
            {"message_id": message_id, "format": "metadata", "metadata_headers": list(_HEADERS)},
        )
        body = got.data if got.success and isinstance(got.data, dict) else {}
        message = body.get("message") if isinstance(body.get("message"), dict) else body
        return message if isinstance(message, dict) else None

    # Headers only, fetched side by side: one round trip of latency, not twelve.
    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(_headers_of, ids[:MAX_MESSAGES]))
    return [m for m in fetched if m], account


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
) -> RecipientResolution:
    """Look the name up in the connected Gmail. Read-only; never raises."""
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    if "gmail" not in connected or not name.strip():
        return RecipientResolution(status="unavailable", query=name)
    started = time.perf_counter()
    try:
        messages, account = await asyncio.wait_for(
            asyncio.to_thread(
                _search_gmail_sync,
                name,
                org_id=org_id,
                client=client,
                settings=settings,
                connected=connected,
                task_state=task_state,
                user_id=user_id,
                conversation_id=conversation_id,
            ),
            timeout=LOOKUP_BUDGET_S,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("recipient_resolution_unavailable source=gmail error=%s", type(exc).__name__)
        return RecipientResolution(
            status="unavailable",
            query=name,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
    resolution = resolution_from_candidates(name, candidates_from_messages(name, messages, account=account))
    resolution.latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "recipient_resolution status=%s candidates=%d messages=%d latency_ms=%d",
        resolution.status,
        len(resolution.candidates),
        len(messages),
        resolution.latency_ms,
    )
    return resolution


# ---------------------------------------------------------------------------
# Staging: shared by the chat connector turn and the ReAct write gate
# ---------------------------------------------------------------------------

_EMAIL_SENDS = frozenset({"gmail.messages.send"})
CANDIDATES_KEY = "recipient_candidates"


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


def stored_candidates(task_state: dict[str, Any] | None) -> list[RecipientCandidate]:
    """Candidates offered for the email still collecting its details.

    Kept beside the pending task rather than inside it: resuming a draft
    rebuilds ``pending_task`` from the ledger.
    """
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    if str(pending.get("status") or "") != "awaiting_params":
        return []
    out = [RecipientCandidate.from_dict(raw) for raw in (state.get(CANDIDATES_KEY) or [])]
    return [c for c in out if c is not None]


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
) -> tuple[Any, RecipientResolution | None]:
    """Fill or check an email's recipient from the user's own mailbox.

    Returns the plan (recipient set, cleared or untouched) and the lookup, if
    one ran. A recipient the user never typed and the mailbox cannot back up
    is cleared, so the turn asks instead of sending to a guessed address.
    """
    from dataclasses import replace as _replace

    invoke = str(getattr(plan, "invoke_action", "") or "")
    if invoke not in _EMAIL_SENDS:
        return plan, None
    args = dict(getattr(plan, "args", None) or {})
    current = str(args.get("to") or "").strip()
    known = _known_addresses(message, task_state)
    if current and current.lower() in known:
        return plan, None

    candidates = stored_candidates(task_state)
    if not current and candidates:
        picked = pick_candidate(message, candidates)
        if picked is not None:
            args["to"] = picked.address
            return _replace(plan, args=args), RecipientResolution(
                status="resolved", query=picked.name, candidates=[picked], source="choice"
            )

    name = extract_recipient_name(message, bare_ok=not current)
    if name is None and current:
        # The model filled an address the user never gave; look for the
        # person the conversation named instead.
        state = task_state if isinstance(task_state, dict) else {}
        for earlier in reversed(list(state.get("recent_user_messages") or [])[-3:]):
            name = extract_recipient_name(str(earlier))
            if name:
                break
    if name is None:
        return plan, None
    resolution = await resolve_email_recipient(
        name,
        org_id=org_id,
        client=client,
        settings=settings,
        connected_integrations=connected_integrations,
        task_state=task_state,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if resolution.status == "unavailable":
        return plan, resolution
    if resolution.status == "resolved" and resolution.chosen is not None:
        if current and current.lower() != resolution.chosen.address.lower():
            logger.info("recipient_model_address_replaced source=gmail")
        args["to"] = resolution.chosen.address
    else:
        if current:
            logger.info("recipient_model_address_dropped status=%s", resolution.status)
        args.pop("to", None)
        args.pop("email", None)
    return _replace(plan, args=args), resolution


def apply_resolution_to_stage(
    staged: tuple[Any, dict[str, Any]] | None,
    resolution: RecipientResolution | None,
) -> tuple[Any, dict[str, Any]] | None:
    """Say what the lookup found, and keep the candidates for the next reply."""
    from dataclasses import replace as _replace

    if staged is None or resolution is None or resolution.status == "unavailable":
        return staged
    clarification, patch = staged
    patch = dict(patch)
    pending = patch.get("pending_task") if isinstance(patch.get("pending_task"), dict) else {}
    if resolution.status == "resolved":
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        args = params.get("args") if isinstance(params.get("args"), dict) else {}
        needs_message = not str(args.get("body") or args.get("message") or "").strip()
        found = resolution_question(resolution, still_needs_message=needs_message)
        text = found if needs_message else f"{found} {clarification.message}".strip()
        patch[CANDIDATES_KEY] = []
        return _replace(clarification, message=text), patch
    patch[CANDIDATES_KEY] = [c.to_dict() for c in resolution.candidates]
    return _replace(clarification, message=resolution_question(resolution)), patch
