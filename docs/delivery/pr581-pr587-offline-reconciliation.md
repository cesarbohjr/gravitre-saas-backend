# PR581 / PR587 offline reconciliation

PR581 owns role and Marketplace packaging; PR587 owns shared intelligence, dialogue, memory, personality, continuity and voice. This continuation keeps both PRs open/draft and performs no merge, application deployment, live installation or provider request. Both project roots disable automatic Vercel deployment for both feature branches.

## Checkpoint review

PR587's `ff724c353533f853674dc353deb0e0654501d03e` full CI failed speculative-turn state equality because an imported `cognitive_loop_controller.uuid4` alias escaped the deterministic test fixture. `53057bb5e690e9d1809dd4edbcf1355164f36968` patches that call site. Full durable-state, write-set and task-state ordering assertions remain unchanged; the real PII redactor still runs. Three focused contracts passed with external network blocked.

PR581's continuation `6d78d17e4a91c1164c440e1777c32b07cff69c7a` preserves the original four enrichments and adds two bounded existing-agent enrichments, a publication-gap install/preview guard, matching manifest guidance in full and compact prompt builders, and native adapter intake/export boundaries. All other source candidates remain staged. Its 678 affected tests passed under the network guard.

The two checkpoint heads combine without conflicts. Joint tree `e57c54469afd48cfebc7bfd2145437955927cf29` ran 3,808 assertions successfully but reported **43 teardown errors**, so it was not a passing suite. The stricter offline guard exposed scripted voice tests that replaced the brain event stream but still attempted external OpenAI moderation and Supabase policy/budget reads. Every attempt was blocked before external dispatch. No live provider inference was needed or authorized for these unit contracts.

## External-source fixture fix

Ten scripted voice test modules explicitly opt into `scripted_voice_external_sources`. The fixture supplies an isolated `FakeSupabaseDB` for policy/budget reads and a synthetic moderation endpoint response. It does **not** mock guard functions or change production configuration. The real budget, model-policy and moderation decision code remains active. Narration, chunking, latency, interruption, speculation/adoption and state assertions are unchanged.

The fixture is not autouse and is not inherited by independent guardrail/refusal/billing/provider tests. Two regression tests prove that a blocked model policy and a flagged moderation response still trigger the real refusals while the fixture is active. CI runs the scripted modules plus those refusal contracts and independent AI guardrail/model-policy suites with the external-network guard. Separate full CI remains required on the final head.

The guard implementation is byte-identical to PR581's: transport checks precede proxy dispatch, with Python DNS/socket and Google gRPC protection; caught attempts still fail teardown. No network assertion or allowlist was relaxed.

## Acceptance limits

Exact final heads, full CI links and the replacement joint-tree results are recorded in the PR descriptions after verification. Old checkpoints and overlapping test counts are historical evidence only. Current CI and offline compatibility do not establish live provider quality, physical voice responsiveness, expressive naturalness, consented memory delivery, telemetry durability or deployed source-of-record outcomes. Those live gates are **NOT RUN — no deployment/live activation authorized by this continuation**.
