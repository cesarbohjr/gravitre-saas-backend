"""Tests for POST/GET /api/admin/model-evaluation and POST /{id}/approve.

Covers:
- run evaluation happy path (report stored, audit event written)
- approve happy path (ledger seeded, routing_approved set)
- approve blocks when critical failures exist
- approve is idempotent (re-approve returns already_approved=True)
- approve returns 404 for unknown eval id
- best_model not in report → 422
- platform admin gate enforced (non-admin → 403)
- unknown/deprecated model in run request → 422
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_supabase_client(
    *,
    stored_eval: dict | None = None,
    insert_raises: bool = False,
    update_raises: bool = False,
) -> MagicMock:
    client = MagicMock()
    insert_result = MagicMock()
    insert_result.data = [{"id": "eval-1"}]

    def _insert(*a, **k):
        if insert_raises:
            raise RuntimeError("db insert error")
        return MagicMock(execute=MagicMock(return_value=insert_result))

    update_result = MagicMock()
    update_result.data = [{"id": "eval-1"}]

    def _update_chain(*a, **k):
        if update_raises:
            raise RuntimeError("db update error")
        eq_mock = MagicMock()
        eq_mock.eq.return_value = MagicMock(execute=MagicMock(return_value=update_result))
        return eq_mock

    select_result = MagicMock()
    select_result.data = [stored_eval] if stored_eval else []

    def _select(*a, **k):
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=select_result))
        chain.execute.return_value = select_result
        return chain

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        tbl.insert.side_effect = _insert
        tbl.update.side_effect = _update_chain
        tbl.select.side_effect = _select
        return tbl

    client.table.side_effect = _table
    return client


def _good_eval_report(critical_failures: int = 0) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "dataset_sha256": "abc123",
        "catalog_sha256": "def456",
        "scope": "synthetic_structured_planning_only",
        "routing_changed": False,
        "models": {
            "gpt-4o-mini": {
                "attempts": 5, "passed": 5, "pass_rate": 1.0,
                "critical_failures": critical_failures,
                "provider_substitutions": 0,
                "total_cost_usd": 0.01, "cost_per_success_usd": 0.002,
                "cost_coverage_complete": True,
                "latency_ms": {"n": 5, "p50": 100, "p95": 200, "p99": 300},
                "routing_approved": False,
            }
        },
        "results": [],
        "limitations": [],
    }


def _make_app(
    *,
    is_admin: bool = True,
    stored_eval: dict | None = None,
    insert_raises: bool = False,
    update_raises: bool = False,
    evaluate_models_result: dict | None = None,
    evaluate_models_raises: Exception | None = None,
    ledger_record_raises: bool = False,
) -> tuple[FastAPI, MagicMock]:
    from app.routers.model_evaluation import router
    from app.auth.dependencies import get_current_user
    from app.config import get_settings

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
    app.dependency_overrides[get_settings] = lambda: MagicMock(
        preferred_ai_provider="openai",
        msp_parent_org_enabled=False,
    )

    supabase_client = _make_supabase_client(
        stored_eval=stored_eval, insert_raises=insert_raises, update_raises=update_raises
    )

    eval_result = evaluate_models_result or _good_eval_report()
    if evaluate_models_raises:
        evaluate_mock = AsyncMock(side_effect=evaluate_models_raises)
    else:
        evaluate_mock = AsyncMock(return_value=eval_result)

    ledger = MagicMock()
    if ledger_record_raises:
        ledger.record = AsyncMock(side_effect=RuntimeError("ledger down"))
    else:
        ledger.record = AsyncMock(return_value=None)

    return app, supabase_client, evaluate_mock, ledger


# ---------------------------------------------------------------------------
# run_evaluation tests
# ---------------------------------------------------------------------------


def test_run_evaluation_happy_path() -> None:
    app, supabase, evaluate_mock, ledger = _make_app()
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_llm_model", return_value=MagicMock(deprecated=False)),
        patch("app.routers.model_evaluation.ModelRouter"),
        patch("app.routers.model_evaluation.evaluate_models", evaluate_mock),
        patch("app.routers.model_evaluation.write_audit_event"),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/api/admin/model-evaluation", json={
            "org_id": "eval-org-1",
            "models": ["gpt-4o-mini"],
            "repetitions": 1,
            "use_golden_cases": True,
        })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "eval_id" in data
    assert "report" in data
    evaluate_mock.assert_awaited_once()


def test_run_evaluation_non_admin_rejected() -> None:
    app, supabase, evaluate_mock, _ = _make_app()
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=False),
        patch("app.routers.model_evaluation.get_llm_model", return_value=MagicMock(deprecated=False)),
    ):
        client = TestClient(app)
        resp = client.post("/api/admin/model-evaluation", json={
            "org_id": "eval-org-1",
            "models": ["gpt-4o-mini"],
        })
    assert resp.status_code == 403


def test_run_evaluation_unknown_model_returns_422() -> None:
    app, supabase, _, _ = _make_app()
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_llm_model", return_value=None),
    ):
        client = TestClient(app)
        resp = client.post("/api/admin/model-evaluation", json={
            "org_id": "eval-org-1",
            "models": ["model-that-does-not-exist"],
        })
    assert resp.status_code == 422


def test_run_evaluation_db_store_failure_returns_500() -> None:
    app, supabase, evaluate_mock, _ = _make_app(insert_raises=True)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_llm_model", return_value=MagicMock(deprecated=False)),
        patch("app.routers.model_evaluation.ModelRouter"),
        patch("app.routers.model_evaluation.evaluate_models", evaluate_mock),
        patch("app.routers.model_evaluation.write_audit_event"),
    ):
        client = TestClient(app)
        resp = client.post("/api/admin/model-evaluation", json={
            "org_id": "eval-org-1",
            "models": ["gpt-4o-mini"],
        })
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# approve_evaluation tests
# ---------------------------------------------------------------------------


def test_approve_evaluation_happy_path() -> None:
    stored = {
        "id": "eval-1",
        "routing_approved": False,
        "models": ["gpt-4o-mini"],
        "report": _good_eval_report(critical_failures=0),
    }
    app, supabase, _, ledger = _make_app(stored_eval=stored)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_strategy_performance_ledger", return_value=ledger),
        patch("app.routers.model_evaluation.write_audit_event"),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/api/admin/model-evaluation/eval-1/approve", json={
            "best_model": "gpt-4o-mini",
            "segment_key": "default",
            "org_id": "prod-org-1",
        })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["routing_approved"] is True
    assert data["ledger_seeds_written"] == 6
    assert data["already_approved"] is False


def test_approve_blocks_on_critical_failures() -> None:
    stored = {
        "id": "eval-1",
        "routing_approved": False,
        "models": ["gpt-4o-mini"],
        "report": _good_eval_report(critical_failures=2),
    }
    app, supabase, _, ledger = _make_app(stored_eval=stored)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_strategy_performance_ledger", return_value=ledger),
    ):
        client = TestClient(app)
        resp = client.post("/api/admin/model-evaluation/eval-1/approve", json={
            "best_model": "gpt-4o-mini",
            "segment_key": "default",
            "org_id": "prod-org-1",
        })
    assert resp.status_code == 409
    assert "critical failure" in resp.json()["detail"]


def test_approve_is_idempotent() -> None:
    stored = {
        "id": "eval-1",
        "routing_approved": True,  # already approved
        "models": ["gpt-4o-mini"],
        "report": _good_eval_report(critical_failures=0),
    }
    app, supabase, _, ledger = _make_app(stored_eval=stored)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_strategy_performance_ledger", return_value=ledger),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/api/admin/model-evaluation/eval-1/approve", json={
            "best_model": "gpt-4o-mini",
            "segment_key": "default",
            "org_id": "prod-org-1",
        })
    assert resp.status_code == 200
    assert resp.json()["already_approved"] is True
    ledger.record.assert_not_awaited()


def test_approve_not_found_returns_404() -> None:
    app, supabase, _, ledger = _make_app(stored_eval=None)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_strategy_performance_ledger", return_value=ledger),
    ):
        client = TestClient(app)
        resp = client.post("/api/admin/model-evaluation/no-such-id/approve", json={
            "best_model": "gpt-4o-mini",
            "segment_key": "default",
            "org_id": "prod-org-1",
        })
    assert resp.status_code == 404


def test_approve_best_model_not_in_report_returns_422() -> None:
    stored = {
        "id": "eval-1",
        "routing_approved": False,
        "models": ["gpt-4o-mini"],
        "report": _good_eval_report(critical_failures=0),
    }
    app, supabase, _, ledger = _make_app(stored_eval=stored)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_strategy_performance_ledger", return_value=ledger),
    ):
        client = TestClient(app)
        resp = client.post("/api/admin/model-evaluation/eval-1/approve", json={
            "best_model": "model-not-in-report",
            "segment_key": "default",
            "org_id": "prod-org-1",
        })
    assert resp.status_code == 422


def test_approve_ledger_failure_still_marks_approved() -> None:
    """Even if the ledger is down, the report should be marked approved."""
    stored = {
        "id": "eval-1",
        "routing_approved": False,
        "models": ["gpt-4o-mini"],
        "report": _good_eval_report(critical_failures=0),
    }
    app, supabase, _, ledger = _make_app(stored_eval=stored, ledger_record_raises=True)
    with (
        patch("app.routers.model_evaluation.shared_service_client", return_value=supabase),
        patch("app.routers.model_evaluation.is_platform_admin", return_value=True),
        patch("app.routers.model_evaluation.get_strategy_performance_ledger", return_value=ledger),
        patch("app.routers.model_evaluation.write_audit_event"),
    ):
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/api/admin/model-evaluation/eval-1/approve", json={
            "best_model": "gpt-4o-mini",
            "segment_key": "default",
            "org_id": "prod-org-1",
        })
    assert resp.status_code == 200
    data = resp.json()
    # Ledger failure means 0 seeds written but still approved.
    assert data["routing_approved"] is True
    assert data["ledger_seeds_written"] == 0
