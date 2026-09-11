"""Voice 3.0 Phase 5 — conversational polish.

Three independent, flag-gated pieces:

* ``VOICE_SPOKEN_PROMPT_V2`` — extra SPOKEN-register directives that stack on top
  of :func:`app.services.voice_agent_profile.spoken_register_section`. It never
  replaces Register 5; the v1 section still ships unchanged when the flag is off.
* ``VOICE_RESPONSE_LENGTH_ADAPT_V1`` — derives a per-turn length band from the
  user's own utterance so a four-word question does not get a four-sentence
  answer, and a long multi-part question is allowed room.
* ``VOICE_PLAYED_AUDIO_RECONCILE_V1`` — after a barge-in, reconcile the drafted
  assistant text down to what was actually spoken aloud, so the next turn's
  history matches what the human heard instead of text they never received.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_WORD_RE = re.compile(r"[\w'’-]+")

# Question shapes that legitimately need more than a one-liner even when the
# user's own utterance was short ("why is the sync failing?").
_EXPLANATORY_PREFIXES = ("why", "how come", "how do", "how does", "how did", "explain", "walk me")

_MULTI_PART_MARKERS = (" and also ", " and then ", "; also", " plus ", " as well as ")


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def spoken_prompt_v2_section() -> str:
    """Additional SPOKEN directives — stacks on Register 5, does not replace it."""
    return """
## Register 5b — SPOKEN delivery (voice turns only; extends Register 5)

- Write for the ear, not the eye. Read the sentence back in your head; if it
  would make a person re-listen, shorten it or split it.
- Use contractions the way people speak: "it's", "you're", "that's", "won't",
  "I'll". Avoid stiff written forms ("do not", "cannot", "it is") unless you are
  deliberately stressing the word.
- One idea per sentence. Do not stack two clauses joined by "which" or "whereas".
- Numbers, dates, and identifiers should be spoken the way a person says them:
  "about twelve hundred" not "1,200"; "March fourth" not "03/04"; read long ids
  in short groups rather than digit-by-digit.
- Never speak punctuation, formatting, or emoji names aloud, and never emit
  asterisks, underscores, backticks, or bracketed stage directions.
- Do not narrate what you are about to do, and never announce a step you are not
  actually taking: no "one moment", "I'm going to", "as I mentioned". Say the
  thing. Progress updates for real tool calls and real loop stages (PERCEIVE,
  RETRIEVE, PLAN, ACT, OBSERVE) are spoken for you by the runtime, so never write your own — and never restate one that was already spoken.
- Vary how you open consecutive turns. If your previous spoken turn opened with
  a given word, do not open with it again.
- If the user interrupted you, do not restart the sentence they cut off and do
  not apologise for being cut off. Answer the new thing they said.
- When you must hand back a list of facts aloud, cap it at three items and say
  how many there are first ("three things — first…").
- End on the substance. Do not close with an offer of further help unless the
  user is genuinely blocked on a choice.
