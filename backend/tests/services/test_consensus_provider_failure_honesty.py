"""Provider outages must not turn unanimous defaults into independent 100% confidence."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.services.conversational_consensus_service import ConversationalConsensusService
from app.services.confidence_honesty import CONFIDENCE_SOURCE_MODEL

@pytest.mark.asyncio
@pytest.mark.parametrize('sources,available', [
    (['heuristic','heuristic'],False),
    ([CONFIDENCE_SOURCE_MODEL,'heuristic'],False),
    ([None,None],False),
    ([CONFIDENCE_SOURCE_MODEL,CONFIDENCE_SOURCE_MODEL],True),
])
async def test_only_completed_model_reviews_can_refine_the_primary_response(monkeypatch,sources,available):
    service=object.__new__(ConversationalConsensusService)
    service.settings=SimpleNamespace()
    opinions=[{'agent_name':str(i),'confidence_source':source} for i,source in enumerate(sources)]
    service._council=SimpleNamespace(start_council=AsyncMock(return_value=SimpleNamespace(
        debate_rounds=[{'round':1,'opinions':opinions}],dissenting_opinions=[],
        final_recommendation='Reviewed result',final_confidence=1.0)))
    service._persist_deliberation=AsyncMock()
    monkeypatch.setattr('app.services.conversational_consensus_service.load_chat_dialogue_settings',AsyncMock(return_value={'consensus_enabled':True}))
    result=await service.refine_if_warranted('org-a','Analyze supplied evidence','Primary result',
        {'intent':'data_analysis'},.4,'guide')
    persisted=service._persist_deliberation.await_args.args[2]
    assert persisted['independent_review_available'] is available
    assert result['consensus_used'] is available
    assert '100%' not in result['response']
    if available:
        assert 'Reviewed result' in result['response']
        assert persisted['confidence_is_estimate'] is True
    else:
        assert result['response']=='Primary result'
        assert persisted['confidence'] is None
        assert persisted['consensus_explanation']==''
