# Phase 2: first dialogue interpretation increment

Implementation branch: `feat/phase2-dialogue-intelligence`.

The existing CognitiveTurnKernel derives tentative English-language cues during
RETRIEVE. The six-stage sequence, reasoning, routing, memory, GOVERN and action
execution remain in the existing runtime. The interpreter does not call an LLM,
read another tenant's context, create memories, or issue authorization decisions.

Supported cues: correction, clarification, uncertainty, hesitation, indirect
requests, explicit frustration/worry/stress/overwhelm/excitement wording,
conversational repair, thinking aloud, gratitude, explicit joking, and explicit
sarcasm. These are lexical cues, not proof of intent or emotion. Unmarked sarcasm,
implicit humour, multilingual understanding and full contextual interpretation
are not certified by this increment.

The kernel exports fixed advisory guidance as `dialogue_section`. ContextCompiler
and unified prompt assembly include it independently of knowledge retrieval, so
conversational turns do not lose it when RAG is excluded. Agent task prompt
assembly also consumes the same section. Pipecat continues to use the existing
cognitive bridge; no new voice pipeline or reasoning engine is introduced.

Only allowlisted cue names and a version/scope are added to the RETRIEVE stage
diagnostics. Neither the interpretation object nor its guidance contains raw
transcripts, identifiers, excerpts, hashes or dynamically generated instructions.
This does not change the broader runtime's existing message-retention policy.

Targeted verification covers interpreter positives/negatives, privacy, arbitrary
cue injection, canonical ambiguous-write denial, per-context isolation, both
spoken and text kernel requests, context propagation when RAG is excluded, and
the existing kernel, canonical ingress and context compiler suites.

Production dialogue quality, cross-role behavioural certification and the live
combined LLM quality battery remain NOT RUN for this branch. They are release
gates before promotion, not evidence supplied by mocked or unit tests. Emotional
intelligence, natural-conversation policy, long-term memory, multilingual behaviour
and Pipecat performance remain subsequent workstreams.

## Emotional and natural-conversation validation increment

Fixed doubled regex word-boundary escapes in the four new cue patterns and the
spoken-write affirmative/hold veto rule. Existing assertions were retained.
The veto correction makes later stop/hesitation clauses classify as `hold_commit`
instead of an unmatched utterance; it does not expand write authorization.

Multi-turn integration runs six successive requests through the real pre-ACT
kernel and context compiler in text and spoken modes: worry, correction,
brainstorming/hesitation, excitement, yes-wait, and gratitude. It verifies cue
changes, absence of stale emotional guidance, history input preservation,
transcript-free cue diagnostics, unchanged pending-action state, and denied
write approval. Recall/storage are mocked; model-generated replies and physical
voice output are not exercised. Spoken conversational depth intentionally skips
heavy recall under the existing latency policy; the test checks that policy
explicitly and does not claim a memory lookup occurred.

Negation/unrelated-word cases guard against obvious false positives. Passing
these deterministic tests is not certification of conversational naturalness,
human emotional understanding, or end-to-end provider/device behaviour. The
branch remains unmerged and undeployed pending those separate release gates.