""".strip()


@dataclass(frozen=True)
class ResponseLengthBand:
    """Target spoken-reply size derived from the user's own utterance.

    Known limitation, measured in production 2026-09-08 with
    ``VOICE_RESPONSE_LENGTH_ADAPT_V1`` on: the band reaches the model correctly
    (verified in the composed prompt) but is not reliably obeyed. A *brief* turn
    (2 sentences / 35 words) came back at 9 sentences / 81 words; a *standard*
    turn (3 / 55) at 17 sentences / 331 words.

    Enforcing it with ``max_completion_tokens`` was tried and reverted the same
    day — it bounded length but cut replies mid-sentence, which TTS speaks aloud
    and cannot un-say. The overruns also correlated with replies that were not in
    spoken register at all (markdown asterisks, table names, "Let me check…" tool
    narration), so length looks like a symptom of tool-using voice turns taking a
    text-chat formatting path rather than a problem to solve with a ceiling.
    """

    band: str
    max_sentences: int
    soft_word_cap: int
    reason: str

    def as_meta(self) -> dict[str, Any]:
        return {
            "band": self.band,
            "max_sentences": self.max_sentences,
            "soft_word_cap": self.soft_word_cap,
            "reason": self.reason,
        }


def resolve_response_length_band(user_text: str | None) -> ResponseLengthBand:
    """Map an utterance to a length band. Pure function — no settings, no I/O."""
    text = (user_text or "").strip()
    words = _word_count(text)
    lowered = text.lower()

    explanatory = lowered.startswith(_EXPLANATORY_PREFIXES)
    multi_part = any(marker in lowered for marker in _MULTI_PART_MARKERS) or lowered.count("?") > 1

    if multi_part:
        return ResponseLengthBand(
            band="expansive",
            max_sentences=5,
            soft_word_cap=90,
            reason="multi_part_question",
        )
    if words >= 40:
        return ResponseLengthBand(
            band="expansive",
            max_sentences=5,
            soft_word_cap=90,
            reason="long_user_utterance",
        )
    if explanatory:
        return ResponseLengthBand(
            band="standard",
            max_sentences=3,
            soft_word_cap=55,
            reason="explanatory_question",
        )
    if words >= 16:
        return ResponseLengthBand(
            band="standard",
            max_sentences=3,
            soft_word_cap=55,
            reason="medium_user_utterance",
        )
    if words >= 5:
        return ResponseLengthBand(
            band="brief",
            max_sentences=2,
            soft_word_cap=35,
            reason="short_user_utterance",
        )
    return ResponseLengthBand(
        band="terse",
        max_sentences=1,
        soft_word_cap=18,
        reason="very_short_user_utterance",
    )


def response_length_directive(band: ResponseLengthBand) -> str:
    """Prompt fragment that states the band without inviting padding to reach it."""
    sentence_word = "sentence" if band.max_sentences == 1 else "sentences"
    return f"""
## Spoken length target for THIS turn

