"""Genuine, cancelable speculative LLM generation on probable-EOT.

Voice-SLO follow-up (2026-09-05) — the highest-value item flagged as "not
built" in docs/delivery/voice-slo-parallelism-standard-2026-09-05.md: Phase 1
previously only did READ-ONLY cache warming (speculative_prefetch.py) on
partial transcripts. This module adds the other half — a real, cancelable
CognitiveTurnKernel reasoning call started on Deepgram Flux's own
ProposedUserStoppedSpeakingFrame ("probably done") signal, whose output is
either:

  - adopted at confirmed end-of-turn, when the final transcript matches the
    text the speculative run was launched with (exact, normalized match —
    a deliberate, conservative scoping choice: a close-but-not-exact match
    falls back to a fresh call rather than risk answering a slightly
    different question to save time), or
  - discarded (cancelled), when the user kept talking and the probable-EOT
    was wrong, or the final transcript doesn't match.

Ownership split, so this module never needs to know about AgentIntelligence,
Pipecat frame types, or write-governance policy:

  - speculative_prefetch.py (SpeculativePrefetchProcessor) decides WHEN to
    start a run (on ProposedUserStoppedSpeakingFrame) and WHETHER it is safe
    to do so at all (never for write-shaped text — same conservative gate
    already used for read-only prefetch), and supplies the `runner` closure
    (a zero-arg callable returning intelligence.execute_task_streaming(...)
    with the current partial as `query`).
  - cognitive_llm.py (GravitreCognitiveLLMService) calls `adopt()` at
    confirmed end-of-turn and, on a hit, drains the run's buffered/live
    events instead of calling execute_task_streaming() again — the actual
    latency win: any tokens the speculative run already produced before
    confirmation arrive instantly instead of waiting for a fresh call.

Side effects, bounds and revisions (2026-10):

  - Every run executes inside a ``SpeculativeScope``
    (app.services.speculative_execution). Durable writes the brain makes while
    speculating (task state, active objective, memory, traces, audit rows) are
    deferred on the scope and replayed by ``commit()`` only when the run is
    adopted; a discarded run drops them. Connector WRITEs and approval staging
    or consumption are refused and mark the run blocked (never adoptable).
  - Bounds: an unadopted run is cancelled after ``timeout_s``. Its buffered
    output is capped (``max_buffered_chars`` / ``max_buffered_events``); past
    the cap the producer pauses until adoption or timeout. A run that cannot
    be adopted is cancelled the moment the confirmed turn arrives.
  - Counters (started / adopted / discarded / timeouts / blocked / buffer
    pauses / wasted seconds) live on the coordinator and are attached to each
    turn's voice_turn_trace record.
  - Behind ``voice_request_revisions_v1``: request revisions bound to the
    transcript, conversation id, pending-task, approval and context versions.
    Adoption requires every bound version to match and a stricter transcript
    check (``strict_transcript_match``) that rejects trailing qualifiers,
    negations and corrections.

Task creation is handled by the caller via a `create_task` callable (Pipecat
FrameProcessor.create_task) so speculative work shares the exact same task
lifecycle/cleanup already used by SpeculativePrefetchProcessor's read-only
prefetch — no second task-management system.
"""
from __future__ import annotations

import asyncio
import datetime
import decimal
import enum
import hashlib
import json
import re
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from app.core.logging import get_logger
from app.services.speculative_execution import SpeculativeScope, speculative_scope
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation

logger = get_logger(__name__)

# Sentinel enqueued once a run's producer coroutine finishes (success or
# error already reported via a preceding BaseException item) so events()
# knows to stop iterating rather than blocking forever on an empty queue.
_DONE = object()


# A number keeps the punctuation that carries its meaning: sign, currency,
# decimal point, time and date separators, percent. Thousands commas go.
_NUMBER_RE = re.compile(r"[-+]?[$€£]?\d[\d,]*(?:[.:/]\d+)*%?")
_TOKEN_RE = re.compile(r"[-+]?[$€£]?\d[\d,]*(?:[.:/]\d+)*%?|\w+")


