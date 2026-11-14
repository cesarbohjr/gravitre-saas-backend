"""ECO-003 timing and isolation guards: no authorization or routing changes."""
from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
from unittest.mock import Mock

import pytest

from app.services import context_stage_metrics as metrics
from app.services.context_assembler import ContextAssembler
from app.services.unified_retrieval_service import UnifiedRetrievalService


@pytest.mark.asyncio
async def test_disabled_preserves_result_without_emitting(monkeypatch):
    monkeypatch.delenv("ECO003_CONTEXT_LATENCY_TRACE", raising=False)
    spy = Mock()
    monkeypatch.setattr(metrics.CONTEXT_STAGE_SECONDS, "labels", spy)

    async def load():
        return {"tenant_scoped": True}

    assert await metrics.measure("org_context", load()) == {"tenant_scoped": True}
    spy.assert_not_called()


@pytest.mark.asyncio
async def test_enabled_emits_fixed_stage_only_and_preserves_result(monkeypatch):
    monkeypatch.setenv("ECO003_CONTEXT_LATENCY_TRACE", "true")
    observer = Mock()
    spy = Mock(return_value=observer)
    monkeypatch.setattr(metrics.CONTEXT_STAGE_SECONDS, "labels", spy)

    async def load():
        return 123

    assert await metrics.measure("rag_retrieval", load()) == 123
    spy.assert_called_once_with(stage="rag_retrieval", outcome="ok")
    observer.observe.assert_called_once()
    assert observer.observe.call_args.args[0] >= 0


@pytest.mark.asyncio
async def test_errors_propagate_without_fallback_change(monkeypatch):
    monkeypatch.setenv("ECO003_CONTEXT_LATENCY_TRACE", "yes")
    observer = Mock()
    spy = Mock(return_value=observer)
    monkeypatch.setattr(metrics.CONTEXT_STAGE_SECONDS, "labels", spy)

    async def load():
        raise PermissionError("scope rejected")

    with pytest.raises(PermissionError, match="scope rejected"):
        await metrics.measure("agent_memory", load())
    spy.assert_called_once_with(stage="agent_memory", outcome="error")
    observer.observe.assert_called_once()


@pytest.mark.asyncio
async def test_cancellation_propagates(monkeypatch):
    monkeypatch.setenv("ECO003_CONTEXT_LATENCY_TRACE", "1")
    observer = Mock()
    spy = Mock(return_value=observer)
    monkeypatch.setattr(metrics.CONTEXT_STAGE_SECONDS, "labels", spy)

    async def load():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await metrics.measure("unified_retrieval", load())
    spy.assert_called_once_with(stage="unified_retrieval", outcome="error")
    observer.observe.assert_called_once()


@pytest.mark.asyncio
async def test_dynamic_label_rejected_and_coroutine_closed(monkeypatch):
    monkeypatch.setenv("ECO003_CONTEXT_LATENCY_TRACE", "true")

    async def load():
        return None

    coro = load()
    with pytest.raises(ValueError, match="Unrecognized static"):
        await metrics.measure("org-id-or-request-text", coro)
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED


def test_context_assembler_scopes_and_serial_policy_are_preserved():
    source = inspect.getsource(ContextAssembler.assemble)
    assert 'measure_context_stage("unified_retrieval"' in source
    assert 'measure_context_stage("company_intelligence"' in source
    assert 'measure_context_stage("external_research"' in source
    assert 'RetrievalScopes(knowledge=True, org_context=True, agent_memory=True)' in source
    assert 'user_id=user_id' in source
    assert 'environment_name=environment_name' in source
    calls = (node for node in ast.walk(ast.parse(textwrap.dedent(source))) if isinstance(node, ast.Call))
    assert not any(isinstance(call.func, ast.Attribute) and call.func.attr == "gather" and isinstance(call.func.value, ast.Name) and call.func.value.id == "asyncio" for call in calls)
    assert "create_task(" not in source


def test_unified_retrieval_preserves_tenant_and_environment_scopes():
    source = inspect.getsource(UnifiedRetrievalService.retrieve)
    assert 'measure_context_stage("org_context"' in source
    assert 'measure_context_stage("agent_memory"' in source
    assert 'measure_context_stage("rag_retrieval"' in source
    assert 'org_id=org_id' in source
    assert 'user_id=user_id' in source
    assert 'environment_name=environment_name' in source
    assert 'filters: dict[str, Any] = {"environment": environment_name}' in source
    calls = (node for node in ast.walk(ast.parse(textwrap.dedent(source))) if isinstance(node, ast.Call))
    assert not any(isinstance(call.func, ast.Attribute) and call.func.attr == "gather" and isinstance(call.func.value, ast.Name) and call.func.value.id == "asyncio" for call in calls)
