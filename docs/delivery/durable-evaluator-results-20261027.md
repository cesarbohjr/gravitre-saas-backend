# Durable sanitized evaluator results

The old probe emitted structured JSON attributes with an empty message. Railway
deployment `1554f3d1-543a-47c8-b75d-073855015db2` did retain results: Anthropic
HTTP 200 with nonempty output, OpenAI HTTP 401. Blank plain-text lines were not
proof that execution results were absent. No newer authentication result is
claimed by this report.

The replacement uses the existing isolated `phase2-social-evaluation` Function,
without an HTTP listener or application/database credentials. A private Railway
bucket named `certification-evidence` stores run manifests and numbered sanitized
events. Only that evaluator receives bucket variable references; inference keys
were not read, replaced or copied by this increment.

The initial manifest and every event are written then read back. Each invocation
has a unique UUID and prompt-source commit prefix. Final PASS requires every
expected unique pair and matching counts. Storage failure, mismatched readback,
duplicate pair, incomplete summary and aborted execution cannot become PASS.
An abort writes a durable ERROR manifest when storage remains available. A
container terminated before finalization leaves RUNNING, which is not a pass.

Artifacts omit raw replies, prompts, headers, exception messages, provider bodies,
credentials and signed URLs. They retain fixed status/error categories, pair
identities, counts and boolean rubric results. Review of actual generated wording
requires separate authorized synthetic-reply capture; these diagnostics do not
claim human quality review. Progress and summary messages have visible fixed
prefixes rather than relying on Railway's structured attribute view.

The deployed clean frozen bundle is from `5bb1789170b2729677aefe8042edb96b5691f76b`:
ten personas, unified/classical paths, text/voice, 26 scenarios and 520 pairs.
The existing evaluator and rubric are unchanged. Compressed embedding is tested
to decode to the exact input bundle. A source evaluation explicitly retains
`production_certified=false`; the deployed-SHA production workflow gate remains.

Validation: eleven Node evaluator/storage contracts and two Python bundler
contracts passed; diff and bundled TypeScript parse checks passed. CI now runs
the new contracts.

## Successful activation

Deployment `df506122-dcfd-407c-9097-7b32cbee739e` reached SUCCESS at
2026-10-27 22:23 UTC. Function source readback matched the complete 50,326-character
runner exactly, including its durable completion path; no staged changes remain.
Packaging now uses Node's built-in Brotli across the full bundle, reducing source
from approximately 303 KB to 50 KB while preserving the exact decoded JSON.
The round-trip contract checks reconstruction; no prompts or rubric were altered.

Payload SHA-256: `a036bf11c971f0c51c8246278f6d13eaf15c21a2611269cf64fe3abf57958c89`.
Run UUID: `66d138a3-ebc4-4911-81bf-a2657a66c2c6`.
Private evidence prefix:
`runs/5bb1789170b2729677aefe8042edb96b5691f76b/66d138a3-ebc4-4911-81bf-a2657a66c2c6/`.

`EVAL_EVIDENCE_READY` confirms the initial private manifest was written and read
back. Anthropic inference returned HTTP 200 with nonempty output; OpenAI returned
HTTP 401. The 520-pair Anthropic suite started and reported its first twenty
completed pairs. This is a running evaluation, not a final suite PASS.
No application deployment, memory rollout, merge or production certification was
performed by this activation.
