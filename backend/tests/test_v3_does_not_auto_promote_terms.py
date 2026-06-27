from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge_intelligence_service import GLOSSARY_STATUS_CANDIDATE, run_glossary_extraction


@pytest.mark.asyncio
async def test_all_extracted_terms_default_to_candidate_status():
    client = MagicMock()
    upsert = MagicMock()
    upsert.execute.return_value = MagicMock(data=[])
    client.table.return_value.upsert.return_value = upsert
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    rows = [
        {"query_text": "QBR deck for APAC", "normalized_query_text": "qbr deck for apac"},
        {"query_text": "Send QBR slides", "normalized_query_text": "send qbr slides"},
    ]
    results = await run_glossary_extraction(MagicMock(), "org-1", rows, client=client)
    assert results
    assert all(r["status"] == GLOSSARY_STATUS_CANDIDATE for r in results)


def test_nothing_in_v3_changes_status_to_confirmed():
    """Regression guard: v3 modules must never promote glossary terms (v4 owns confirmation)."""
    root = Path(__file__).resolve().parents[1] / "app"
    v3_modules = {
        "services/knowledge_intelligence_service.py",
        "ml/glossary_extraction.py",
        "services/company_intelligence_orchestrator.py",
    }
    offenders: list[str] = []
    for rel in v3_modules:
        path = root / rel.replace("/", "\\") if "\\" in str(root) else root / rel
        if not path.exists():
            path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if 'status": "confirmed"' in text or "status': 'confirmed'" in text:
            offenders.append(str(path.relative_to(root.parent)))
    assert not offenders, f"v3 must not set glossary status confirmed: {offenders}"


@pytest.mark.asyncio
async def test_glossary_service_never_upserts_confirmed():
    with patch(
        "app.services.knowledge_intelligence_service.extract_glossary_candidates",
        new=AsyncMock(return_value=[{"term": "QBR", "term_type": "acronym", "frequency": 2, "source": "query"}]),
    ), patch(
        "app.services.knowledge_intelligence_service.map_terms_to_departments",
        return_value=[{"term": "QBR", "term_type": "acronym", "frequency": 2, "source": "query"}],
    ):
        client = MagicMock()
        captured: dict = {}

        def _upsert(row, on_conflict=None):
            captured.update(row)
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=[row])
            return chain

        client.table.return_value.upsert.side_effect = _upsert
        await run_glossary_extraction(MagicMock(), "org-1", [], client=client)
        assert captured.get("status") == GLOSSARY_STATUS_CANDIDATE
