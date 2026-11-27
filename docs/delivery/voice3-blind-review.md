# Voice 3 blinded listening acceptance

Use only synthetic fixture audio and isolated acceptance credentials. The coordinator runs
`voice3_blind_review.py generate` with the exact-SHA catalog proposal and two new,
disjoint directories. Distribute only the public listening pack and review template
to at least three independent listeners. Keep the mapping key private; do not publish
it together with reviewer materials. Reviewers listen at comparable volume in a quiet
setting, replay as needed, and select A, B or equal for each dimension. Naturalness:
human-like rhythm and delivery. Emotion: fit to scenario. Warmth: appropriate interpersonal
tone, not maximum friendliness. Emphasis: meaningfully placed stress. Identity continuity:
perceived continuity of the paired voice, not biometric identity.

Coordinator confirms reviewer identity and independence outside the tool, collects
completed JSON forms, verifies the audio hashes and runs the score subcommand with
a JSON list of authorized reviewer IDs. The initial conservative rubric rejects any
inferior rating and blocks disagreement, missing evidence or ties without demonstrated
superiority on naturalness or emotional appropriateness for each protocol. Agreement is
raw pairwise exact agreement, not chance-adjusted reliability. Three reviewers are a
minimum pilot panel, not a statistically validated release population. Recognizable
voices may compromise blinding. Do not infer objective speaker identity or claim a
validated MOS from these judgments.

No automatic certification import is authorized by the score file alone. A trusted
coordinator must verify provenance and reviewer identity before any future gate import.
All production activation remains disabled. Fresh listening audio is synthesized for this
pack; it is not the identical recording used by the HTTP acoustic evaluator.
