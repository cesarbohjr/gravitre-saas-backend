# Stored dict coercion hardening verification (2026-08-07)

## Local regression matrix

### Matrix A

Command:

```bash
python3 -m pytest -q \
  tests/lint/test_no_unguarded_dict_coercion.py \
  tests/services/test_pending_reply_classifier.py \
  tests/services/test_parameter_ledger.py \
  tests/services/test_chat_connector_execution.py \
  tests/services/test_chat_orchestration.py \
  tests/services/test_conversational_execution.py \
  tests/services/test_extension_bridge_service.py \
  tests/workflows/test_execution_engine.py \
  tests/workflows/test_builder_sync.py \
  tests/workflows/test_digital_twin.py \
  tests/workflows/test_workflow_schedule_repository.py \
  tests/connectors/test_apollo_api.py \
  tests/connectors/test_clay_api.py \
  tests/connectors/test_confluence_oauth.py \
  tests/connectors/test_generic_oauth_registry.py \
  tests/connectors/test_google_analytics_oauth.py \
  tests/connectors/test_google_calendar_oauth.py \
  tests/connectors/test_google_vendor_oauth.py \
  tests/connectors/test_health_monitor.py \
  tests/connectors/test_hubspot_oauth.py \
  tests/connectors/test_jira_oauth.py \
  tests/connectors/test_marketo_oauth.py \
  tests/connectors/test_netsuite_oauth.py \
  tests/connectors/test_notion_oauth.py \
  tests/connectors/test_pagerduty_oauth.py \
  tests/connectors/test_quickbooks_oauth.py \
  tests/connectors/test_salesforce_oauth.py \
  tests/connectors/test_slack_oauth.py \
  tests/connectors/test_workday_oauth.py
```

Result: `187 passed, 3 warnings in 4.97s`

### Matrix B

Command:

```bash
python3 -m pytest -q \
  tests/connectors/test_pagerduty_api.py \
  tests/services/test_agent_handoff.py \
  tests/services/test_meta_learning_wave_d.py \
  tests/services/test_task_classifier_honesty.py \
  tests/services/test_voice_expression_range.py \
  tests/services/test_agent_role_marketplace_service.py \
  tests/services/test_partner_marketplace_service.py \
  tests/services/test_marketplace_billing_service.py
```

Result: `56 passed, 1 warning in 1.87s`

### Guard probe proof

1. Temporary probe file added with `dict(payload.get("params") or {})`.
2. `python3 -m pytest -q tests/lint/test_no_unguarded_dict_coercion.py` failed as expected (guard fired).
3. Probe file removed.
4. Same lint command passed (`2 passed`).

## Static inventory and zero-hit confirmation

- Full pre-refactor inventory: `docs/delivery/stored-dict-coercion-inventory-2026-08-07.md`
  - 423 total candidates
  - 194 `.get(...)` dict coercions
  - 229 subscript-based dict coercions
- Post-refactor AST scan:
  - `dict_get_hits 0`
  - `dict_string_subscript_hits 0`

## Merge + deploy

- Merged to `main` at `d191b12f196cac66052468cbe87d513b0755fd28`
- PR #186 merged with merge commit `d191b12f196cac66052468cbe87d513b0755fd28`
- GitHub Actions run `31147785709` (`Railway backend production`) completed `success`
- Deployment health gate observed production health `git_sha` reach `d191b12f...`
- Post-deploy chat smoke verdict: `PASS — post-deploy chat ok @ d191b12f`

## Additional live workflow notes

- `Chat history hygiene live` run `31147785712` failed before deploy converged to new SHA, reporting:
  - verdict `FAIL`
  - `git_sha` still `38e75e75...`
  - operator list latency 3340ms vs budget 2000ms
