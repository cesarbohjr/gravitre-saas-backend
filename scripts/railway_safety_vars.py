#!/usr/bin/env python3
"""Audit and plan the Gravitre 3.0 Plus safety variables on Railway.

Reads ``railway variables --json`` output and checks the 21 3.0 Plus settings
against backend/app/config.py. It prints flag values (they are not secrets) and
only set/unset for secrets. Exit codes:

  0  nothing conflicts; ``--plan-out`` lists the ``KEY=VALUE`` pins to add
  1  a variable would block startup or is not at its safety value

Pins are only ever added for variables that are absent. A variable that is
present with a different value is reported, never overwritten: turning a live
flag off is an owner decision, not cleanup. No pin sets a flag to true.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Pinned explicitly: safety settings whose decision should be visible in Railway.
SAFETY_PINS: dict[str, str] = {
    "DOMAIN_EVENT_RELAY_ENABLED": "false",
    "SOURCE_PURGE_DRY_RUN": "true",
    "CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT": "false",
    "SOURCE_DELETION_PROPAGATION_ENABLED": "false",
    "KNOWLEDGE_RETENTION_PRUNE_ENABLED": "false",
    "RETRIEVED_CONTENT_GUARD_ENABLED": "false",
    "RAG_WORKER_PILOT_ENABLED": "false",
}

# Owner-approved production values that differ from the safety pin. A present
# variable at its approved value is reported, not a problem. Absent ones are
# still pinned to the code default, so ``apply`` never turns anything on.
APPROVED_VALUES: dict[str, str] = {
    # Read-path filter only (no writes or deletes); owner decision 2026-10-12.
    "RETRIEVED_CONTENT_GUARD_ENABLED": "true",
}

# Default-off flags the owner approved switching on (2026-10-13, "safe subset"):
# read-path context ranking only, no customer data and no writes. On is reported,
# not a problem; absent is still fine.
APPROVED_ON: frozenset[str] = frozenset(
    {
        "CROSS_SOURCE_CONTEXT_LIVENESS_V1",
        "CROSS_SOURCE_CONTEXT_FRESHNESS_V1",
        "CONTEXT_ENGINE_WORK_STATE_V1",
    }
)

# Left absent: each defaults to off in config.py, and absent is the safe value.
DEFAULT_OFF: tuple[str, ...] = (
    "RAG_INGEST_CHECKSUM_SKIP_ENABLED",
    "ENTITY_WRITER_ENABLED",
    "ENTITY_OBSERVATIONS_ENABLED",
    "ENTITY_CONTEXT_CARDS_ENABLED",
    "ENTITY_BEHAVIOR_SIGNALS_ENABLED",
    "ACCOUNT_HEALTH_ENABLED",
    "CHURN_ENTITY_FEATURES_ENABLED",
    "ACCOUNT_PLAY_PROPOSALS_ENABLED",
    "GOAL_LINKS_ENABLED",
    "WORK_OBJECT_PROPOSALS_ENABLED",
    "WORK_LOOP_LINKS_ENABLED",
    "PLAY_SIGNAL_EVALUATION_ENABLED",
    "RECOMMENDATION_FEED_ENABLED",
    "ACCOUNT_FEED_UNIFIED_V1",
    "ML_PREDICTION_OUTCOMES_ENABLED",
    "OUTCOME_LEARNING_HANDLER_ENABLED",
    "ML_TIME_SPLIT_ENABLED",
    "CROSS_SOURCE_CONTEXT_LIVENESS_V1",
    "CROSS_SOURCE_CONTEXT_FRESHNESS_V1",
    "CONTEXT_ENGINE_OBSERVATIONS_V1",
    "CONTEXT_ENGINE_ACCOUNT_SIGNALS_V1",
    "CONTEXT_ENGINE_WORK_STATE_V1",
    # Lineage tags, read-time revoked-source filter, cache invalidation on revoke
    # and the memory/observation purge (PR #374). Needs migration 20261012070000
    # first: before it, recall returns no memories (the filter fails closed).
    "MEMORY_SOURCE_LINEAGE_ENABLED",
)

# A str setting; absent and empty both mean "no pilot orgs".
PILOT_ORG_IDS = "RAG_WORKER_PILOT_ORG_IDS"

# Required in production (config.py validator); reported as set/unset only, never printed.
REQUIRED_SECRETS: tuple[str, ...] = (
    "INTERNAL_API_SECRET",
    "CONNECTOR_SECRETS_ENCRYPTION_KEY",
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
)
OPTIONAL_REPORTED: tuple[str, ...] = ("TEMPORAL_HOST",)

# Emergency stop for customer-data ingestion (default off). Reported with its
# value, never pinned: true is a deliberate stop, not a misconfiguration, but it
# pauses every knowledge sync, so it must be visible.
KILL_SWITCH = "DISABLE_INGESTION"

# Context delivery settings (pre-3.0 Plus): reported with their values, never
# pinned and never a problem. Absent means the code default applies.
CONTEXT_REPORTED: dict[str, str] = {
    "UNIFIED_TURN_LIVE_ENABLED": "false",
    "UNIFIED_TURN_SHADOW_ENABLED": "false",
    "CROSS_SOURCE_CONTEXT_ENGINE_ENABLED": "false (shadow only)",
    "CROSS_SOURCE_CONTEXT_ENGINE_SHADOW_ENABLED": "true",
    "CROSS_SOURCE_CONTEXT_TOKEN_BUDGET": "12000",
}

_TRUE = {"1", "true", "yes", "on", "t", "y"}
_FALSE = {"0", "false", "no", "off", "f", "n"}


def _bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    return None  # pydantic rejects it, including "" (startup fails)


def audit(env: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """Return (report lines, problems, pins to add)."""
    lines: list[str] = []
    problems: list[str] = []
    pins: list[str] = []

    for key, safe in SAFETY_PINS.items():
        if key not in env:
            pins.append(f"{key}={safe}")
            lines.append(f"{key}: absent (default is safe) -> pin {safe}")
            continue
        parsed = _bool(env[key])
        if parsed is None:
            problems.append(f"{key}={env[key]!r} is not a boolean; startup would fail")
        elif key in APPROVED_VALUES and parsed == (APPROVED_VALUES[key] == "true"):
            lines.append(f"{key}={env[key]!r} (owner-approved)")
            continue
        elif parsed != (safe == "true"):
            problems.append(f"{key}={env[key]!r} differs from safety value {safe}; owner decision")
        lines.append(f"{key}={env[key]!r}")

    pilot = env.get(PILOT_ORG_IDS)
    if pilot is None or not pilot.strip():
        lines.append(f"{PILOT_ORG_IDS}: empty (no pilot orgs)")
    else:
        problems.append(f"{PILOT_ORG_IDS} lists pilot orgs; owner decision before the pilot flag")
        lines.append(f"{PILOT_ORG_IDS}: {len(pilot.split(','))} org id(s)")

    for key in DEFAULT_OFF:
        if key not in env:
            lines.append(f"{key}: absent (off)")
            continue
        parsed = _bool(env[key])
        if parsed is None:
            problems.append(f"{key}={env[key]!r} is not a boolean; startup would fail")
        elif parsed and key in APPROVED_ON:
            lines.append(f"{key}={env[key]!r} (owner-approved)")
            continue
        elif parsed:
            problems.append(f"{key} is on; 3.0 Plus features stay off until acceptance")
        lines.append(f"{key}={env[key]!r}")

    kill = env.get(KILL_SWITCH)
    if kill is None:
        lines.append(f"{KILL_SWITCH}: absent (ingestion runs)")
    else:
        parsed = _bool(kill)
        if parsed is None:
            problems.append(f"{KILL_SWITCH}={kill!r} is not a boolean; startup would fail")
        state = "ON: all ingestion and knowledge syncs are stopped" if parsed else "off (ingestion runs)"
        lines.append(f"{KILL_SWITCH}={kill!r} {state}")

    for key, default in CONTEXT_REPORTED.items():
        value = env.get(key, env.get(key.lower()))
        if value is None:
            lines.append(f"{key}: absent (code default {default})")
        else:
            lines.append(f"{key}={value!r}")

    # Informational only: sealed variables are not returned with their values,
    # and a running service already proves the required ones are present.
    for key in REQUIRED_SECRETS:
        if env.get(key, "").strip():
            state = "set"
        elif key in env:
            state = "present, value hidden (sealed?)"
        else:
            state = "not listed (sealed or missing)"
        lines.append(f"{key}: {state}")
    for key in OPTIONAL_REPORTED:
        value = env.get(key)
        if key.endswith("_ENABLED") and value is not None:
            lines.append(f"{key}={value!r}")
        else:
            lines.append(f"{key}: {'set' if value else 'unset'}")
    return lines, problems, pins


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vars_json", type=Path)
    parser.add_argument("--plan-out", type=Path)
    args = parser.parse_args()
    data = json.loads(args.vars_json.read_text(encoding="utf-8") or "{}")
    if not isinstance(data, dict):
        print(f"unexpected railway variables payload: {type(data).__name__}")
        return 1
    env = {str(k): "" if v is None else str(v) for k, v in data.items()}
    lines, problems, pins = audit(env)
    for line in lines:
        print(line)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if args.plan_out:
        args.plan_out.write_text("".join(f"{pin}\n" for pin in pins), encoding="utf-8")
    print(f"pins_to_add={len(pins)} problems={len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