def _normalize_for_match(text: str) -> str:
    """Whitespace/case/punctuation-insensitive comparison — Deepgram framing
    can differ trivially between an interim partial and the final transcript
    without the underlying words actually differing.

    Punctuation inside a number is kept: "1.5" and "1 5", "-5" and "5",
    "10/12" and "10 12" are different requests.
    """
    tokens = _TOKEN_RE.findall((text or "").strip().casefold())
    return " ".join(tok.replace(",", "") if _NUMBER_RE.fullmatch(tok) else tok for tok in tokens)


def _word_prefix_extra(norm_spec: str, norm_final: str) -> list[str] | None:
    """Trailing words ``norm_final`` adds to ``norm_spec``, or None when the
    final does not extend the speculative text on a word boundary
    ("send it" is not a prefix of "send items").
    """
    spec_words = norm_spec.split()
    final_words = norm_final.split()
    if len(final_words) < len(spec_words) or final_words[: len(spec_words)] != spec_words:
        return None
    return final_words[len(spec_words) :]


# ---------------------------------------------------------------------------
# Strict transcript check (voice_request_revisions_v1)
# ---------------------------------------------------------------------------

# Trailing phrases that never change what was asked. Anything else after the
# speculative text (a qualifier, a negation, a new constraint, a correction)
# rejects adoption. Kept deliberately small: a miss costs one fresh call, a
# false accept answers a different question. ("again" is not inert: it can
# ask for a repeat of the action.)
_INERT_TAIL_PHRASES: tuple[tuple[str, ...], ...] = (
    ("thank", "you"),
    ("thanks",),
    ("please",),
    ("pls",),
    ("for", "me"),
    ("real", "quick"),
    ("quickly",),
    ("ok",),
    ("okay",),
    ("um",),
    ("uh",),
    ("uhm",),
    ("hmm",),
    ("er",),
    ("you", "know"),
)

# Words that, in a tail, qualify, negate or correct the request. Used for the
# rejection reason (the allowlist above rejects them anyway).
_QUALIFIER_RE = re.compile(
    r"\b(but|not|no|don t|dont|never|except|excluding|exclude|without|minus|only|just|"
    r"actually|wait|hold|instead|rather|unless|although|however|cancel|stop|nevermind|"
    r"scratch|sorry|or|and|also|plus)\b"
)


def _inert_tail(words: list[str]) -> bool:
    i = 0
    while i < len(words):
        for phrase in _INERT_TAIL_PHRASES:
            if tuple(words[i : i + len(phrase)]) == phrase:
                i += len(phrase)
                break
        else:
            return False
    return True


def extract_request_constraints(text: str) -> dict[str, Any]:
    """Cheap entities/constraints of an utterance, from the existing resolvers.

    No I/O and no model: the canonical time phrase (canonical_time_resolver),
    analytics sources and breakdowns (analytics_followup), the utterance-only
    tier and continuation shape (conversation_tier), and whether a qualifier or
    negation word is present.
    """
    raw = str(text or "")
    norm = _normalize_for_match(raw)
    out: dict[str, Any] = {
        "time": None,
        "sources": (),
        "breakdowns": (),
        "tier": None,
        "continuation": False,
    }
    try:
        from app.services.canonical_time_resolver import detect_time_phrase

        found = detect_time_phrase(raw)
        out["time"] = found[0] if found else None
    except Exception:  # noqa: BLE001 - extraction is best-effort; equal failures compare equal
        pass
    try:
        from app.services.analytics_followup import _breakdowns, _named_sources

        out["sources"] = tuple(_named_sources(raw))
        out["breakdowns"] = tuple(_breakdowns(raw))
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.conversation_tier import _content_tier, is_continuation_utterance

        out["tier"] = _content_tier(raw).tier
        out["continuation"] = bool(is_continuation_utterance(raw))
    except Exception:  # noqa: BLE001
        pass
    out["qualified"] = bool(_QUALIFIER_RE.search(norm))
    return out


