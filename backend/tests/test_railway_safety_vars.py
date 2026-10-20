"""The Railway safety-variable audit pins only code defaults and never overwrites."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.config import Settings

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("railway_safety_vars", REPO / "scripts" / "railway_safety_vars.py")
rsv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rsv)


def _default(env_name: str):
    return Settings.model_fields[env_name.lower()].default


def test_every_pin_equals_the_code_default_so_applying_changes_nothing():
    for key, value in rsv.SAFETY_PINS.items():
        assert _default(key) is (value == "true"), key
    for key in rsv.DEFAULT_OFF:
        assert _default(key) is False, key
    assert _default(rsv.PILOT_ORG_IDS) == ""


def test_the_only_true_pin_is_purge_dry_run():
    assert [k for k, v in rsv.SAFETY_PINS.items() if v == "true"] == ["SOURCE_PURGE_DRY_RUN"]


def test_absent_variables_become_pins_and_nothing_else_does():
    lines, problems, pins = rsv.audit({"OPENAI_API_KEY": "sk-secret-value"})
    assert problems == []
    assert pins == [f"{k}={v}" for k, v in rsv.SAFETY_PINS.items()]
    assert not any("sk-secret-value" in line for line in lines)


def test_a_present_value_that_differs_is_reported_not_pinned():
    _lines, problems, pins = rsv.audit({"DOMAIN_EVENT_RELAY_ENABLED": "true", "SOURCE_PURGE_DRY_RUN": "false"})
    assert not any(p.startswith(("DOMAIN_EVENT_RELAY_ENABLED=", "SOURCE_PURGE_DRY_RUN=")) for p in pins)
    assert len([p for p in problems if "owner decision" in p]) == 2


def test_empty_boolean_is_flagged_because_it_breaks_startup():
    _lines, problems, _pins = rsv.audit({"GOAL_LINKS_ENABLED": "", "RAG_WORKER_PILOT_ENABLED": "maybe"})
    assert any("GOAL_LINKS_ENABLED" in p and "startup" in p for p in problems)
    assert any("RAG_WORKER_PILOT_ENABLED" in p and "startup" in p for p in problems)


def test_an_enabled_feature_or_pilot_org_list_is_reported():
    _lines, problems, _pins = rsv.audit({"ENTITY_WRITER_ENABLED": "true", "RAG_WORKER_PILOT_ORG_IDS": "a,b"})
    assert any("ENTITY_WRITER_ENABLED" in p for p in problems)
    assert any("RAG_WORKER_PILOT_ORG_IDS" in p for p in problems)


def test_owner_approved_value_is_reported_not_a_problem():
    lines, problems, pins = rsv.audit({"RETRIEVED_CONTENT_GUARD_ENABLED": "true"})
    assert problems == []
    assert "RETRIEVED_CONTENT_GUARD_ENABLED=true" not in pins
    assert "RETRIEVED_CONTENT_GUARD_ENABLED='true' (owner-approved)" in lines


def test_approved_values_cover_only_safety_pins_and_never_add_pins():
    assert set(rsv.APPROVED_VALUES) <= set(rsv.SAFETY_PINS)
    _lines, _problems, pins = rsv.audit({})
    assert "RETRIEVED_CONTENT_GUARD_ENABLED=false" in pins


def test_guard_switched_back_off_is_still_clean():
    _lines, problems, _pins = rsv.audit({"RETRIEVED_CONTENT_GUARD_ENABLED": "false"})
    assert problems == []


def test_kill_switch_is_reported_with_its_value_and_never_pinned():
    lines, problems, pins = rsv.audit({})
    assert "DISABLE_INGESTION: absent (ingestion runs)" in lines
    assert not any(p.startswith("DISABLE_INGESTION") for p in pins)
    lines, problems, _ = rsv.audit({"DISABLE_INGESTION": "true"})
    assert any(line.startswith("DISABLE_INGESTION='true' ON") for line in lines)
    assert problems == []
    _lines, problems, _ = rsv.audit({"DISABLE_INGESTION": ""})
    assert any("DISABLE_INGESTION" in p and "startup" in p for p in problems)
    assert _default(rsv.KILL_SWITCH) is False


def test_context_engine_settings_are_reported_never_problems_or_pins():
    lines, problems, pins = rsv.audit({"CROSS_SOURCE_CONTEXT_ENGINE_ENABLED": "true"})
    assert "CROSS_SOURCE_CONTEXT_ENGINE_ENABLED='true'" in lines
    assert "CROSS_SOURCE_CONTEXT_TOKEN_BUDGET: absent (code default 12000)" in lines
    assert not any("CROSS_SOURCE" in item for item in problems + pins)


def test_owner_approved_context_flags_on_are_reported_not_problems():
    env = {k: "true" for k in rsv.APPROVED_ON}
    lines, problems, pins = rsv.audit(env)
    assert problems == []
    for key in rsv.APPROVED_ON:
        assert f"{key}='true' (owner-approved)" in lines
    # Customer-data flags stay a problem when on.
    _, problems, _ = rsv.audit({"CONTEXT_ENGINE_OBSERVATIONS_V1": "true", "ENTITY_OBSERVATIONS_ENABLED": "true"})
    assert len(problems) == 2


def test_approved_on_flags_are_default_off_and_carry_no_customer_data():
    assert rsv.APPROVED_ON <= set(rsv.DEFAULT_OFF)
    assert not any("OBSERVATIONS" in k or "SIGNALS" in k or "ENTITY" in k for k in rsv.APPROVED_ON)


def test_storage_flags_are_default_on_and_reported():
    # Owner decision 2026-10-20: the storage features ship on.
    for key in (
        "AUDIT_RETENTION_ARCHIVE_ENABLED",
        "STORAGE_METER_ENABLED",
        "STORAGE_QUOTA_ENFORCEMENT_ENABLED",
        "BYO_STORAGE_ENABLED",
    ):
        assert key in rsv.DEFAULT_ON and key not in rsv.DEFAULT_OFF
        assert _default(key) is True
    lines, problems, _pins = rsv.audit({})
    assert problems == []
    assert "STORAGE_METER_ENABLED: absent (on)" in lines
    lines, problems, _pins = rsv.audit({"BYO_STORAGE_ENABLED": "false"})
    assert problems == [] and "BYO_STORAGE_ENABLED='false'" in lines
    _lines, problems, _pins = rsv.audit({"BYO_STORAGE_ENABLED": "maybe"})
    assert any("BYO_STORAGE_ENABLED" in p and "startup" in p for p in problems)


def test_retention_settings_are_reported_never_pinned():
    assert _default("AUDIT_RETENTION_DAYS") == 365
    assert _default("TELEMETRY_RETENTION_DAYS") == 365
    assert _default("AUDIT_RETENTION_DRY_RUN") is False
    lines, problems, pins = rsv.audit({})
    assert "AUDIT_RETENTION_DAYS: absent (code default 365)" in lines
    assert not any(p.startswith(("AUDIT_RETENTION", "TELEMETRY_RETENTION")) for p in pins)
    lines, problems, pins = rsv.audit(
        {"AUDIT_RETENTION_DAYS": "365", "AUDIT_RETENTION_DRY_RUN": "false", "TELEMETRY_RETENTION_DAYS": "0"}
    )
    assert problems == []
    assert "AUDIT_RETENTION_DAYS='365' (rows older than this are removed; floor applies)" in lines
    assert "AUDIT_RETENTION_DRY_RUN='false'" in lines
    assert "TELEMETRY_RETENTION_DAYS='0' (keep forever)" in lines
    assert not any(p.startswith(("AUDIT_RETENTION", "TELEMETRY_RETENTION")) for p in pins)


def test_retention_values_that_break_startup_are_problems():
    _lines, problems, _pins = rsv.audit({"AUDIT_RETENTION_DAYS": "a year", "AUDIT_RETENTION_DRY_RUN": "maybe"})
    assert any("AUDIT_RETENTION_DAYS" in p and "startup" in p for p in problems)
    assert any("AUDIT_RETENTION_DRY_RUN" in p and "startup" in p for p in problems)
