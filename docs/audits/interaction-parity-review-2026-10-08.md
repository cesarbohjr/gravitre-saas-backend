# Interaction parity review — 2026-10-08

Status: NOT VERIFIED at the required live product standard. Reports from Claude are distinguished from this review's independently observed evidence.

## Text

Production incident: HubSpot company count → identical resend → “Ok do that”. First request ad1f57c8-9c57-4a3b-a259-b66663e2079b; resend e883b0b6-e0e9-4a96-8ee3-9bf6c8a4f6e6; continuation 48a449d9-463d-4e26-8f66-f7c29625ea4c. Conversation 0bcb4ffa-84eb-4ac5-b522-b0ea22df83e4.

| Measure | Original | Resend | Continuation |
| --- | ---: | ---: | ---: |
| HTTP middleware timing, ms | 3897 | 1820 | 526 |
| Planning stage, ms | 20356 | 116 | 4857 |
| Stream timer total, ms | 21858 | 1686 | 6675 |

These are server measurements, not browser perceived latency. first_token=0 is not usable evidence of immediate output; this instrumentation does not establish time to first useful content.

Observed failures: web content about companies using HubSpot was retrieved for a private account-count question; one CRM result was read without a total; the resend repeated a cached incomplete response without tools; the confirmation selected analytics rather than the count. Messages were saved at completion; refresh before completion saw zero messages and no completed replay.

Implemented remediation: company counts use sealed hubspot.companies.search with a createdate HAS_PROPERTY filter and provider total; a returned page without an integer total is blocked from becoming an account count; live business reads bypass answer caching; a short read continuation resolves to the nearest concrete request and cannot override pending approval; missing capability no longer defaults to analytics. Listing execution uses io_pool off the event loop.

Post-fix live deployment/result: NOT VERIFIED. Browser refresh recovery and accepted-task durability: NOT VERIFIED; not implemented by this patch. No external writes were performed during investigation.

## Voice

Claude PR #326 reports synthetic speech-end-to-audio improvement and interruption fixes. PR #327 explicitly says real speech/audio hardware was not verified. PR #329 reports a synthetic real-pipeline bench with network faked: medium first answer token p50 4.9 s and deep 8.3 s. Deep first-audio timing mostly measures an acknowledgement. This is not production speech-to-answer proof and medium latency remains above its stated 1–2 s target.

Independently measured live speech timing, interruption, silence/dead air, tool-progress announcements, and hardware playback: NOT VERIFIED in this review. No microphone/audio hardware test was performed. Human comparative evaluation against ChatGPT/Claude: NOT VERIFIED.

Code inspection confirms Pipecat calls execute_task_streaming(spoken_mode=True), shared guardrails, and shared cognitive kernel. Speech context/tier differences still require objective and permission equivalence tests against the owner tenant. The repaired read routing is shared with text, but that alone is not live voice acceptance.

## Cross-modal equivalence

The existing objective parity suite uses an in-memory PostgREST store and patched connector inventory/research availability. It validates planner behavior for disconnected providers, entitlement distinctions, objective corrections and declarative department packs. It does not validate actual STT, TTS, production transport, real approvals, provider mutations, or verified business outcomes.

Required live paired scenario: same tenant baseline, typed then spoken company-count and lead-generation requests, correction to Canadian MSPs with 20–100 employees, disconnected Apollo/Clay, connected-but-not-entitled Apollo, approval/rejection, provider failure, refresh/reconnect during execution. Compare objective, capabilities, resources, plans, governance, observations and verified outcomes. All live paired results remain NOT VERIFIED.

## Database evidence

Read-only production checks independently confirmed all four intelligence_outcome_events_play_* indexes valid and ready, connector_action_availability present with RLS enabled, validated state check and named org policy, and org_metric_definitions.definition as non-null jsonb. This proves structural installation, not enforcement behavior or tenant isolation under authenticated sessions.

## Test evidence

Combined focused run after the final code changes: 127 passed (gateway, objective, reference, listing, text/voice task parity, canonical ingress, replay, incident and traffic/replanner). Syntax compilation and git diff --check pass.

Full regression attempts initially stopped at missing environment dependencies (Temporal/SAML/Pipecat/SOCKS); those were installed locally without changing repository requirements. The subsequent wider voice run invoked an unmocked request to api.openai.com and automatic approval review rejected it because test/runtime data could leave the environment. Wider pytest processes were stopped. The full regression and those voice tests are NOT VERIFIED; the rejection was not bypassed. Approved live-provider testing or a separately reviewed, fully mocked suite is needed before those gates can pass.
