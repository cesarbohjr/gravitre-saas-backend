# Stored dict coercion reverification (2026-09-04)

## Scope

Re-ran the structural bug-class audit for unguarded dict coercion on current backend code and verified the standing guard behavior.

Pattern class audited:

- `dict(x.get(...))`
- `dict(x["..."])`
- equivalent direct coercions where stored/retrieved payload shape may be non-dict

## Phase 1 — Exhaustive inventory (backend)

AST scan command (backend workspace scan):

```bash
python -c "<ast walk over backend/app/*.py finding dict(...) with .get() input or string-key subscript input>"
```

Findings before this pass:

1. `backend/app/services/sync_back_policy_service.py`
   - `dict(root.get(_SETTINGS_KEY) or {})`
   - risk: **legacy-shape-reachable** (`org_settings` payload is persisted settings; can be malformed, stringified, or partial)
2. `backend/app/services/sync_back_policy_service.py`
   - `dict(block.get("syncBack") or {})`
   - risk: **legacy-shape-reachable** (`department_pipelines.syncBack` is nested stored settings; can be missing/malformed)

All other backend files scanned: no unguarded `.get`/string-subscript dict coercion instances.

Post-fix scan result:

- `dict_get_hits=0`
- `dict_string_subscript_hits=0`

## Phase 2 — Shared helper refactor

Updated call sites to use shared normalizer:

- `backend/app/services/sync_back_policy_service.py`
  - added `from app.core.safe_dict import safe_normalize_stored_dict`
  - replaced
    - `dict(root.get(_SETTINGS_KEY) or {}) ...` with `safe_normalize_stored_dict(root, key=_SETTINGS_KEY)`
    - `dict(block.get("syncBack") or {}) ...` with `safe_normalize_stored_dict(block, key="syncBack")`

Fallback correctness for this site:

- returning `{}` for malformed/missing org settings is correct and consistent with default policy behavior (`syncTiming=immediate`), avoiding hard-fail during policy read/write.

## Phase 3 — Structural guard proof

Existing enforced guard:

- `backend/tests/lint/test_no_unguarded_dict_coercion.py`

Deliberate reintroduction proof:

1. Added temporary probe file with `dict(payload.get("params") or {})`.
2. Ran:

```bash
python -m pytest -q tests/lint/test_no_unguarded_dict_coercion.py
```

3. Guard failed as expected with explicit hit:
   - `app/_tmp_dict_guard_probe.py:2 [dict-get] payload.get("params") or {}`
4. Removed probe file.
5. Re-ran lint test; guard returned green.

## Phase 4 — Regression coverage

Executed focused regression suite for this bug class:

```bash
python -m pytest -q \
  tests/lint/test_no_unguarded_dict_coercion.py \
  tests/services/test_parameter_ledger.py \
  tests/services/test_pending_reply_classifier.py \
  tests/services/test_chat_connector_execution.py::test_plan_action_awaiting_params_legacy_string_args_does_not_raise \
  tests/services/test_chat_connector_execution.py::test_plan_from_dict_parses_json_args_string
```

Result:

- `44 passed`

Additional full-file run attempt including full `test_chat_connector_execution.py` surfaced an unrelated circular-import failure in department-pipeline WIP wiring (`sync_back_policy_service` <-> `department_pipelines.__init__/service`) not caused by dict coercion normalization itself.

## Phase 5 — Deploy verification

Pending in this report at creation time. Add run IDs and deployed `git_sha` after push/deploy completes.
