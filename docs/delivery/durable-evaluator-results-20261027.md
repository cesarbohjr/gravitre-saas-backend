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

The clean frozen bundle is from `184beb2f060fc657f67277550bbeb884da932c39`:
ten personas, unified/classical paths, text/voice, 26 scenarios and 520 pairs.
The existing evaluator and rubric are unchanged. Compressed embedding is tested
to decode to the exact input bundle. A source evaluation explicitly retains
`production_certified=false`; the deployed-SHA production workflow gate remains.

Validation: eleven Node evaluator/storage contracts and two Python bundler
contracts passed; diff and bundled TypeScript parse checks passed. CI now runs
the new contracts. Bun/S3 integration and live generation require actual execution.

The replacement is staged as Railway patch
`2b1e4836-1fe0-4a98-b6ea-32f99ff0889d` (one source change). The immediate
deployment was rejected by automatic approval review; the subsequent staged
deployment action was cancelled by the approval tool. No new authentication or
520-pair run occurred during this increment. Bucket creation and its evaluator
references succeeded. No application deployment, memory rollout or certification
status was changed.
