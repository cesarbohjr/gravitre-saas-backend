"""G.5 Phase 4.2/4.3 unit guards — enrichment sample + aggressive compress."""
from __future__ import annotations

from app.connectors.action_catalog import action_retrieval_enrichment as enrich_mod
from app.connectors.action_catalog.action_retrieval_enrichment import (
    ACTION_RETRIEVAL_ENRICHMENT,
    enrichment_document_suffix,
)
from app.services.agent_platform_optimizer import compress_tool_definition_aggressive
from app.services.chat_action_mapper import ChatActionMapper


def test_enrichment_sample_covers_f4_and_g1_vendors():
    keys = set(ACTION_RETRIEVAL_ENRICHMENT)
    for required in (
        "github.issues.list",
        "clickup.tasks.list",
        "salesforce.contacts.search",
        "asana.tasks.create",
        "notion.pages.create",
    ):
        assert required in keys
    assert 15 <= len(keys) <= 25


def test_enrichment_toggle_disables_suffix():
    prior = enrich_mod.ENRICHMENT_ENABLED
    enrich_mod.ENRICHMENT_ENABLED = False
    assert enrichment_document_suffix("gmail.messages.send") == ""
    enrich_mod.ENRICHMENT_ENABLED = True
    try:
        assert "examples:" in enrichment_document_suffix("gmail.messages.send")
    finally:
        enrich_mod.ENRICHMENT_ENABLED = prior


def test_aggressive_compress_keeps_when_why_cue():
    tool = {
        "type": "function",
        "function": {
            "name": "gmail_messages_send",
            "description": (
                "Send a Gmail message via Gmail API. Use this when the user wants "
                "to email someone. Prefer over drafts when they say send."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "recipient"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "cc": {"type": "string"},
                    "bcc": {"type": "string"},
                    "thread_id": {"type": "string"},
                    "extra1": {"type": "string"},
                    "extra2": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    }
    out = compress_tool_definition_aggressive(tool)
    desc = str(out["function"]["description"]).lower()
    assert "when" in desc or "use this" in desc or "prefer" in desc
    props = out["function"]["parameters"]["properties"]
    assert "to" in props
    assert len(props) <= 6


def test_g1_github_issues_still_maps_with_enrichment():
    prior = enrich_mod.ENRICHMENT_ENABLED
    enrich_mod.ENRICHMENT_ENABLED = True
    try:
        match = ChatActionMapper().match_segment(
            "search GitHub issues mentioning billing",
            connected_integrations=["github"],
        )
        assert match is not None
        assert "issues" in match.entry.registry_key
    finally:
        enrich_mod.ENRICHMENT_ENABLED = prior


def test_enrichment_defaults_on_with_full_catalog():
    from app.connectors.action_catalog.action_retrieval_enrichment import enrichment_coverage

    assert enrich_mod.ENRICHMENT_ENABLED is True
    cov = enrichment_coverage()
    assert cov["data_path_exists"] is True
    assert cov["full_coverage"] is True
    assert cov["catalog_action_count"] >= 690
