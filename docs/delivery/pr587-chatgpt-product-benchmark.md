# PR587: observed ChatGPT product benchmark protocol

This engineering protocol extends the existing provider-neutral scenario registry. It creates no second brain, provider call, quality result, training authority, prompt promotion, connector grant or customer-facing parity claim. Native guidance remains selected until existing DSPy evidence/promotion gates independently pass. The original 26-case/520-pair and multi-turn/DSPy baselines are unchanged.

## Three independently measured dimensions

The fixed behavioral registry supplies text-to-text, voice-to-voice and tool/action execution tasks. Execution tasks run from both text and voice. Existing cross-modal scenarios cover switching channels and reconnect/continuation. Every task has the same starting state and two independently captured product sessions; unsupported/non-comparable connector workflows are gaps, not fabricated comparable trials. The full protocol, task mapping, rubrics and thresholds are hashed together, so changing any of them invalidates old evidence.

Capture the actual contemporary ChatGPT product configuration: date/time, accessible model, voice mode, access and feature limits. Do not substitute an OpenAI API completion for an observed ChatGPT session. Pin the deployed Gravitre SHA and one shared device/network/environment fingerprint. Reference and Gravitre collection must occur within the same 24-hour window. No default ChatGPT configuration or observed score is supplied by code.

Each comparable task requires private, hashed JSON interaction evidence bound to its task, opaque A/B label, environment, observed capture method and completion outcome. It includes monotonically timestamped input/output/tool/approval/receipt/cancellation/channel-switch events as applicable. Voice and cross-modal tasks additionally require an actual WAV recording at least one second long. File presence, containment, byte hash and WAV format are validated. The same artifact cannot be counted as multiple trials. No recording, transcript, prompt, private file path, account identity or credential is copied into the resulting metrics report.

Two independent raters review each trial using opaque A/B labels and complete dimension-specific 1–5 rubrics. Keep the A/B identity file separate from the raters' manifest until scoring. The named review reference and rater references are opaque SHA-256 values. `blind_review_attested` is false by default. The report explicitly records that local integrity checks plus human provenance attestation do not independently prove a capture's product origin. Voice identifiability and differing integration coverage must be included in the human review's limitations.

## Internal acceptance thresholds

These are engineering thresholds, not measured results or customer claims. Every dimension independently needs at least three comparable tasks and 80% of its fixed task set. Gravitre must have zero failed safety invariants, at least 90% task completion, no more than a five-point percentage completion gap, no more than a 0.5-point mean quality gap, and P95 observed latency no worse than 1.2 times the reference plus 250ms. Voice latency is speech end to first audible meaningful audio, using the same device/network; digital text response timing is not a substitute. Missing observations, missing/duplicate cases, asymmetric comparability, fixtures, omitted ratings, absent recordings, altered files and unsafe outcomes cannot be averaged into a pass.

The report returns per-dimension PASS_MEASURED_SCOPE/FAIL/NOT_READY and a gap inventory. Overall status remains NOT_CERTIFIED unless every dimension passes. Even a complete report always sets `whole_product_equivalence_claim=false`: the evidence supports only its observed comparable tasks and recorded configurations. The report hashes the evidence manifest and reference configuration for reproducibility. It cannot activate a prompt, change memory consent or authorize an action.

## Execution after coordinated deployment

1. Emit an unscored template: `python scripts/run-conversation-parity-benchmark.py --product-template --out /private/benchmark/ratings.json`. Fill the observed configuration and private capture references; no template field is an observed result.
2. Capture each task in deployed Gravitre and accessible ChatGPT using controlled synthetic accounts/data. Record real tool outcomes, approvals/refusals, cancellation, scope/revocation and speech evidence. Never record authentication headers, cookies, API keys or unrelated user data. Keep recordings/traces in access-controlled storage under the evidence root.
3. Collect independent blinded human ratings and the explicit named review attestation. Keep `/private/benchmark/identity.json` (`A/B` mapped to `gravitre/chatgpt`, in randomized order) withheld while rating.
4. Score locally: `python scripts/run-conversation-parity-benchmark.py --product-score /private/benchmark/ratings.json --identity-file /private/benchmark/identity.json --evidence-root /private/benchmark/captures --out /private/benchmark/report.json`. Invalid/incomplete evidence produces NOT_CERTIFIED and a nonzero exit. No raw capture is uploaded by this command.
5. Review each dimension and non-comparable gap. Provider-quality and physical/reference voice acceptance remain NOT RUN until those observed sessions exist. Record the final report hash in the coordinated release record; do not claim ChatGPT equivalence.

The legacy `--template` mode remains unchanged and has its own output file. New deterministic contract tests use explicitly synthetic fixtures to verify validation/scoring behavior; their passing status is not a product quality result.
