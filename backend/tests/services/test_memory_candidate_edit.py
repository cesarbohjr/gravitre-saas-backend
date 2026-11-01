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


@pytest.mark.asyncio
async def test_correction_queues_a_linked_candidate_and_leaves_the_memory_in_use():
    service = MemoryPromotionService(settings=MagicMock())
    original = {
        "id": "c1",
        "status": "written",
        "content": "Main contact is Lena Ortiz",
        "candidate_type": "glossary",
        "memory_category": "account",
        "memory_ids": ["m1"],
        "frequency": 4,
        "department_count": 2,
    }
    client, updates = _client(original)
    with (
        patch.object(service, "_client", return_value=client),
        patch.object(service, "_upsert_candidate", return_value={"id": "c2", "status": "pending_approval"}) as upsert,
        patch("app.workflows.audit.write_audit_event") as audit,
    ):
        out = await service.request_correction("c1", "org-1", "user-1", " Main contact is  Marcus Hale ", "Lena left")
    assert out["id"] == "c2"
    kwargs = upsert.call_args.kwargs
    assert kwargs["source_table"] == "memory_correction"
    assert kwargs["source_id"] == "c1"
    assert kwargs["status"] == "pending_approval"
    assert kwargs["content"] == "Main contact is Marcus Hale"
    assert kwargs["candidate_type"] == "glossary"
    assert kwargs["metadata"]["corrects_candidate_id"] == "c1"
    assert kwargs["metadata"]["corrects_memory_ids"] == ["m1"]
    assert kwargs["metadata"]["reason"] == "Lena left"
    assert updates == []
    assert audit.call_args.args[3] == "memory.correction_requested"


@pytest.mark.asyncio
async def test_correction_refuses_waiting_rejected_missing_and_unchanged():
    service = MemoryPromotionService(settings=MagicMock())
    for status in ("pending_approval", "candidate", "rejected", "rolled_back"):
        client, _ = _client({"id": "c1", "status": status, "content": "x"})
        with patch.object(service, "_client", return_value=client), patch.object(service, "_upsert_candidate") as upsert:
            with pytest.raises(ValueError):
                await service.request_correction("c1", "org-1", "u", "new text")
        upsert.assert_not_called()
    client, _ = _client({"id": "c1", "status": "written", "content": "same"})
    with patch.object(service, "_client", return_value=client):
        with pytest.raises(ValueError):
            await service.request_correction("c1", "org-1", "u", "same")
    client, _ = _client({})
    with patch.object(service, "_client", return_value=client):
        with pytest.raises(ValueError):
            await service.request_correction("missing", "org-1", "u", "text")


@pytest.mark.asyncio
async def test_approving_a_correction_retires_the_memory_it_replaces():
    service = MemoryPromotionService(settings=MagicMock())
    correction = {
        "id": "c2",
        "status": "pending_approval",
        "candidate_type": "glossary",
        "content": "Main contact is Marcus Hale",
        "metadata": {"corrects_candidate_id": "c1", "corrects_memory_ids": ["m1"]},
    }
    client, _ = _client(correction)
    with (
        patch.object(service, "_client", return_value=client),
        patch.object(service, "_promote_candidate", return_value={"candidate_id": "c2", "memory_ids": ["m2"]}),
        patch.object(service, "rollback_memory") as rollback,
    ):
        out = await service.approve_candidate("c2", "org-1", "admin-1")
    assert out["memory_ids"] == ["m2"]
    rollback.assert_awaited_once_with("m1", "org-1", "admin-1", "Replaced by a reviewed correction")
