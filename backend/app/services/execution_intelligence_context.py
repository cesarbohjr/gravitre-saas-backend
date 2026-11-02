"""Feed background agents and Play/workflow consumers through the shared router.

Evidence stays advisory; no permissions, approvals or learning labels are created.
"""
import asyncio
import json

from app.services.chat_dialogue_settings import load_chat_dialogue_settings
from app.services.intelligence_router import CAPABILITY_NAMES, intelligence_context_block


async def collect_execution_intelligence(*, settings, org_id, task, agent, briefing):
    """Return tenant-bound advisory data from the existing seven-capability router."""
    if not org_id:
        raise ValueError("org_id is required")
    if agent.get("org_id") is not None and agent["org_id"] != org_id:
        raise ValueError("Agent organization does not match execution organization")
    from app.services.chat_intelligence_facade import get_chat_intelligence_facade
    async def collect():
        facade = get_chat_intelligence_facade(settings)
        router = facade._router
        understanding = await router._understanding.understand(task, [], org_id)
        classification = await router._task_classifier.classify(org_id, task, [], understanding=understanding)
        # Upstream tool observations are data. They cannot select models, set
        # authorization flags or overwrite backend classification.
        upstream = json.dumps(briefing or {}, default=str)[:6000]
        understanding = {**understanding, "workflow_evidence": upstream, "advisory_only": True}
        dialogue = await load_chat_dialogue_settings(org_id, settings)
        sentiment_enabled = dialogue.get("sentiment_detection_enabled", True)
        sentiment = router._sentiment.analyze(task, []) if sentiment_enabled else {"status": "disabled"}
        return await facade.run_router_enrichments(org_id, task,
            {**classification, "department": classification.get("department") or agent.get("department")},
            context={"understanding": understanding, "sentiment": sentiment, "sentiment_detection_enabled": sentiment_enabled})

    try:
        packet = await asyncio.wait_for(collect(), timeout=3.0)
    except Exception:
        packet = {"capabilities": {key: {"status": "unavailable", "source": "shared_router",
                  "advisory_only": True} for key in CAPABILITY_NAMES}}
    capabilities = packet.get("capabilities") if isinstance(packet, dict) else {}
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    return {"org_id": org_id, "capabilities": {
        key: {**capabilities[key], "advisory_only": True}
        if isinstance(capabilities.get(key), dict) else
        {"status": "unavailable", "source": "shared_router", "advisory_only": True}
        for key in CAPABILITY_NAMES
    }}


async def execution_intelligence_context(**kwargs):
    """Compatibility prompt consumer; collection is shared with non-chat intake."""
    return intelligence_context_block(await collect_execution_intelligence(**kwargs))


def capability_diagnostics(packet):
    """Allowlisted statuses only: never copy evidence, provider errors or text."""
    known = {"available", "unavailable", "disabled", "disabled_or_unavailable",
             "not_requested", "deferred", "missing_entity", "insufficient_data",
             "insufficient_samples", "not_supported", "unsupported", "pending_consent"}
    slots = packet.get("capabilities", {}) if isinstance(packet, dict) else {}
    slots = slots if isinstance(slots, dict) else {}
    return {key: slot.get("status") if isinstance(slot.get("status"), str) and slot.get("status") in known else "unavailable"
            for key in CAPABILITY_NAMES
            for slot in [slots.get(key) if isinstance(slots.get(key), dict) else {}]}
