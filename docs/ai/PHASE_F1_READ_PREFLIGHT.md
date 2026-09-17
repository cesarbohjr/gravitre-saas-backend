# Phase F1 — Canonical Action Compilation + READ Preflight

**Status:** structural closure (local). Live Google / QBO / Zendesk remain EXTERNAL_BLOCKED until those connectors are connected on the isolated test org.  
**Date:** 2026-09-17

F1 leftovers closed in the F2 increment (still no WRITE/G8/slice expansion): sole-connected CRM prompt policy, invoke audit fields from PreflightResult, analytics traffic overview primary report through `preflight_read_action` + `invoke_tool`.

See `docs/ai/PHASE_F2_READ_REPAIR.md` for the next runtime phase.

## ActionSpec ownership

Option B: `f1_read_slice.py` is **build-time augmentation only**. `get_vendor_catalog()` materializes F1 fields onto the existing catalog `ActionSpec` and stamps `spec_revision`. `get_action_spec()` returns that **one** object. If `vendor_definitions` later sets the same fields, catalog values win. ReAct / workflow / preflight / executor must not import `_OVERLAYS`.

## Trusted preflight proof

Typed `ToolContext.preflight_result` only. HMAC binding: org_id, plan_id, step_id, action_key, connector_id, resource_id, compiled parameters, spec_revision. `_preflight_ok` in params is stripped and never trusted. Missing proof → `PREFLIGHT_REQUIRED`. Mutation → `PREFLIGHT_STALE`.

Default traffic window without a time phrase: ActionSpec default (rolling 30d / `30daysAgo`). Documented. `last month` / `previous month` / `last calendar month` / `in August` / `August 2026` resolve to the previous or named calendar month, never rolling 30d.
