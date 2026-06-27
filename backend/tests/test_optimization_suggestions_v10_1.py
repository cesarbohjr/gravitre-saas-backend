from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.optimization_suggestion_service import (
    DEFAULT_CACHE_TTL_SECONDS,
    ONE_CLICK_APPLY_SUGGESTION_TYPE,
    OptimizationSuggestionService,
)


def _slow_step_suggestion(**overrides) -> dict:
    base = {
        "id": "s-1",
        "org_id": "org-1",
        "status": "pending_review",
        "suggestion_type": ONE_CLICK_APPLY_SUGGESTION_TYPE,
        "target_entity_id": "Fetch CRM",
        "target_entity_type": "workflow_node",
        "evidence": {"source": "workflow_steps.duration", "step_name": "Fetch CRM"},
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_preview_requires_qualifying_suggestion_type():
    service = OptimizationSuggestionService(settings=MagicMock())
    with patch.object(service, "_load_suggestion", return_value=_slow_step_suggestion(suggestion_type="duplicate_step")):
        with pytest.raises(ValueError, match="slow_step"):
            await service.generate_apply_preview("org-1", "s-1")


@pytest.mark.asyncio
async def test_apply_rejects_non_slow_step_suggestions():
    service = OptimizationSuggestionService(settings=MagicMock())
    with patch.object(service, "_load_suggestion", return_value=_slow_step_suggestion(suggestion_type="duplicate_step")):
        with pytest.raises(ValueError, match="slow_step"):
            await service.apply_suggestion("org-1", "s-1", preview_token="token", reviewed_by="admin")


@pytest.mark.asyncio
async def test_apply_requires_valid_preview_token():
    service = OptimizationSuggestionService(settings=MagicMock())
    suggestion = _slow_step_suggestion(
        evidence={
            "apply_preview": {
                "token_hash": "abc",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "node_id": "node-1",
                "before_config": {},
                "after_config": {"cache_ttl_seconds": DEFAULT_CACHE_TTL_SECONDS},
            }
        }
    )
    with patch.object(service, "_load_suggestion", return_value=suggestion):
        with pytest.raises(ValueError, match="Invalid apply preview token"):
            await service.apply_suggestion("org-1", "s-1", preview_token="wrong", reviewed_by="admin")


@pytest.mark.asyncio
async def test_preview_token_expires():
    service = OptimizationSuggestionService(settings=MagicMock())
    import hashlib

    token = "valid-token"
    suggestion = _slow_step_suggestion(
        evidence={
            "apply_preview": {
                "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
                "node_id": "node-1",
                "before_config": {},
                "after_config": {"cache_ttl_seconds": DEFAULT_CACHE_TTL_SECONDS},
            }
        }
    )
    with patch.object(service, "_load_suggestion", return_value=suggestion):
        with pytest.raises(ValueError, match="expired"):
            await service.apply_suggestion("org-1", "s-1", preview_token=token, reviewed_by="admin")


@pytest.mark.asyncio
async def test_apply_writes_full_audit_event():
    service = OptimizationSuggestionService(settings=MagicMock())
    import hashlib

    token = "valid-token"
    suggestion = _slow_step_suggestion(
        evidence={
            "apply_preview": {
                "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "node_id": "node-1",
                "before_config": {},
                "after_config": {"cache_ttl_seconds": DEFAULT_CACHE_TTL_SECONDS},
            }
        }
    )
    client = MagicMock()

    def _table(name: str):
        table = MagicMock()
        if name == "workflow_nodes":
            table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "node-1", "config": {"cache_ttl_seconds": DEFAULT_CACHE_TTL_SECONDS}}]
            )
        elif name == "optimization_suggestions":
            table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        **suggestion,
                        "status": "applied",
                        "applied_change_summary": "Set cache_ttl_seconds=300 on workflow node node-1",
                    }
                ]
            )
        return table

    client.table.side_effect = _table
    with patch.object(service, "_client", return_value=client):
        with patch.object(service, "_load_suggestion", return_value=suggestion):
            with patch("app.services.optimization_suggestion_service.write_audit_event") as audit_mock:
                result = await service.apply_suggestion(
                    "org-1",
                    "s-1",
                    preview_token=token,
                    reviewed_by="admin-1",
                )
    assert result["status"] == "applied"
    audit_mock.assert_called_once()
    assert audit_mock.call_args.kwargs["action"] == "optimization_suggestion.apply"


@pytest.mark.asyncio
async def test_apply_only_modifies_cache_related_config():
    service = OptimizationSuggestionService(settings=MagicMock())
    import hashlib

    token = "valid-token"
    suggestion = _slow_step_suggestion(
        evidence={
            "apply_preview": {
                "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "node_id": "node-1",
                "before_config": {"action": "hubspot.deals.get"},
                "after_config": {
                    "action": "hubspot.deals.get",
                    "cache_ttl_seconds": DEFAULT_CACHE_TTL_SECONDS,
                    "prompt": "changed",
                },
            }
        }
    )
    with patch.object(service, "_load_suggestion", return_value=suggestion):
        with pytest.raises(ValueError, match="more than cache_ttl_seconds"):
            await service.apply_suggestion("org-1", "s-1", preview_token=token, reviewed_by="admin")


def test_no_other_suggestion_type_gained_apply_path():
    import inspect

    from app.services.optimization_suggestion_service import OptimizationSuggestionService

    source = inspect.getsource(OptimizationSuggestionService.apply_suggestion)
    assert ONE_CLICK_APPLY_SUGGESTION_TYPE in source
    assert "duplicate_step" not in source
    assert "low_reliability_source" not in source
    assert "poor_outcome_pattern" not in source