def strict_transcript_match(
    spec_text: str,
    final_text: str,
    *,
    max_extra_words: int,
) -> tuple[bool, str]:
    """Stricter adoption test than the v2 prefix rule. Returns (ok, reason).

    An exact normalized match adopts. Otherwise the final must extend the
    speculative text on a word boundary by at most ``max_extra_words`` words
    (0 means exact only, which is what applies while v2 is off), every added
    word must belong to an inert tail ("please", "thanks"), and the extracted
    constraints must be identical.
    """
    norm_spec = _normalize_for_match(spec_text)
    norm_final = _normalize_for_match(final_text)
    if not norm_final or not norm_spec:
        return False, "empty"
    if norm_spec == norm_final:
        return True, "exact"
    if max_extra_words <= 0:
        return False, "exact_only"
    extra = _word_prefix_extra(norm_spec, norm_final)
    if extra is None:
        return False, "not_word_prefix"
    if len(extra) > max_extra_words:
        return False, "too_many_extra_words"
    if _QUALIFIER_RE.search(" ".join(extra)):
        return False, "qualifier_or_negation"
    if not _inert_tail(extra):
        return False, "meaningful_tail"
    if extract_request_constraints(spec_text) != extract_request_constraints(final_text):
        return False, "constraints_changed"
    return True, "inert_tail"


def classify_revision_delta(spec_text: str, final_text: str) -> str:
    """What a rejected revision changed, for the turn record.

    ``time_window_only`` marks a correction whose only change is the time
    window, the case partial reuse would target. Reuse itself is NOT done: the
    speculative run is one opaque execute_task_streaming call, so its context
    assembly and retrieval cannot be detached and re-bound to new constraints.
    A rejected run is discarded and the confirmed turn runs fresh (the
    read-only prefetch caches still help it). This label measures how often
    reuse would apply before anyone builds it.
    """
    if _normalize_for_match(spec_text) == _normalize_for_match(final_text):
        return "same"
    a = extract_request_constraints(spec_text)
    b = extract_request_constraints(final_text)
    if b.get("qualified") and not a.get("qualified"):
        return "qualified"
    changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if changed == ["time"]:
        try:
            from app.services.canonical_time_resolver import detect_time_phrase

            ta, tb = detect_time_phrase(spec_text), detect_time_phrase(final_text)
            rest_a = _normalize_for_match(spec_text.replace(ta[1], " ") if ta else spec_text)
            rest_b = _normalize_for_match(final_text.replace(tb[1], " ") if tb else final_text)
            if rest_a == rest_b:
                return "time_window_only"
        except Exception:  # noqa: BLE001
            pass
    return ("changed:" + ",".join(changed)) if changed else "wording"


# ---------------------------------------------------------------------------
# Request revisions
# ---------------------------------------------------------------------------


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RevisionVersions:
    """State a speculative answer depends on besides the words themselves."""

    conversation_id: str | None
    pending_task_version: str
    approval_version: str
    context_version: str
    # False when the state could not be read: unknown never matches anything,
    # not even another unknown.
    known: bool = True
    # Who asks, and the prompt (instructions, retrieved knowledge, injection
    # notes) the answer was produced under; set once the turn inputs exist.
    principal_version: str = ""
    prompt_version: str = ""


def compute_revision_versions(
    *,
    conversation_id: str | None,
    task_state: dict[str, Any] | None,
    history: list[dict[str, Any]] | None,
    history_summary: str | None,
) -> RevisionVersions:
    """Pure: fingerprint the pending task, approval state and context.

    The parameter ledger is left out on purpose: the confirmed turn ingests the
    final transcript's slots before the brain runs, so it always differs from
    the speculative read and would make adoption impossible without making it
    any safer (the slots come from the transcript, which is checked anyway).
    """
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else None
    approval = {
        "status": (pending or {}).get("status"),
        "claim": (pending or {}).get("execution_claim_id"),
        "approval": (pending or {}).get("approval_id") or (pending or {}).get("approval_token"),
        "pending_action": state.get("pending_action"),
        "unavailable": bool(state.get("_unavailable")),
    }
    turns = [
        (str(m.get("role") or ""), _normalize_for_match(str(m.get("content") or "")))
        for m in (history or [])
        if isinstance(m, dict)
    ]
    context = {
        "turns": turns,
        "summary": history_summary or "",
        "objective": state.get("active_objective"),
        "analytics_frame": state.get("analytics_frame"),
    }
    return RevisionVersions(
        conversation_id=(str(conversation_id).strip() or None) if conversation_id else None,
        pending_task_version=_digest({"pending_task": pending, "plan": state.get("current_plan")}),
        approval_version=_digest(approval),
        context_version=_digest(context),
        known=not bool(state.get("_unavailable")),
    )