The user's message maps to the **{band.band}** band. Answer in at most
{band.max_sentences} {sentence_word} (roughly {band.soft_word_cap} spoken words or
fewer). This is a ceiling, not a quota — if one short sentence fully answers the
question, stop there. Never add filler, restated context, or a closing offer just
to reach the ceiling. If the facts genuinely cannot fit, give the answer first and
offer the detail rather than overrunning.
""".strip()


@dataclass(frozen=True)
class PlayedAudioReconciliation:
    """What the human actually heard vs. what the model drafted."""

    reconciled_text: str
    full_draft_text: str
    dropped_chars: int
    truncated: bool
    match_strategy: str
    matched_words: int

    def as_meta(self) -> dict[str, Any]:
        return {
            "reconciled_chars": len(self.reconciled_text),
            "draft_chars": len(self.full_draft_text),
            "dropped_chars": self.dropped_chars,
            "truncated": self.truncated,
            "match_strategy": self.match_strategy,
            "matched_words": self.matched_words,
        }


# Punctuation that belongs to the word it follows, so a cut at a word boundary
# keeps "finished." rather than stranding the period into the dropped tail.
_TRAILING_PUNCT = set(".,!?;:…\"')]}")


def _leading_matched_words(draft: str, spoken: str) -> tuple[int, int, int]:
    """Count leading words shared by draft and spoken; return (n, cut, spoken_n).

    Comparison is on word tokens (case-folded, punctuation excluded), so the two
    strings can differ in whitespace, capitalisation, or punctuation and still
    align. ``cut`` is an index into ``draft`` just past the n-th matched word.
    """
    draft_tokens = [(m.group(0).casefold(), m.end()) for m in _WORD_RE.finditer(draft)]
    spoken_tokens = [m.group(0).casefold() for m in _WORD_RE.finditer(spoken)]

    matched = 0
    cut = 0
    for (draft_word, draft_end), spoken_word in zip(draft_tokens, spoken_tokens):
        if draft_word != spoken_word:
            break
        matched += 1
        cut = draft_end
    # Absorb punctuation that immediately trails the last matched word.
    while cut < len(draft) and draft[cut] in _TRAILING_PUNCT:
        cut += 1
    return matched, cut, len(spoken_tokens)


def reconcile_played_audio(
    *,
    spoken_text: str | None,
    full_draft_text: str | None,
) -> PlayedAudioReconciliation:
    """Trim a barge-in draft to the portion that was actually spoken aloud.

    ``spoken_text`` comes from TTS-aligned text frames, so it is the closest
    available proxy for played audio. Alignment is done on word tokens rather than
    raw characters: the TTS provider routinely returns the same words with
    different whitespace or punctuation than the LLM draft, and a strict
    ``startswith`` check would silently fall through to "no truncation" on those
    turns — reporting success while dropping nothing.

    ``match_strategy`` records how the boundary was found so a live trace can
    distinguish a real truncation from a fallback:

    * ``exact_prefix`` — spoken text is a literal prefix of the draft.
    * ``word_prefix`` — all spoken words matched; whitespace/punctuation differed.
    * ``diverged_word_prefix`` — alignment diverged partway; cut at the last
      word known to have been spoken (conservative, never over-claims).
    * ``full_match`` — the whole draft was spoken; nothing to drop.
    * ``nothing_spoken`` — interrupted before any audio was aligned.
    * ``no_overlap_fallback_draft`` — zero shared leading words; keep the draft
      rather than invent a boundary.
    * ``empty_draft`` — no draft to reconcile against.
    """
    spoken = (spoken_text or "").strip()
    draft = (full_draft_text or "").strip()

    if not draft:
        return PlayedAudioReconciliation(
            reconciled_text=spoken,
            full_draft_text=spoken,
            dropped_chars=0,
            truncated=False,
            match_strategy="empty_draft",
            matched_words=0,
        )
    if not spoken:
        # Interrupted before any audio was aligned — nothing was heard.
        return PlayedAudioReconciliation(
            reconciled_text="",
            full_draft_text=draft,
            dropped_chars=len(draft),
            truncated=True,
            match_strategy="nothing_spoken",
            matched_words=0,
        )

    matched, cut, spoken_word_count = _leading_matched_words(draft, spoken)

    if matched == 0:
        return PlayedAudioReconciliation(
            reconciled_text=draft,
            full_draft_text=draft,
            dropped_chars=0,
            truncated=False,
            match_strategy="no_overlap_fallback_draft",
            matched_words=0,
        )

    reconciled = draft[:cut].rstrip()
    dropped = len(draft) - len(reconciled)

    if dropped <= 0:
        return PlayedAudioReconciliation(
            reconciled_text=draft,
            full_draft_text=draft,
            dropped_chars=0,
            truncated=False,
            match_strategy="full_match",
            matched_words=matched,
        )

    if matched < spoken_word_count:
        strategy = "diverged_word_prefix"
    elif draft.startswith(spoken):
        strategy = "exact_prefix"
    else:
        strategy = "word_prefix"

    return PlayedAudioReconciliation(
        reconciled_text=reconciled,
        full_draft_text=draft,
        dropped_chars=dropped,
        truncated=True,
        match_strategy=strategy,
        matched_words=matched,
    )


def resolve_conversational_polish_flags(settings: Any) -> dict[str, bool]:
    """Read the three Phase 5 flags off settings with safe defaults."""
    return {
        "spoken_prompt_v2": bool(getattr(settings, "voice_spoken_prompt_v2", False)),
        "response_length_adapt_v1": bool(
            getattr(settings, "voice_response_length_adapt_v1", False)
        ),
        "played_audio_reconcile_v1": bool(
            getattr(settings, "voice_played_audio_reconcile_v1", False)
        ),
    }
