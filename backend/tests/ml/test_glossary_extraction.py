from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ml.glossary_extraction import extract_glossary_candidates, map_terms_to_departments


@pytest.mark.asyncio
async def test_extracts_acronyms():
    rows = [
        {"query_text": "Where is the QBR deck for APAC?", "normalized_query_text": "where is the qbr deck for apac"},
        {"query_text": "Send the QBR to leadership", "normalized_query_text": "send the qbr to leadership"},
    ]
    candidates = await extract_glossary_candidates(query_rows=rows, document_texts=[])
    acronyms = [c for c in candidates if c["term_type"] == "acronym" and c["term"] == "QBR"]
    assert acronyms
    assert acronyms[0]["source"] == "query"
    assert acronyms[0]["frequency"] >= 2


@pytest.mark.asyncio
async def test_extracts_named_entities_via_spacy():
    rows = [
        {
            "query_text": "Schedule meeting with Acme Corp in Seattle",
            "normalized_query_text": "schedule meeting with acme corp in seattle",
        }
    ]
    with patch("app.ml.glossary_extraction._get_spacy_nlp") as mock_nlp:
        ent = MagicMock()
        ent.text = "Acme Corp"
        doc = MagicMock()
        doc.ents = [ent]
        mock_nlp.return_value = lambda text: doc
        candidates = await extract_glossary_candidates(query_rows=rows, document_texts=[])
    named = [c for c in candidates if c["term_type"] == "named_entity"]
    assert any(c["term"] == "Acme Corp" for c in named)


@pytest.mark.asyncio
async def test_term_associated_with_correct_department():
    candidates = [{"term": "QBR", "term_type": "acronym", "frequency": 2, "source": "query"}]
    rows = [
        {
            "query_text": "QBR deck",
            "normalized_query_text": "qbr deck",
            "department": "Marketing",
        },
        {
            "query_text": "latest QBR",
            "normalized_query_text": "latest qbr",
            "department": "Marketing",
        },
        {
            "query_text": "QBR for sales",
            "normalized_query_text": "qbr for sales",
            "department": "Sales",
        },
    ]
    enriched = map_terms_to_departments(candidates, rows)
    assert enriched[0]["associated_department"] == "Marketing"


@pytest.mark.asyncio
async def test_extraction_from_both_query_and_document_sources():
    rows = [{"query_text": "Use the CRM dashboard", "normalized_query_text": "use the crm dashboard"}]
    docs = ["Our CRM dashboard lives in Salesforce."]
    candidates = await extract_glossary_candidates(query_rows=rows, document_texts=docs)
    sources = {c["source"] for c in candidates if c["term"] == "CRM"}
    assert "query" in sources
    assert "document" in sources