def with_turn_inputs(
    versions: RevisionVersions,
    *,
    org_id: str | None,
    user_id: str | None,
    agent_id: str | None,
    turn_inputs: dict[str, Any] | None,
) -> RevisionVersions:
    """Bind the principal and the prompt the brain is about to run under."""
    return replace(
        versions,
        principal_version=_digest({"org": org_id, "user": user_id, "agent": agent_id}),
        prompt_version=_digest(turn_inputs or {}),
    )


async def load_revision_task_state(
    settings: Any, *, org_id: str, conversation_id: str | None
) -> dict[str, Any] | None:
    """The task_state revisions are computed from; ``{"_unavailable": True}`` on a failed read."""
    if not (conversation_id and org_id):
        return None
    try:
        from app.services.conversation_state_service import get_conversation_state_service

        return await get_conversation_state_service(settings).get_task_state(
            conversation_id, org_id, strict=True
        )
    except Exception as exc:  # noqa: BLE001 - an unknown state never matches anything
        logger.debug("speculative_revision_state_unavailable error=%s", exc)
        return {"_unavailable": True}


async def load_revision_versions(
    settings: Any,
    *,
    org_id: str,
    conversation_id: str | None,
    history: list[dict[str, Any]] | None,
    history_summary: str | None,
) -> RevisionVersions:
    """Read task_state (one small query, off the loop) and fingerprint it."""
    task_state = await load_revision_task_state(settings, org_id=org_id, conversation_id=conversation_id)
    return compute_revision_versions(
        conversation_id=conversation_id,
        task_state=task_state,
        history=history,
        history_summary=history_summary,
    )


@dataclass(frozen=True)
class RequestRevision:
    """One provisional version of what the user is asking (monotonic number)."""

    revision: int
    transcript: str


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpeculativeBounds:
    """Per-run limits (conservative defaults; Settings overrides are read by
    voice_latency_tuning.resolve_voice_speculative_bounds)."""

    timeout_s: float = 5.0
    max_buffered_chars: int = 2000
    max_buffered_events: int = 512
    # Hard limits: a run that keeps more than this alive (complete events,
    # tool payloads) or defers more writes than this is discarded, not paused.
    max_retained_bytes: int = 2_000_000
    max_deferred_writes: int = 256


@dataclass
class SpeculativeStats:
    """Per-session speculation counters."""

    started: int = 0
    adopted: int = 0
    discarded: int = 0
    timeouts: int = 0
    blocked: int = 0
    over_budget: int = 0
    buffer_pauses: int = 0
    rejected_revisions: int = 0
    deferred_writes_replayed: int = 0
    deferred_writes_dropped: int = 0
    wasted_s: float = 0.0

    def snapshot(self) -> dict[str, Any]:
        data = asdict(self)
        data["wasted_s"] = round(self.wasted_s, 3)
        return data


def _current_task() -> "asyncio.Task[Any] | None":
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


def _event_text_len(event: Any) -> int:
    payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        delta = payload.get("delta")
        if isinstance(delta, str):
            return len(delta)
    return 0


# Past this nesting depth or node count a payload is not measured: it counts
# as over any budget, so the run is dropped instead of undercounted.
_RETAINED_MAX_DEPTH = 32
_RETAINED_MAX_NODES = 50_000
# Leaf types measured by their own in-memory size; they hold no references.
_RETAINED_LEAVES = (
    type(None), bool, int, float, complex, str, bytes, bytearray, memoryview,
    enum.Enum, datetime.date, datetime.time, datetime.timedelta, decimal.Decimal, uuid.UUID,
)


def _slot_values(item: Any) -> list[Any] | None:
    """The attribute values held in ``__slots__`` (across the MRO), or None."""
    names: list[str] = []
    found = False
    for klass in type(item).__mro__:
        slots = klass.__dict__.get("__slots__")
        if slots is None:
            continue
        found = True
        names.extend([slots] if isinstance(slots, str) else list(slots))
    if not found:
        return None
    return [getattr(item, name) for name in names if name not in ("__dict__", "__weakref__") and hasattr(item, name)]


