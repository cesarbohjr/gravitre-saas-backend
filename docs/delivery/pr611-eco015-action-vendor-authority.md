# ECO-015: action registration must belong to the connector

Base: PR #611 at `37c49bb280cd07fe95c65b68caf1a254257efe79`.
The register's original acceptance criteria and all closure flags remain in force.

## Source/caller trace

| Path | Readiness authority and limitation |
| --- | --- |
| Connector router `_connector_response_item` -> `evaluate_connector_availability` | Account display/auth state; normally no action key. A connected account is not proof of any particular action's OAuth permissions. |
| ChatConnectorExecutionService `_verify_plan_executable` -> `find_integration_availability` -> list/evaluate | Supplies `plan.integration` and `plan.invoke_action`; gates `process_turn` before the execution/approval path. Actual verifier exercised in this regression. |
| Chat unresolved-turn and Apollo-list readiness paths | Vendor-level availability, no action key. Source traced; not all caller branches executed here. |
| AgentIntelligence connector-unavailable clarification | Vendor-level error taxonomy and recovery message; no per-action authorization claim. |
| ToolRegistry `list_connected_integrations` -> cached snapshot -> executable listing | Supplies org, environment, force-live and optional action key. Consumers include assistant knowledge retrieval and the Pipecat bootstrap. Snapshot/freshness parity is not established by this batch. Voice implementation remains PR #610. |
| Recipient resolution executable-integration listing | Source traced as a vendor-discovery consumer; no provider acceptance in this batch. |

The evaluator obtains health via `resolve_connector_auth_status`, separates
configured/authenticated/token/scope/display state, and requires a registered
action when an action key is supplied. Native HubSpot has seven explicit
action-scope requirements. Existing tests already reject missing/malformed grants
for those known actions without disconnecting account-level listings. Managed
non-native connectors additionally require their existing executor allowlists.
Neither that limited scope table nor account-level listing establishes complete
per-provider scope coverage. No OAuth metadata, scope requirement or managed
allowlist is weakened here.

## Confirmed preflight defect

On unmodified source, a synthetic connected HubSpot row with only contacts-read
permission returned `execution_available=true` for both genuinely registered
`gmail.messages.list` and `gmail.messages.send`. The actual chat plan verifier
returned None (no blocker) for those mismatched plans.

The regression produced **2 failed, 41 passed** together with the existing
availability/connected-filter suites. Both failing tuples were `(True, True)`
instead of `(False, False)` for `(availability_ready, verifier_has_no_blocker)`.
The correctly owned `hubspot.contacts.search` control passed.

Cause: membership in the global invoke registry was treated as membership in
every connector's action set. This is a readiness/plan-preflight gap. No provider
was invoked, and no claim is made that downstream credential, permission or write
approval gates could be bypassed. A mismatched plan was constructed directly;
production model/persisted-plan occurrence remains unproven.

## Bounded repair

`_registered_action_matches_vendor` first requires actual global registration,
then validates the connector namespace or declared catalog ownership. It reuses
the existing Google prefix-alias table and execution matrix for exact aliases
(Outlook -> Microsoft365 mail) and native ownership. It does not grant Outlook
the entire Microsoft365 namespace. Existing HubSpot-CRM and Google Ads aliases
remain recognized. Unregistered names still fail closed.

The evaluator uses this check in place of global registration alone. Existing
health/scope/availability gates, org/environment arguments, managed executor
allowlists, approval and invoke guards remain intact. Connected-account display
stays connected while a foreign action is blocked as unsupported.

## Local verification

**142 tests passed**, normal backend conftest loaded:

```text
tests/connectors/test_eco015_action_vendor_authority.py
tests/connectors/test_connector_availability_service.py
tests/master_qa/test_connector_connected_filter.py
tests/services/test_react_write_gate.py
tests/services/test_react_write_gate_catalog_authority.py
tests/services/test_chat_connector_execution.py
tests/services/test_connector_execution_matrix.py
tests/services/test_assistant_availability.py
tests/services/test_action_availability_honesty.py
```

The new tests cover foreign Gmail read/write rejection, correctly owned HubSpot
readiness, Google/HubSpot/Outlook aliases, namespace-negative cases, unregistered
actions, and all **783 registered catalog ownership pairs**. The actual evaluator,
availability lookup and chat verifier execute; only connector/OAuth storage and
health are synthetic in the reproduction. No model or external provider runs.
Proxy variables were unset for this task's Python environment (socksio absent).

## Publication prerequisite and remaining gates

All ten hosted PR workflows passed on the base SHA, including
[Core45095846435](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45095846435),
[Operations45095846507](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45095846507),
and [QA1245095846420](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45095846420).
Core's five required checks all passed; backend logged **17,473 passed, 64 skipped,
14 subtests passed**. QA12's independently downloaded artifact14783881237 reports
matching base SHA, 20 real PostgREST cases passed, zero skips, whole-finding
certification false. ZIP SHA256:
`2a4fc1e2dc80e2548bbac6211bc09e82dd0dc464324ee68a768aa9d03d896603`.
This base CI does not verify the new ECO-015 source change.

Fresh exact-head hosted CI is required after publication. Deployed caller parity,
complete provider scope coverage, native/managed precedence, cache freshness,
independent provider/persistence receipts and rollback/owner criteria remain open.
Skipped live/provider/billing jobs and physical-device placeholders are not
acceptance. No merge, deployment, live dispatch, provider write, migration or
retirement is performed. Both audit stores and twelve installed workflows remain.
**0/43 findings certified closed**.
