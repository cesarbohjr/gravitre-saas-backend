"""Offline image contract. Imports real pinned SDKs without model/browser access."""
import inspect
import sys
if sys.argv[1]=='openhands':
    from openhands.sdk import LLM,Agent,Conversation,Tool
    from openhands.sdk.conversation.impl.local_conversation import LocalConversation
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.terminal import TerminalTool
    assert 'max_iteration_per_run' in inspect.signature(LocalConversation).parameters
    assert {'stream','num_retries','timeout','max_output_tokens'} <= set(LLM.model_fields)
    assert FileEditorTool.name and TerminalTool.name
elif sys.argv[1]=='browser_use':
    from browser_use import Agent,Browser,ChatOpenAI,Tools
    assert {'browser','tools','directly_open_url','use_judge','use_vision','max_actions_per_step'} <= set(inspect.signature(Agent).parameters)
    assert {'include_screenshot','cached'} <= set(inspect.signature(Browser.get_browser_state_summary).parameters)
    assert hasattr(Browser,'kill') and hasattr(Tools,'act')
    # Exercise the real SDK serialization/response path using an in-process
    # HTTP transport. This cannot reach a model provider or open a browser.
    import asyncio,json,httpx
    from browser_use.llm.messages import UserMessage
    async def verify_chat_wire():
        def respond(request):
            body=json.loads(request.content)
            assert body['model']=='offline-contract'
            assert body['max_completion_tokens']==4096
            assert 'frequency_penalty' not in body
            assert set(body)<={'model','messages','temperature','max_completion_tokens','response_format'}
            return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,'model':'offline-contract','choices':[{'index':0,'message':{'role':'assistant','content':'ok'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            model=ChatOpenAI(model='offline-contract',api_key='job-token',base_url='http://gateway:8080/v1',frequency_penalty=None,max_retries=0,timeout=35,http_client=client)
            result=await model.ainvoke([UserMessage(content='offline SDK contract')])
            assert result.completion=='ok'
    asyncio.run(verify_chat_wire())
else:raise ValueError('Unknown contract')
print('Pinned SDK call surface verified; no provider or browser task executed')
