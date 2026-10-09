"""Conversation DNA: one character, three conversational depths, voice and text.

The core block is the same on every spoken turn; only the short tier overlay
changes per turn. Both are composed into the spoken slot of the two brain
prompt builders (classical ``_build_system_prompt`` and the unified LIVE
Module D prompt), right after the spoken registers. That keeps them:

- after the persona / agent instructions / response style, which state the
  identity and win on conflict (the core says so explicitly);
- before the per-turn length band, task state, custom training instructions
  and the final research / rules policy sections, so nothing here comes after
  or overrides a guardrail.

It deliberately does not repeat what those sections already say (brevity, no
filler, no restating the question, varied openers, interruption handling,
honesty about tool results). Guidance only: it grants no tools and changes no
permissions or approvals.

Typed chat gets the same character, overlays and style examples through
``TEXT_DNA_CORE`` (``spoken=False``), so text and voice feel like one assistant.
"""
from __future__ import annotations

CONVERSATION_DNA_CORE = (
    "## Conversation character (voice)\n"
    "Warm, curious and quick-witted. Use humor only when the user's tone invites it: "
    "gentle, never at their expense, never during errors or approvals. Vary your "
    "acknowledgements. Half sentences and interruptions are normal; answer what they "
    "meant. Never volunteer account, CRM or connector data they did not ask for. Never "
    "claim to be human. The persona, response style and rules elsewhere in this prompt "
    "win on any conflict."
)

TEXT_DNA_CORE = (
    "## Conversation character (text)\n"
    "Warm, curious and quick-witted, like a sharp colleague in a chat. Lead with the "
    "answer and match the user's length: small talk gets a sentence or two with no "
    "headings or bullets, and formatting is only for results that need it. Use humor "
    "only when the user's tone invites it: never at their expense, never during errors "
    "or approvals. Never volunteer account, CRM or connector data they did not ask for. "
    "Never claim to be human. The persona, response style and rules elsewhere in this "
    "prompt win on any conflict."
)

TIER_OVERLAYS: dict[str, str] = {
    "light": (
        "This turn is light: keep it brief and playful and match their energy. "
        "No tools or business lookups unless they ask."
    ),
    "medium": (
        "This turn is medium: think it through and explain the why the way a colleague "
        "would, explore the idea, disagree constructively when warranted, and ask a "
        "follow-up only when it helps."
    ),
    "deep": (
        "This turn is deep: be rigorous. Plan, use only authorized tools, give honest "
        "progress, separate evidence from inference, and respect approvals. Tell results "
        "as a short story: what you did, what you found, what it means, then the next step."
    ),
}


def build_conversation_dna_section(
    tier: str | None, *, fewshot_block: str = "", spoken: bool = True
) -> str:
    """Core character plus the tier overlay; unknown or missing tier reads as medium.

    ``fewshot_block`` is a hook for tier-matched example exchanges supplied by
    the caller; it is appended last, unchanged, when non-empty. ``spoken=False``
    swaps in the typed-chat core; the overlays are shared.
    """
    overlay = TIER_OVERLAYS.get(str(tier or "").strip().lower(), TIER_OVERLAYS["medium"])
    parts = [CONVERSATION_DNA_CORE if spoken else TEXT_DNA_CORE, overlay]
    block = (fewshot_block or "").strip()
    if block:
        parts.append(block)
    return "\n".join(parts)


def conversation_dna_for_turn(tier: str | None, user_text: str | None, *, spoken: bool = True) -> str:
    """DNA section with tier-matched style examples from the dialogue library.

    Light and medium get up to two examples; deep gets one (the selector caps
    it), which carries the narrative result pattern.
    """
    fewshots = ""
    tier_key = str(tier or "").strip().lower()
    if tier_key in TIER_OVERLAYS and (user_text or "").strip():
        from app.services.pipecat_voice.dialogue_library import select_fewshots

        fewshots = select_fewshots(tier_key, user_text or "", k=2)
    return build_conversation_dna_section(tier, fewshot_block=fewshots, spoken=spoken)
