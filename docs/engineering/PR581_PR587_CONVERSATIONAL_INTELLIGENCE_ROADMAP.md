# PR581 + PR587 — Conversational intelligence research and adoption roadmap

Status: **full engineering authorized for DSPy optimization/rollback, shared text/voice feedback and the previously approved Paid Media inventory**. The user's latest direct implementation instruction supersedes the earlier planning/package-install restrictions for this scope. Current engineering records are `docs/delivery/pr587-guidance-voice-feedback.md` on PR587 and `docs/engineering/PR581_PAID_MEDIA_IMPLEMENTATION.md` on PR581. Provider/physical/deployed acceptance follows the authorized release stage; both PRs remain open/draft and unmerged.

Historical research authorization below is preserved as history, not a restriction on the newly authorized implementation.

Original status: **approved for planning and controlled research only**. This record preserves the user-requested research in both draft PR branches. It is not approval to install packages, activate telemetry, change provider credentials, publish Marketplace SKUs, merge, deploy, or change production policies.

## Ownership and architecture
- **PR587 (owner):** shared seven-capability intelligence, dialogue/session state, conversation planning, personality and tone behavior, governed memory, consent, voice turn taking, text/voice parity, evaluation, feedback, and versioned optimization.
- **PR581 (consumer/compatibility owner):** approved specialist role manifests and exact reference guidance, Marketplace package/config/entitlement/connector lifecycle, and representative role-specific dialogue tests. No separate dialogue engine, memory store, selector, agent brain, or tool-grant semantics.
- **Existing Gravitre runtime:** authoritative authentication, tenant isolation, permissions, connector scope, approvals, quotas, versioning, and audited writes. Advisory memories, role guidance, retrieved documents, and evaluations must never grant tools or approve actions.
- PR581's six existing-agent enrichments are implemented. The separately approved Paid Media tranche remains a later scoped implementation increment after the shared memory/evaluation gates; this research checkpoint creates no Paid Media listing, campaign, price or spending permission. Other source candidates remain staged, and the excluded OrgScript role remains excluded. No framework installation or broad automatic profile publication is authorized.
- PR587's 26 cases × ten personas × unified/classical × paired text/voice (520 pairs) constitute an existing synthetic evaluation foundation, **not live voice certification**.

## Repository research register (no adoption decision implied)
| Candidate | Role in plan | Initial disposition | Repo |
|---|---|---|---|
| Mem0 | selective personalized long-term memory and retrieval | benchmark against existing governed memory | https://github.com/mem0ai/mem0 |
| Letta / Letta Code | persistent identity, evolving context and durable-state patterns | alternative benchmark; no autonomous memory or skill edits | https://github.com/letta-ai/letta ; https://github.com/letta-ai/letta-code |
| DSPy | versioned offline optimization of dialogue guidance against fixed evaluation objectives | evaluate as offline tooling only | https://github.com/stanfordnlp/dspy |
| Pipecat | streamed spoken conversation, interruption, silence and turn-taking | physical voice benchmark | https://github.com/pipecat-ai/pipecat |
| LiveKit Agents | speech pipeline and semantic end-of-turn / interruption | benchmark against Pipecat and existing voice path | https://github.com/livekit/agents |
| DeepEval | repeatable conversational retention, consistency and completion scores | evaluation candidate | https://github.com/confident-ai/deepeval |
| Langfuse | sanitized experiment metrics, observability and comparison | extend PR581 opt-in native metrics boundary only after authorized review | https://github.com/langfuse/langfuse |
| LangGraph | durable orchestration and state patterns | architectural reference, no second runtime | https://github.com/langchain-ai/langgraph |
| Hugging Face TRL | SFT / DPO and preference training of open-weight models | deferred until consented curated corpus and an owned serving case | https://github.com/huggingface/trl |

All third-party licenses, versions, APIs, data-handling terms and dependency/security posture require pinning and review before incorporation. No project is adopted by adding it here.

## Incremental implementation plan
1. **Current PR reconciliation:** certify existing PR581 six enrichments, provenance/rendering, published snapshot integrity, canonical install/upgrade/rollback, connector/entitlement/IAM denial, and PR587 combined-tree compatibility. Final-head CI must be green before changing merge status. Preserve current no-deployment boundary.
2. **PR587 conversational baseline:** reuse existing 520 synthetic paired cases; add multi-turn tests for intent, non-repetition, corrections, response length, naturalness, social awareness without fabricated emotions, role consistency, uncertainty, tool selection, and governed handoff. Record evaluator version, dataset hash, response provenance, cost/latency, category scores and negative security outcomes. Keep simulated and live separate.
3. **Governed memory benchmark:** compare current retrieval to Mem0 and Letta in an isolated test harness. Evaluate consent (default off until configured), scope, user-fact vs inference labeling, freshness, false memory resistance, update/correction, deletion, retention, tenant crossover denial, prompt-injection quarantine and rollback. No uncontrolled self-editing or external memory transfer.
   Current checkpoint: 26 canonical governance reference cases plus pinned Mem0/Letta source audit and research contracts. Candidate SDK/runtime comparisons remain NOT_RUN; no ranking or adoption decision is claimed. See `scripts/memory_benchmark/README.md` for exact boundaries. The user-directed sequence starts with memory/evaluation infrastructure, then later agent tranches; Paid Media approval is preserved without inferring advertising execution authority.
4. **Offline behavior optimization:** evaluate DSPy on curated, consent-appropriate cases; promote only a versioned, human-reviewed prompt/guidance candidate through CI, with measurable improvement against an untouched baseline and no regressions in factuality, security, permissions or role boundaries.
5. **Physical voice certification:** benchmark Pipecat and LiveKit against existing Gravitre speech pipeline on real speech: first-token/speech latency, word-error context, end-of-turn accuracy, interruptions/barge-in, silence, corrections and confirmed write cancellation. Prove an interrupted or revoked confirmation **prevents the write**, not just delayed text. No voice-provider rollout by default.
6. **Evaluation feedback loop:** use DeepEval and Langfuse only with sanitized evidence, opt-in export and tenant-scoped retention. Require durable outcome manifests, judge validity, provider status/error categories, bounded retries, privacy redaction, baseline delta and reviewed version promotion/rollback. Langfuse submission != durable receipt.
7. **Optional fine-tuning:** defer TRL/weight updates until a documented consented corpus, provider/model ownership, privacy review, cost-benefit benchmark, deployment rollback, and separate product approval exist.
8. **PR581 role smoke matrix:** after PR587 interface changes, validate at least content-writer, seo-analyst, sdr-coach, ticket-triage, revenue-operations-agent, competitor-research-agent via shared text/voice paths; ensure existing persona, systems, grant counts, pricing and published entitlement remain unchanged. No source persona text is executable authority.

## Acceptance and release boundaries
- Each item is a separately reviewable future increment, not a prerequisite retroactively added to either PR's current scope.
- Exact pinned dependency versions and license/security review, migration/rollback plan, deterministic/offline regression suite, consent/privacy controls, negative cross-tenant tests, human write approvals and final-head CI are required before any production adoption.
- Live voice, telemetry and provider evaluations require separately authorized isolated environments and real observed evidence. No synthetic result is called a production PASS.
- **Open questions:** baseline quality thresholds; memory product UX/retention and deletion policy; consent/data residency; selected voice provider and SLA; allowed telemetry fields and verified delivery; adoption vs internal reimplementation; compute budget; fine-tuning dataset/model economics. Preserve these as unknowns pending explicit decisions.
- Keep PR581 and PR587 **open and draft**; no merge, publication, installation or deployment authorized by this document.
