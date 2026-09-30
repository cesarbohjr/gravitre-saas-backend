# Gravitre Voice parity standard

Gravitre LIVE is accepted only when its observable conversational experience is competitive with the current ChatGPT Voice and Claude Voice class of assistants. This is a behavioral benchmark, not an attempt to copy proprietary implementations or voices.

## Required behavior

1. **Continuous session** — a completed assistant turn must become audible and commit without closing or reopening Talk.
2. **Full-duplex barge-in** — user speech during assistant playback immediately stops current output and the next response follows the interruption, without replaying stale audio.
3. **Patient turn-taking** — ordinary thinking pauses must not be treated as a completed turn too aggressively. Explicit requests to wait/listen must be respected.
4. **Low perceived latency** — acknowledge quickly when useful; do not fill latency with robotic lifecycle narration.
5. **Natural speech** — sentence-level prosody, coherent pacing, no tiny TTS fragments, no raw markdown, enums, action keys, or internal state read aloud.
6. **Conversational grounding** — follow-ups such as “another one”, “yes”, “no, the other one”, corrections, and pronouns resolve against the live conversation rather than restarting context.
7. **Interruption reconciliation** — visible/persisted assistant text reflects what was actually delivered after an interruption.
8. **Tool continuity** — tool work may take longer than speech, but Voice remains conversational, explains approval needs naturally, and resumes with the result without duplicating the answer.
9. **No false completion** — a text result is not counted as successful Voice delivery unless the live transport owns the turn and playback evidence/recovery semantics are coherent.
10. **Failure recovery** — transient transport/TTS failures recover inside the same session where possible and never require orb close/reopen as the normal recovery mechanism.

## Release acceptance

Automated tests must cover the deterministic contracts above. Production acceptance additionally requires five consecutive multi-turn Talk exchanges, including one interruption, one thinking pause, one follow-up correction, and one tool/approval flow. None may require closing/reopening Talk, replay an already delivered response, leak lifecycle jargon, or leave text/result state contradictory.

Subjective voice quality is evaluated on natural pacing, continuity, expressiveness without exaggeration, and absence of synthetic fragment resets. Provider defaults alone are not acceptance evidence.