def _retained_size(value: Any, limit: int | None = None) -> int:
    """Conservative bytes a buffered value keeps alive.

    Every node counts its own in-memory size (``sys.getsizeof``, so a
    four-byte-per-character string counts as such), containers and objects
    are walked through ``__dict__`` and ``__slots__``. A payload too deep or
    too large to walk, or an object of a shape this cannot see into, returns
    more than ``limit`` (or a huge number), so it can never pass as small.
    Stops early once ``limit`` is exceeded.
    """
    ceiling = limit if limit is not None else 1 << 62
    over = ceiling + 1
    total = 0
    nodes = 0
    seen: set[int] = set()
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > _RETAINED_MAX_NODES or depth > _RETAINED_MAX_DEPTH:
            return over
        if isinstance(item, _RETAINED_LEAVES):
            # Counted per reference: a value repeated in a payload is counted
            # each time, which only ever overestimates.
            total += sys.getsizeof(item, 64)
            if total > ceiling:
                return over
            continue
        if id(item) in seen:
            # A container or object reached twice (or a cycle): counted once.
            continue
        seen.add(id(item))
        total += sys.getsizeof(item, 64)
        if isinstance(item, dict):
            for key, val in item.items():
                stack.append((key, depth + 1))
                stack.append((val, depth + 1))
        elif isinstance(item, (list, tuple, set, frozenset)):
            stack.extend((child, depth + 1) for child in item)
        else:
            held = getattr(item, "__dict__", None)
            slots = _slot_values(item)
            if held is None and slots is None:
                # An object this cannot see into: never treat it as small.
                return over
            if held is not None:
                stack.append((held, depth + 1))
            if slots:
                stack.extend((child, depth + 1) for child in slots)
        if total > ceiling:
            return over
    return total


def _event_retained_size(event: Any, limit: int | None = None) -> int:
    """Everything an event holds, not only its text delta: a complete event's
    full content, tool inputs and results, task state, any payload."""
    return _retained_size(event, limit)


