from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.memory_promotion_service import MemoryPromotionService


def _client(candidate: dict):
    client = MagicMock()
    updates: list[dict] = []

    def table(name):
        t = MagicMock()
        if name == "memory_promotion_candidates":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[candidate] if candidate else []
            )

            def update(payload):
                updates.append(payload)
                return MagicMock()

            t.update.side_effect = update
        return t

    client.table.side_effect = table
    return client, updates


@pytest.mark.asyncio
async def test_edit_rewords_a_waiting_candidate_and_keeps_the_first_wording():
    service = MemoryPromotionService(settings=MagicMock())
    client, updates = _client(
        {"id": "c1", "status": "pending_approval", "content": "Cold chain ships from Reno", "metadata": {"term": "Depot"}}
    )
    with patch.object(service, "_client", return_value=client), patch("app.workflows.audit.write_audit_event") as audit:
        out = await service.edit_candidate("c1", "org-1", "user-1", "  Refrigerated freight ships   from Reno and Tacoma ")
    assert out["content"] == "Refrigerated freight ships from Reno and Tacoma"
    assert updates[0]["metadata"]["original_content"] == "Cold chain ships from Reno"
    assert updates[0]["metadata"]["term"] == "Depot"
    assert "content_fingerprint" not in updates[0]
    audit.assert_called_once()
    assert audit.call_args.args[3] == "memory.candidate_edited"


@pytest.mark.asyncio
async def test_edit_refuses_decided_or_missing_candidates_and_empty_text():
    service = MemoryPromotionService(settings=MagicMock())
    for status in ("written", "rejected", "approved"):
        client, updates = _client({"id": "c1", "status": status, "content": "x", "metadata": {}})
        with patch.object(service, "_client", return_value=client):
            with pytest.raises(ValueError):
                await service.edit_candidate("c1", "org-1", "u", "new text")
        assert updates == []
    client, _ = _client({})
    with patch.object(service, "_client", return_value=client):
        with pytest.raises(ValueError):
            await service.edit_candidate("missing", "org-1", "u", "text")
    with pytest.raises(ValueError):
        await service.edit_candidate("c1", "org-1", "u", "   ")
