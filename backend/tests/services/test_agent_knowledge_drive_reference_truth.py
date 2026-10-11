"""Phase 1: linking a Drive folder must not claim its content was indexed."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.agent_knowledge_sync_service import AgentKnowledgeSyncService


def test_drive_reference_summary_states_content_is_not_indexed():
    svc = AgentKnowledgeSyncService.__new__(AgentKnowledgeSyncService)
    svc.settings = SimpleNamespace()
    svc._provenance = MagicMock()
    result = asyncio.run(
        svc._sync_drive_reference(
            MagicMock(), "org-1", "agent-1", {"id": "a1", "sourceId": "folder-1", "label": "Sales playbooks"}
        )
    )
    reference = svc._provenance.upsert_reference.call_args[0][3]
    summary = reference["memory_summary"]
    assert "indexed as summaries and embeddings" not in summary
    assert "not been fetched or indexed" in summary
    assert "not indexed" in result["message"]
