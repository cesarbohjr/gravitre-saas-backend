# PR587 multi-turn conversational baseline

The user's continuation advances the roadmap's conversational-baseline increment.
PR587 remains open/draft; no merge, deployment, provider request, dependency
installation, runtime policy change, external memory transfer or telemetry
activation is performed.

## Resulting behavior

The existing 26-case / 520-pair synthetic baseline is preserved byte-for-byte at
the case-data level. A regression freezes its SHA-256 as
`a41ab1f73ebeff9cc857b1513e0ae5c437b8b25da5d79ee8925f4fba9676c68b`.
A separate 12-case, three-turn corpus spans the six approved Marketplace target
labels and twelve conversational categories. Canonical ten-persona profiles,
two prompt paths and paired channels produce 240 paired conversations / 720
turn checkpoints for a future separately authorized generated evaluation.

The runner carries each channel's own generated replies into its next turn.
It uses the existing dialogue/session-continuity builders, message-priority
conventions and strict judge rubric. No answer key is a reference assistant
turn. Target labels do not create agents or grant tools. Production prompt
builders, task model tiers, voice transports, memory and execution gates are
unchanged.

## Evidence honesty and boundaries

The new runner has no default HTTP/provider adapter or credential discovery.
Missing callbacks report NOT_RUN; successful injected-fixture runs report
CONTRACT_PASS. Generated-mode callback provenance is explicitly reported rather
than independently verified; a trusted authorized host remains responsible for
real receipts. Every report marks production_certified false.

Source SHA/file hashes, dataset and old-baseline hashes, evaluator version,
category outcomes, negative security outcomes, measured callback latency and
supplied token counts are recorded. Cost stays unknown without verified pricing;
incomplete token usage stays unknown. Raw prompt/reply text, request IDs and
exception bodies are omitted. Dirty/tampered/unpaired/oversized bundles are
rejected; invalid judgments, missing provenance, provider failures and timeouts
cannot become PASS. Explicit user word limits are enforced even if the judge
passes the response. Deadlines are bounded; no automatic retry or deployment
loop exists.

## Validation

Final-SHA CI and the combined PR581/PR587 compatibility result are recorded in
the live PR description after verification. Counts overlap prior checkpoint
coverage and must not be summed. Offline fixtures establish harness behavior
only; actual generated quality, naturalness, latency through devices, durable
handoff delivery, live voice and production acceptance are NOT RUN under the
existing no-deployment/no-live-evaluation boundary.

Mem0/Letta/DSPy/LiveKit/DeepEval/TRL remain research candidates with no package
adoption, installation or activation in this increment. PR581's approved six
enrichments and the staged status of all other candidates remain unchanged.
