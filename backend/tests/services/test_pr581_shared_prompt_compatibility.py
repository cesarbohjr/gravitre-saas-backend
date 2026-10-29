"""Packaging's canonical prompt builders compose with the shared brain envelope.

Run unchanged against both standalone PR581 and the PR581+PR587 integration tree.
Provider/service collaborators are fixtures; router and rendering are real.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.capabilities.agency_enrichment import APPROVED_ENRICHMENTS
from app.capabilities.agent_manifest import MANIFESTS
from app.operators.agent_prompts import build_agent_instructions_section, build_agent_system_prompt
from app.services.execution_intelligence_context import execution_intelligence_context
from app.services.intelligence_router import CAPABILITY_NAMES


@pytest.mark.parametrize("role", MANIFESTS)
@pytest.mark.parametrize("status", ["available", "deferred", "unavailable", "pending_consent"])
@pytest.mark.asyncio
async def test_same_role_guidance_and_seven_slots_compose_in_full_and_compact_prompts(role, status):
    agent = {"id": "agent-a", "org_id": "tenant-a", "role": role, "config": {}}
    original = deepcopy(agent)
    facade = SimpleNamespace(
        _router=SimpleNamespace(
            _understanding=SimpleNamespace(understand=AsyncMock(return_value={})),
            _task_classifier=SimpleNamespace(classify=AsyncMock(return_value={})),
            _sentiment=SimpleNamespace(analyze=lambda *a: {})),
        run_router_enrichments=AsyncMock(return_value={"capabilities": {
            name: {"status": status, "source": "fixture", "advisory_only": True} for name in CAPABILITY_NAMES}}),
    )
    with patch("app.services.chat_intelligence_facade.get_chat_intelligence_facade", return_value=facade), patch(
        "app.services.execution_intelligence_context.load_chat_dialogue_settings", new_callable=AsyncMock, return_value={}
    ):
        evidence = await execution_intelligence_context(settings=None, org_id="tenant-a", task="Review evidence",
                                                       agent=agent, briefing={"observations": "fixture"})
    for builder in (build_agent_system_prompt, build_agent_instructions_section):
        prompt = builder(agent) + "\n" + evidence
        assert MANIFESTS[role].system_guidance in prompt
        assert all(f'"{name}"' in prompt for name in CAPABILITY_NAMES)
        assert f'"status": "{status}"' in prompt
        assert "grants no permissions or approval" in prompt
    assert agent == original
    assert facade.run_router_enrichments.call_args.args[0] == "tenant-a"


@pytest.mark.parametrize("spec", APPROVED_ENRICHMENTS, ids=lambda s: s.target_slug)
def test_enrichment_is_identical_in_text_and_voice_prompt_builders(spec):
    agent = {"id": "agent-a", "org_id": "tenant-a", "config": {
        "marketplaceSlug": spec.target_slug, "agency_enrichment": spec.reference()}}
    for builder in (build_agent_system_prompt, build_agent_instructions_section):
        prompt = builder(agent)
        assert all(line in prompt for line in spec.guidance)
        rolled_back = deepcopy(agent)
        rolled_back["config"].pop("agency_enrichment")
        assert not any(line in builder(rolled_back) for line in spec.guidance)


def test_unknown_role_does_not_get_a_registered_role():
    for builder in (build_agent_system_prompt, build_agent_instructions_section):
        prompt = builder({"role": "superuser", "config": {}})
        assert all(manifest.system_guidance not in prompt for manifest in MANIFESTS.values())
