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
    from browser_use.agent.views import AgentHistoryList
    from browser_use.browser.profile import BrowserProfile
    from PIL import Image
    assert {'highlight_elements','dom_highlight_elements','demo_mode'} <= set(BrowserProfile.model_fields)
    # Construct without starting Chromium to verify the pinned session call surface.
    session=Browser(headless=True,highlight_elements=False,dom_highlight_elements=False,browser_profile=BrowserProfile(demo_mode=False))
    assert session.browser_profile.demo_mode is False
    assert session.browser_profile.highlight_elements is False
    assert session.browser_profile.dom_highlight_elements is False
    from browser_use.browser.watchdogs.aboutblank_watchdog import AboutBlankWatchdog
    original_recovery=AboutBlankWatchdog.on_TabClosedEvent
    assert hasattr(AboutBlankWatchdog,'_show_dvd_screensaver_on_about_blank_tabs')
    import asyncio
    from engine import configure_browser_sdk
    configure_browser_sdk()
    from browser_use.browser.events import TabCreatedEvent
    from browser_use.browser.watchdogs.popups_watchdog import PopupsWatchdog
    assert PopupsWatchdog.on_TabCreatedEvent.__name__=='on_TabCreatedEvent'
    assert PopupsWatchdog.on_TabCreatedEvent.__annotations__['event'] is TabCreatedEvent
    assert AboutBlankWatchdog.on_TabClosedEvent is original_recovery
    # The replacement needs no CDP/session/network access, even on an opaque object.
    assert asyncio.run(AboutBlankWatchdog._show_dvd_screensaver_on_about_blank_tabs(object())) is None
    assert all(hasattr(AgentHistoryList,name) for name in ('is_done','is_successful','errors','urls','final_result'))
    assert {'browser','tools','directly_open_url','use_judge','use_vision','max_actions_per_step'} <= set(inspect.signature(Agent).parameters)
    assert {'include_screenshot','cached'} <= set(inspect.signature(Browser.get_browser_state_summary).parameters)
    assert hasattr(Browser,'kill') and hasattr(Tools,'act')
    assert {'full_page','format'} <= set(inspect.signature(Browser.take_screenshot).parameters)
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
