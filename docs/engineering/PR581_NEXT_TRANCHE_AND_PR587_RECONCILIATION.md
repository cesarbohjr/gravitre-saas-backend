# PR581 continuation: review, shared-brain compatibility and native adapters

## Authorization and checkpoint review

The user authorized review of PR581's `db01409fa2c45e68ed643004eec9d04065c6ca81` checkpoint, reconciliation with PR587, selection/certification of a next small tranche and continuation of OpenHands → Browser Use → Langfuse. Both PRs stay open/draft. No merge, deployment, live install, production migration or paid runtime is authorized by this checkpoint.

Review found an interrupted-publication gap: an enrichment's catalog pointer could advance before its version snapshot was marked published. Current-version installs and previews now reject missing, unpublished or mismatched enrichment snapshots, including force installs. A repeated identical seed safely completes a matching pending snapshot without minting another version. Historical install selection continues to use published snapshots and current entitlement/visibility. Failure-injection tests retain these requirements.

## Next approved small tranche

Selection is made under the user's explicit instruction to approve the next small tranche. These are bounded enrichments of two existing agents; no new SKU, price, persona, capability or permission is added.

| Source role | Existing agent | Required connector | Scope |
|---|---|---|---|
| Pipeline Analyst | `revenue-operations-agent` | Existing HubSpot prerequisite | Pipeline health, evidence-based hygiene and forecast assumptions; no fabricated commitments or CRM writes |
| Trend Researcher | `competitor-research-agent` | Existing HubSpot prerequisite | Source-dated market/competitor findings, uncertainty and validation questions; no browser/scraping entitlement |

Immutable Agency Agents revision remains `b37b5bb33b78f2c1d6567d98e25ca818e3259219`, MIT. Source paths/hashes are checked against the previously audited inventory; the new specs carry `PR581:user-authorized-next-small-tranche`. The original four retain their original approval references unchanged. All six use exact-reference rendering, canonical installs and the same parameterized lifecycle/security tests. Revenue Operations retains its existing HubSpot/Salesforce systems; its initial default-grant count is therefore two, and tests require that exact count to remain unchanged through upgrade/rollback. This is not a grant expansion.

The source census stays immutable/proposed. All other 277 source roles remain staged (including the excluded OrgScript role). Its old proposed Trend Researcher disposition does not authorize a separate listing: only the existing-agent enrichment is approved. Review-only source previews remain unseedable.

## PR587 reconciliation

PR587 head reviewed: `ff724c353533f853674dc353deb0e0654501d03e`. Its actual full CI had one failure in speculative-turn durable-state parity, caused by a directly imported `cognitive_loop_controller.uuid4` alias escaping the test's stable UUID fixture. PR587 now patches that actual call site as well. It retains full durable-state, write-set and ordering assertions, and the real PII redactor. Three parity contracts passed with external network blocked. This is a fixture fix, not a production redaction change. Automatic Vercel deployments are disabled for both feature branches in both project roots.

PR581 owns declarative role/Marketplace packaging; PR587 remains owner of shared intelligence, dialogue, personality, memory, session continuity and text/voice orchestration. No second router or brain is introduced. Both canonical agent prompt builders now render the same bounded manifest role guidance for exact registered roles; unknown roles receive none. Six enrichment references render identically in full/classical and compact/unified/voice prompt builders and disappear on baseline rollback. A four-role × four-availability-state matrix checks all seven evidence slots through the shared context collector. Joint-tree testing combines both unmerged heads locally; it is compatibility evidence, not a remote merge or deployed-SHA certification.

Live provider, expressive voice, physical interruption and deployed-source-of-record certification remain separate release gates. This continuation does not reuse PR587's earlier live credential checks or partial evaluator counts as a PASS.

## Gravitre-native adapters, in the approved order

`app/services/native_agent_adapters.py` implements narrow host-callable boundaries with no dependency installation or background activation:

1. **OpenHands:** native v1 scoped observations become canonical `ExecutionPlan` review/clarification steps. Commands, patches, external success claims and tool keys cannot become executable actions. The caller must validate evidence and separately use existing governed planning/execution for any change.
2. **Browser Use:** native v1 scoped observations become the same review-only plans. Exact caller-approved HTTPS hosts are required; credentials, invalid ports and malformed URLs fail closed. Query/fragment data is dropped. No browser is launched, URL fetched or session reused. Navigation, redirect, sandbox and outbound-network enforcement are requirements of a future separately configured worker, not claims made by this intake adapter.
3. **Langfuse:** an injected configured client may submit an allowlisted metrics-only observation using `start_as_current_observation`. Export is disabled without an explicit matching per-run permit. It sends a keyed HMAC correlation reference, schema version, enum status and bounded integer duration only. It excludes prompts, replies, source records, raw identity, provider errors, URLs and credentials. Submission failure is explicit and does not change the business run. `submitted` does not mean verified durable delivery.

These adapters are callable application boundaries, not Marketplace listings, hosted runtimes, new action registrations or claims of full upstream SDK compatibility. Native artifact schema v1 requires authenticated `org_id`, `agent_id`, `run_id`, integer `schema_version: 1` and 1–50 `observations` with string `summary` (plus `url` for browser evidence). Caller scope must come from authenticated intake; copying provider-supplied identity into the trusted scope would defeat the boundary. No user-facing enable control is added.

### Upstream compatibility audit (reference only; no code vendored)

| Repository | Inspected immutable revision | License | Finding |
|---|---|---|---|
| `OpenHands/OpenHands` | `6354932e87f99e1583f482f2cea49d6d573443e0` | MIT | Current README describes Agent Canvas/ACP and multiple backends; do not assume the old Python runtime API or run unsandboxed |
| `browser-use/browser-use` | `2cc71890e65056b67fdb29d98bb407749c15bb08` | MIT | Local and hosted paths differ; preserve Gravitre identity, session and tool policy before worker adoption |
| `langfuse/langfuse-python` | `b483bd06ae7953e16f1f50d5a0316de3bb2aaaec` | MIT | Current observation interface replaces legacy trace/span clients; no legacy API imported |

Repository READMEs and LICENSE files were inspected at these revisions. No transitive dependency or executable upstream code is adopted; a future worker/SDK installation still requires package/security review, sandbox configuration and its own certification. Mem0/LlamaIndex remain benchmark-only; LangGraph/CrewAI remain evaluation-only.

## Certification record

The dedicated CI offline gate includes the native-adapter and shared-prompt matrix contracts. Standalone PR581, PR587 and joint-tree results and exact final SHAs are recorded on the live PR descriptions. Required full CI remains authoritative; prior checkpoint CI does not certify new code. Live installation, runtime launch, telemetry delivery and production acceptance are **NOT RUN — explicit no-deployment/no-live-install boundary**.