@dataclass
class SpeculativeGenerationRun:
    """One in-flight or completed speculative generation attempt.

    `text` is the (partial) transcript this run was launched with — the only
    thing `adopt()` ever compares against the final transcript.
    """

    text: str
    task: "asyncio.Task[None]"
    queue: "asyncio.Queue[Any]" = field(default_factory=asyncio.Queue)
    consumed: bool = False
    # Conversation tier the run computed for its own text + history; set by
    # the runner once known. Used to refuse a prefix adoption across tiers.
    tier: str | None = None
    # The brain's pre-LLM checkpoints for this run (execute_task_streaming
    # latency_marks), read by the confirmed turn's latency record on adoption.
    latency_marks: dict[str, Any] = field(default_factory=dict)
    # Side-effect ledger: deferred durable writes, refused side effects.
    scope: SpeculativeScope = field(default_factory=SpeculativeScope)
    # The run's own work token; the turn that adopts it links it to its own.
    cancellation: TurnCancellation = field(default_factory=TurnCancellation)
    bounds: SpeculativeBounds = field(default_factory=SpeculativeBounds)
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float | None = None
    # None while pending, then adopted | discarded | timeout | blocked.
    outcome: str | None = None
    buffered_chars: int = 0
    buffered_events: int = 0
    retained_bytes: int = 0
    paused: bool = False
    dropped_writes: int = 0
    # voice_request_revisions_v1: the revision this run answers and the state
    # versions it was produced under (set by the runner before the brain runs).
    revision: RequestRevision | None = None
    versions: RevisionVersions | None = None
    on_settle: Callable[["SpeculativeGenerationRun"], None] | None = None
    on_pause: Callable[[], None] | None = None
    _adopted_evt: asyncio.Event = field(default_factory=asyncio.Event)
    _timer: asyncio.TimerHandle | None = None

    def matches(
        self,
        final_text: str,
        *,
        prefix_max_extra_words: int = 0,
        tier: str | None = None,
    ) -> bool:
        if not final_text:
            return False
        norm_final = _normalize_for_match(final_text)
        norm_spec = _normalize_for_match(self.text)
        if norm_final == norm_spec:
            # Same text and same history give the same tier (the classifier is
            # pure), so an exact match needs no tier comparison.
            return True
        if prefix_max_extra_words <= 0 or not norm_spec:
            return False
        if tier is not None and self.tier != tier:
            # Extra trailing words can change the tier ("hey" -> "hey, pull my
            # pipeline"); an answer produced for another tier is not reusable.
            return False
        # Word boundary, not character prefix: "send it" must not adopt for
        # "send items".
        extra = _word_prefix_extra(norm_spec, norm_final)
        if extra is None:
            return False
        return len(extra) <= prefix_max_extra_words

    # -- lifecycle -------------------------------------------------------------
    def _settle(self, outcome: str) -> None:
        if self.outcome is not None:
            return
        self.outcome = outcome
        self.ended_at = time.monotonic()
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if outcome != "adopted":
            self.dropped_writes = self.scope.discard()
            # A worker thread of the run outlives the task cancel below.
            self.cancellation.cancel(f"speculative_{outcome}")
            if not self.task.done() and self.task is not _current_task():
                self.task.cancel()
            # Release a producer paused on the buffer cap so its cancellation lands.
            self._adopted_evt.set()
        if self.on_settle is not None:
            self.on_settle(self)

    @property
    def wasted_s(self) -> float:
        if self.outcome in (None, "adopted"):
            return 0.0
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return max(0.0, end - self.started_at)

    def cancel(self) -> None:
        if self.outcome is None:
            self._settle("blocked" if self.scope.blocked else "discarded")
        elif not self.task.done():
            self.task.cancel()

    def _expire(self) -> None:
        self._timer = None
        if self.outcome is None and not self.consumed:
            logger.info("pipecat_voice_speculative_generation_timeout chars=%s", len(self.text))
            self._settle("timeout")

    def mark_adopted(self) -> None:
        self.consumed = True
        self._settle("adopted")
        self._adopted_evt.set()

    async def commit(self) -> int:
        """Replay the deferred durable writes (adoption). Raises
        SpeculativeSideEffectBlocked when the run hit a refused side effect."""
        return await self.scope.commit()

    def start_commit(self) -> "asyncio.Task[int] | None":
        """Adopt now and replay the deferred writes in the background.

        The adoption check (blocked or not) is synchronous, so a refused run
        still fails before any of its output is used; the replay does not
        hold the first buffered event back. Writes the producer makes from
        here on queue behind the replay, in order. None when there is nothing
        to replay.
        """
        if not self.scope.begin_commit():
            return None
        return asyncio.ensure_future(self.scope.replay())

    async def _admit(self, event: Any) -> bool:
        """Account for one produced event; False when the run must stop."""
        self.buffered_events += 1
        self.buffered_chars += _event_text_len(event)
        self.retained_bytes += _event_retained_size(
            event, max(0, self.bounds.max_retained_bytes - self.retained_bytes)
        )
        if self.consumed:
            return True
        if self.retained_bytes > self.bounds.max_retained_bytes:
            # Over the hard budget: free it now. The confirmed turn runs fresh.
            logger.info(
                "pipecat_voice_speculative_generation_over_budget bytes=%s", self.retained_bytes
            )
            self._settle("over_budget")
            # Drop what it buffered so the memory goes with it.
            while not self.queue.empty():
                self.queue.get_nowait()
            return False
        if (
            self.buffered_chars > self.bounds.max_buffered_chars
            or self.buffered_events > self.bounds.max_buffered_events
        ):
            # Bounded buffer: stop producing until the confirmed turn adopts
            # (and drains) the run or the timeout discards it.
            if not self.paused:
                self.paused = True
                if self.on_pause is not None:
                    self.on_pause()
            await self._adopted_evt.wait()
        return True

    async def events(self) -> AsyncIterator[Any]:
        """Yield every event this run has produced (already-buffered ones
        first, then whatever the still-running producer adds) until the
        producer signals completion. Re-raises any exception the producer
        surfaced, matching the semantics of iterating the live generator
        directly (a fresh execute_task_streaming() call failing mid-stream
        looks identical to the caller either way).
        """
        while True:
            item = await self.queue.get()
            if item is _DONE:
                return
            if isinstance(item, BaseException):
                raise item
            yield item

    async def adopted_events(self) -> AsyncIterator[Any]:
        """Replay the run's deferred writes, then yield its events."""
        await self.commit()
        async for item in self.events():
            yield item


