"""Feed background agents and Play/workflow consumers through the shared router.

Evidence stays advisory; no permissions, approvals or learning labels are created.
"""
import asyncio
import json

from app.services.intelligence_router import CAPABILITY_NAMES, intelligence_context_block


async def execution_intelligence_context(*, settings, org_id, task, agent, briefing):
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
        sentiment = router._sentiment.analyze(task, [])
        return await facade.run_router_enrichments(org_id, task,
            {**classification, "department": classification.get("department") or agent.get("department")},
            context={"understanding": understanding, "sentiment": sentiment})

    try:
        packet = await asyncio.wait_for(collect(), timeout=3.0)
    except Exception:
        packet = {"capabilities": {key: {"status": "unavailable", "source": "shared_router",
                  "advisory_only": True} for key in CAPABILITY_NAMES}}
    return intelligence_context_block(packet)
