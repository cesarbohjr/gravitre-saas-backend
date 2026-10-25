import asyncio
import pytest
from app.plays.prospecting_agent import plan_prospect_research, prospect_research_brief

class FakeIntelligenceRouter:
    def __init__(self):
        self.calls = []
    async def route(self, **kwargs):
        self.calls.append(kwargs)
        return {"answer": "Review discovered evidence before contact export"}

def test_brief_rejects_bad_target():
    with pytest.raises(ValueError):
        prospect_research_brief(country="CA",industry="MSP",target_roles=("CEO",),count=0)

def test_agent_reuses_existing_router_and_remains_advisory():
    router=FakeIntelligenceRouter()
    result=asyncio.run(plan_prospect_research(
        org_id="tenant-a",actor_id="user-a",country="Canada",
        industry="Managed IT",target_roles=("CEO",),count=100,router=router
    ))
    assert result["read_only"] and not result["crm_write_allowed"]
    assert not result["outbound_email_allowed"]
    assert router.calls[0]["org_id"] == "tenant-a"
    assert router.calls[0]["user_id"] == "user-a"
    assert "Never send email" in router.calls[0]["request"]