async def _drive_into_queue(
    runner: Callable[[], AsyncIterator[Any]],
    queue: "asyncio.Queue[Any]",
    run: SpeculativeGenerationRun | None = None,
) -> None:
    scope = run.scope if run is not None else SpeculativeScope()
    cancellation = run.cancellation if run is not None else None
    with speculative_scope(scope), bound_turn_cancellation(cancellation):
        try:
            async for event in runner():
                if run is not None:
                    if scope.blocked and not run.consumed:
                        # A refused side effect: this run can never be adopted,
                        # so stop spending on it now.
                        run._settle("blocked")
                        break
                    if not await run._admit(event):
                        break
                await queue.put(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — surfaced to the eventual consumer, not lost
            await queue.put(exc)
        finally:
            await queue.put(_DONE)


def start_speculative_run(
    *,
    text: str,
    runner: Callable[[], AsyncIterator[Any]],
    create_task: Callable[[Awaitable[None]], "asyncio.Task[None]"],
    bounds: SpeculativeBounds | None = None,
    revision: RequestRevision | None = None,
) -> SpeculativeGenerationRun:
    """Launch one speculative run. Caller is responsible for cancelling any
    prior run first (SpeculativeGenerationCoordinator.set_run does this).
    """
    queue: "asyncio.Queue[Any]" = asyncio.Queue()
    holder: list[SpeculativeGenerationRun] = []

    async def _drive() -> None:
        # create_task only schedules, so the run below exists before this body runs.
        await _drive_into_queue(runner, queue, holder[0] if holder else None)

    task = create_task(_drive())
    run = SpeculativeGenerationRun(
        text=text,
        task=task,
        queue=queue,
        bounds=bounds or SpeculativeBounds(),
        revision=revision,
    )
    holder.append(run)
    run.scope.max_deferred = run.bounds.max_deferred_writes
    if run.bounds.timeout_s and run.bounds.timeout_s > 0:
        try:
            run._timer = asyncio.get_running_loop().call_later(run.bounds.timeout_s, run._expire)
        except RuntimeError:
            pass
    return run


class SpeculativeGenerationCoordinator:
    """Owns at most one in-flight/pending speculative run per voice session.

    Shared (one instance) between SpeculativePrefetchProcessor and
    GravitreCognitiveLLMService via pipeline.py, so the run started by the
    former can be adopted by the latter.
    """

    def __init__(self) -> None:
        self._run: SpeculativeGenerationRun | None = None
        self.stats = SpeculativeStats()
        self._revision = 0
        self._latest: RequestRevision | None = None
        # Why the last adopt() refused, and what the revision changed (turn record).
        self.last_reject_reason: str | None = None
        self.last_revision_delta: str | None = None

    @property
    def has_pending_run(self) -> bool:
        return self._run is not None

    @property
    def pending_run(self) -> SpeculativeGenerationRun | None:
        return self._run

    # -- revisions -------------------------------------------------------------
    def note_transcript(self, text: str) -> RequestRevision:
        """Record a provisional transcript. The revision number rises only when
        the normalized words change, and never goes down."""
        norm = _normalize_for_match(text)
        if self._latest is None or _normalize_for_match(self._latest.transcript) != norm:
            self._revision += 1
            self._latest = RequestRevision(revision=self._revision, transcript=text)
        return self._latest

    @property
    def latest_revision(self) -> RequestRevision | None:
        return self._latest

    # -- accounting ------------------------------------------------------------
    def _settled(self, run: SpeculativeGenerationRun) -> None:
        if run.outcome == "adopted":
            self.stats.adopted += 1
            return
        if run.outcome == "timeout":
            self.stats.timeouts += 1
        elif run.outcome == "blocked":
            self.stats.blocked += 1
        elif run.outcome == "over_budget":
            self.stats.over_budget += 1
        self.stats.discarded += 1
        self.stats.wasted_s += run.wasted_s
        self.stats.deferred_writes_dropped += run.dropped_writes
        logger.info(
            "pipecat_voice_speculative_generation_settled outcome=%s wasted_ms=%s dropped_writes=%s",
            run.outcome,
            int(run.wasted_s * 1000),
            run.dropped_writes,
        )

    def _paused(self) -> None:
        self.stats.buffer_pauses += 1

    def note_replayed(self, count: int) -> None:
        self.stats.deferred_writes_replayed += max(0, int(count or 0))

    def cancel(self) -> None:
        """Cancel and discard any pending run — the probable-EOT was wrong
        (user kept talking) or a new turn boundary made it moot.
        """
        if self._run is not None:
            self._run.cancel()
            self._run = None

    def set_run(self, run: SpeculativeGenerationRun) -> None:
        """Replace the pending run, cancelling whatever was running before.

        Reuses the same cancel-then-restart pattern speculative_prefetch.py
        already applies to its own read-only prefetch task — no second,
        separate cancellation mechanism introduced for generation.
        """
        self.cancel()
        run.on_settle = self._settled
        run.on_pause = self._paused
        self.stats.started += 1
        self._run = run

    def adopt(
        self,
        final_text: str,
        *,
        prefix_max_extra_words: int = 0,
        tier: str | None = None,
        strict: bool = False,
        versions: RevisionVersions | None = None,
    ) -> SpeculativeGenerationRun | None:
        """Return the pending run if its text matches `final_text`, else None
        (cancelling a non-matching pending run along the way — it will never
        be consumed now that the turn has been confirmed with different
        text). Idempotent: a run already consumed is never returned twice.

        When ``prefix_max_extra_words`` > 0 (Phase 4), a final transcript
        that merely extends the speculative partial by a few trailing words
        still adopts — e.g. probable-EOT on "what is two plus two" and final
        "what is two plus two please" keeps the head-start instead of
        restarting the LLM call.

        ``strict`` (voice_request_revisions_v1) additionally requires the
        strict transcript check, no newer incompatible revision, and every
        bound version (conversation, pending task, approval, context) to
        equal ``versions``. It only ever rejects more.
        """
        run = self._run
        self._run = None
        self.last_reject_reason = None
        self.last_revision_delta = None
        if run is None or run.consumed:
            return None
        reason = self._reject_reason(
            run,
            final_text,
            prefix_max_extra_words=prefix_max_extra_words,
            tier=tier,
            strict=strict,
            versions=versions,
        )
        if reason is not None:
            # Confirmed work takes priority: a run that cannot be adopted is
            # cancelled now, not left to finish in the background.
            self.last_reject_reason = reason
            if strict:
                self.stats.rejected_revisions += 1
                self.last_revision_delta = classify_revision_delta(run.text, final_text)
            run.cancel()
            return None
        run.mark_adopted()
        return run

    def _reject_reason(
        self,
        run: SpeculativeGenerationRun,
        final_text: str,
        *,
        prefix_max_extra_words: int,
        tier: str | None,
        strict: bool,
        versions: RevisionVersions | None,
    ) -> str | None:
        if run.outcome is not None:
            return f"run_{run.outcome}"
        if run.scope.blocked:
            return "side_effect_blocked"
        if not run.matches(final_text, prefix_max_extra_words=prefix_max_extra_words, tier=tier):
            return "transcript_mismatch"
        if not strict:
            return None
        ok, why = strict_transcript_match(run.text, final_text, max_extra_words=prefix_max_extra_words)
        if not ok:
            return f"strict_transcript:{why}"
        latest = self._latest
        if run.revision is not None and latest is not None and latest.revision != run.revision.revision:
            ok, why = strict_transcript_match(
                run.revision.transcript, latest.transcript, max_extra_words=prefix_max_extra_words
            )
            if not ok:
                return f"newer_revision:{why}"
        if run.versions is None or versions is None:
            return "versions_unbound"
        if not run.versions.known or not versions.known:
            return "versions_unknown"
        for name in (
            "conversation_id",
            "principal_version",
            "prompt_version",
            "pending_task_version",
            "approval_version",
            "context_version",
        ):
            if getattr(run.versions, name) != getattr(versions, name):
                return f"version_mismatch:{name}"
        return None
