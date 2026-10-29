"""Disposable SDK entrypoint. Never run directly on a backend/worker host."""
from __future__ import annotations
import asyncio
import base64
import copy
import difflib
import hashlib
import io
import json
import os
import re
from pathlib import Path
import sys
import time
import traceback
import urllib.request


def gateway(config,path,body):
    request=urllib.request.Request('http://gateway:8080'+path,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+config['engine_token'],'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=35) as response:return json.loads(response.read(1048576))


def software(config):
    from pydantic import SecretStr
    from openhands.sdk import LLM,Agent,Conversation,Tool
    from openhands.tools.file_editor import FileEditorTool
    from openhands.tools.terminal import TerminalTool
    for path,value in config['files'].items():
        target=Path('/workspace')/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
    llm=LLM(model='openai/'+config['model'],base_url='http://gateway:8080/v1',api_key=SecretStr(config['engine_token']),stream=False,num_retries=0,timeout=35,max_output_tokens=4096)
    agent=Agent(llm=llm,tools=[Tool(name=TerminalTool.name),Tool(name=FileEditorTool.name)])
    conversation=Conversation(agent=agent,workspace='/workspace',max_iteration_per_run=config['max_steps'])
    try:
        conversation.send_message('Work only on the supplied software task inside this isolated workspace. Produce a reviewable draft; no external publication, credential access or claimed production outcome.\n'+config['task'])
        conversation.run()
    finally:conversation.close()
    patch=[];count=0
    for folder,dirs,files in os.walk('/workspace',followlinks=False):
        dirs[:]=[d for d in dirs if not d.startswith('.') and d not in {'node_modules','__pycache__'} and not (Path(folder)/d).is_symlink()]
        for name in files:
            target=Path(folder)/name
            if target.is_symlink() or not target.is_file() or target.stat().st_size>120000:continue
            path=target.relative_to('/workspace').as_posix()
            if name.startswith('.'):continue
            try:current=target.read_text()
            except (UnicodeError,OSError):continue
            original=config['files'].get(path,'')
            if current!=original:patch.extend(difflib.unified_diff(original.splitlines(True),current.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
            count+=1
            if count>=100:break
        if count>=100:break
    for path,original in config['files'].items():
        if not (Path('/workspace')/path).exists():patch.extend(difflib.unified_diff(original.splitlines(True),[],fromfile='a/'+path,tofile='b/'+path))
    return {'observations':[{'summary':'The software sandbox produced a draft artifact. Review the patch and independently verify any claimed tests before applying changes.'}],'patch':''.join(patch)[:120000]}


def _browser_targets(state,requested):
    targets=[]
    for name,parameters in requested.items():
        if not isinstance(parameters,dict):continue
        index=parameters.get('index')
        if name=='click' and (index is None or parameters.get('coordinate_x') is not None or parameters.get('coordinate_y') is not None):
            raise PermissionError('Coordinate clicks require a separate visual review path')
        if index is not None:
            node=state.dom_state.selector_map.get(index)
            if node is None:raise PermissionError('Browser target no longer exists')
            attrs=node.attributes or {}
            targets.append({'index':index,'tag':str(node.node_name)[:40],
                'label':str(attrs.get('aria-label') or attrs.get('title') or node.get_all_children_text(max_depth=2))[:300]})
    return targets


def screenshot_pixel_hash(encoded):
    # Pillow is pinned by the Browser Use SDK. Bound decoding before allocating
    # pixels; image-container metadata is not visible browser context.
    from PIL import Image
    try:
        if not isinstance(encoded,str) or not 0<len(encoded)<=4194304:raise ValueError('bounds')
        raw=base64.b64decode(encoded,validate=True)
        with Image.open(io.BytesIO(raw),formats=('PNG','JPEG')) as image:
            width,height=image.size
            if not 0<width<=8192 or not 0<height<=8192 or width*height>16777216:raise ValueError('bounds')
            pixels=image.convert('RGBA').tobytes()
        return hashlib.sha256(f'{width}x{height}\nRGBA\n'.encode()+pixels).hexdigest()
    except Exception:
        raise PermissionError('Bounded decoded browser pixels required') from None


def browser_evidence(state,requested):
    # The same direct viewport capture path supplies both approval snapshots.
    # A visually identical page with a changed indexed target still invalidates it.
    dom=state.dom_state.llm_representation()
    if not state.screenshot or len(state.screenshot)>4194304 or len(dom)>2097152:
        raise PermissionError('Bounded fresh browser evidence required')
    targets=_browser_targets(state,requested)
    fingerprint=hashlib.sha256((state.url+'\n'+screenshot_pixel_hash(state.screenshot)+'\n'+dom).encode()).hexdigest()
    return {'page_fingerprint':fingerprint,'page_title':str(state.title)[:300],'targets':targets}


def browser_error_diagnostic(history):
    errors=[str(error)[:16384] for error in history.errors()[:10] if error]
    phrases={'sandbox':'sandbox','namespace':'namespace','permission denied':'permission_denied','operation not permitted':'operation_not_permitted','executable':'executable','browser closed':'browser_closed','cdp':'cdp','websocket':'websocket','parse':'parse','json':'json','validation':'validation','schema':'schema','navigation':'navigation','domain':'domain','screenshot':'screenshot'}
    codes=sorted({code for phrase,code in phrases.items() if any(phrase in error.lower() for error in errors)})
    codes+=sorted({code.lower() for code in ('ERR_TUNNEL_CONNECTION_FAILED','ERR_NAME_NOT_RESOLVED','ERR_CERT_AUTHORITY_INVALID','ERR_PROXY_CONNECTION_FAILED','ERR_CONNECTION_REFUSED','ERR_CONNECTION_CLOSED','ERR_CONNECTION_RESET','ERR_CONNECTION_TIMED_OUT') if any(code in error for error in errors)})
    known_classes={'ValueError','ValidationError','RuntimeError','TimeoutError','PermissionError','ConnectionError','BrowserError','BrowserClosedError','CancelledError','HTTPStatusError'}
    classes=sorted({match.group(1) for error in errors for match in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):',error) if match.group(1) in known_classes})
    print(json.dumps({'browser_error_codes':codes,'browser_error_classes':classes}),file=sys.stderr,flush=True)


def browser_result(history):
    if history.is_done() is not True or history.is_successful() is not True or any(history.errors()):
        browser_error_diagnostic(history)
        raise RuntimeError('Browser session did not finish successfully')
    summary=history.final_result()
    url=next((u for u in reversed(history.urls()) if isinstance(u,str) and u.startswith('https://')),None)
    if not isinstance(summary,str) or not summary.strip() or url is None:
        browser_error_diagnostic(history)
        raise ValueError('Completed browser session requires a result and an observed page')
    return {'observations':[{'summary':summary[:2000],'url':url}]}


async def fresh_browser_evidence(browser_session,requested,phase):
    try:
        # SDK screenshots are model previews and can vary in format/resolution.
        # Approval always uses actual viewport PNG pixels from the same CDP API.
        before=await browser_session.get_browser_state_summary(include_screenshot=False,cached=False)
        if getattr(before,'state_error',None):raise PermissionError('Fresh browser DOM required')
        before_url,before_title=before.url,before.title
        dom=before.dom_state.llm_representation()
        if len(dom)>2097152:raise PermissionError('Bounded fresh browser DOM required')
        targets=_browser_targets(before,requested)
        image=await browser_session.take_screenshot(full_page=False,format='png')
        if not isinstance(image,bytes) or not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image)>3145728:
            raise PermissionError('Bounded actual viewport screenshot required')
        after=await browser_session.get_browser_state_summary(include_screenshot=False,cached=False)
        if getattr(after,'state_error',None) or (after.url,after.title)!=(before_url,before_title) or after.dom_state.llm_representation()!=dom or _browser_targets(after,requested)!=targets:
            raise PermissionError('Browser changed during viewport evidence capture')
        state=copy.copy(after)
        state.screenshot=base64.b64encode(image).decode('ascii')
        return state,browser_evidence(state,requested)
    except Exception as error:
        frames=[{'file':Path(frame.filename).name,'line':frame.lineno,'function':frame.name} for frame in traceback.extract_tb(error.__traceback__) if '/browser_use/' in frame.filename or frame.filename.endswith('/engine.py')][-16:]
        print(json.dumps({'browser_failure_stage':phase,'browser_failure_class':type(error).__name__ if type(error).__name__ in {'ValueError','PermissionError','RuntimeError','TimeoutError','AttributeError'} else 'InternalError','frames':frames}),file=sys.stderr,flush=True)
        raise


async def stable_browser_evidence(browser_session,requested):
    # Initial paint can lag the DOM. Obtain two identical fresh captures before
    # presenting a review; never retry or refresh an already approved action.
    previous=None
    for _ in range(6):
        state,evidence=await fresh_browser_evidence(browser_session,requested,'before_approval')
        if evidence==previous:return state,evidence
        previous=evidence
        await asyncio.sleep(0.25)
    raise PermissionError('Browser viewport did not stabilize before approval')


async def install_rejecting_dialog_handler(watchdog,event):
    # A click approval is not approval for an additional JS confirmation.
    # Enable Page only on its target session, never on the browser root.
    if event.target_id in watchdog._dialog_listeners_registered:return
    session=await watchdog.browser_session.get_or_create_cdp_session(event.target_id,focus=False)
    async def dismiss_dialog(event_data,session_id=None):
        if session_id is not None and session_id!=session.session_id:return
        await session.cdp_client.send.Page.handleJavaScriptDialog(params={'accept':False},session_id=session.session_id)
    session.cdp_client.register.Page.javascriptDialogOpening(dismiss_dialog)
    await session.cdp_client.send.Page.enable(session_id=session.session_id)
    watchdog._dialog_listeners_registered.add(event.target_id)


def configure_browser_sdk():
    from browser_use.browser.watchdogs.aboutblank_watchdog import AboutBlankWatchdog
    from browser_use.browser.watchdogs.popups_watchdog import PopupsWatchdog
    # The pinned SDK injects an animated remote logo into about:blank even with
    # demo_mode=False. Disable only that cosmetic hook in this one-job process;
    # leave the watchdog's tab creation/recovery and all security hooks intact.
    async def no_blank_animation(self):
        return None
    AboutBlankWatchdog._show_dvd_screensaver_on_about_blank_tabs=no_blank_animation
    # Preserve the concrete SDK event annotation used by event-bus validation.
    install_rejecting_dialog_handler.__name__='on_TabCreatedEvent'
    install_rejecting_dialog_handler.__annotations__=PopupsWatchdog.on_TabCreatedEvent.__annotations__
    PopupsWatchdog.on_TabCreatedEvent=install_rejecting_dialog_handler


async def browser_page_diagnostic(browser):
    # Read-only diagnostics contain fixed transport codes/booleans, never page
    # text, titles, URLs, model content or credentials.
    known=('ERR_EMPTY_RESPONSE','ERR_CERT_AUTHORITY_INVALID','ERR_TUNNEL_CONNECTION_FAILED','ERR_NAME_NOT_RESOLVED','ERR_CONNECTION_REFUSED','ERR_CONNECTION_CLOSED','ERR_CONNECTION_RESET','ERR_CONNECTION_TIMED_OUT','ERR_TIMED_OUT','ERR_HTTP2_PROTOCOL_ERROR','ERR_BLOCKED_BY_CLIENT')
    try:
        session=await asyncio.wait_for(browser.get_or_create_cdp_session(),timeout=5)
        expression="(()=>{const t=document.body?.innerText||'';return {codes:"+json.dumps(known)+".filter(c=>t.includes(c)),body_present:!!t.trim(),title_empty:!document.title,ready:document.readyState,is_html:document.contentType==='text/html'}})()"
        result=await asyncio.wait_for(session.cdp_client.send.Runtime.evaluate(params={'expression':expression,'returnByValue':True},session_id=session.session_id),timeout=5)
        value=result.get('result',{}).get('value',{})
        if not isinstance(value,dict):return
        codes=value.get('codes',[])
        ready=value.get('ready')
        print(json.dumps({'browser_page_diagnostic':{'codes':[code for code in known if isinstance(codes,list) and code in codes],
            'body_present':value.get('body_present') is True,'title_empty':value.get('title_empty') is True,
            'is_html':value.get('is_html') is True,'ready':ready if ready in ('loading','interactive','complete') else 'unknown'}}),file=sys.stderr,flush=True)
    except Exception:
        print(json.dumps({'browser_page_diagnostic':{'unavailable':True}}),file=sys.stderr,flush=True)


async def browse(config):
    from browser_use import Agent,Browser,ChatOpenAI,Tools
    from browser_use.browser.profile import BrowserProfile
    configure_browser_sdk()
    # Explicitly remove code execution, file access and upload surfaces. Every
    # remaining model-chosen action passes the host's exact per-action approval.
    class GovernedTools(Tools):
        def __init__(self):
            super().__init__(exclude_actions=['evaluate','write_file','replace_file','read_file','upload_file','save_as_pdf','search'])
            self.sequence=0
        async def act(self,action,browser_session,**kwargs):
            requested=action.model_dump(exclude_unset=True)
            if set(requested)<={'done','extract','search_page','find_elements','scroll','find_text','screenshot','dropdown_options','wait'}:
                return await super().act(action,browser_session,**kwargs)
            before,evidence=await stable_browser_evidence(browser_session,requested)
            before_decoded=screenshot_pixel_hash(before.screenshot)
            before_url=before.url
            before_pixels=hashlib.sha256(before.screenshot.encode()).hexdigest()
            before_dom=hashlib.sha256(before.dom_state.llm_representation().encode()).hexdigest()
            details={'actions':requested,'url':before.url,**evidence}
            sequence=self.sequence
            deadline=time.monotonic()+config['max_seconds']
            while True:
                status=await asyncio.to_thread(gateway,config,'/action',{'sequence':sequence,'action':details})
                if status['state']=='approved':break
                if status['state']=='denied' or time.monotonic()>=deadline:raise PermissionError('Browser action not approved')
                await asyncio.sleep(0.5)
            after,refreshed=await fresh_browser_evidence(browser_session,requested,'after_approval')
            if refreshed!=evidence:
                print(json.dumps({'browser_evidence_changed':True,'url_changed':after.url!=before_url,'decoded_pixels_changed':screenshot_pixel_hash(after.screenshot)!=before_decoded,'screenshot_bytes_changed':hashlib.sha256(after.screenshot.encode()).hexdigest()!=before_pixels,'dom_changed':hashlib.sha256(after.dom_state.llm_representation().encode()).hexdigest()!=before_dom,'title_changed':refreshed['page_title']!=evidence['page_title'],'targets_changed':refreshed['targets']!=evidence['targets']}),file=sys.stderr,flush=True)
                raise PermissionError('Browser context changed after approval; a new review is required')
            self.sequence+=1
            return await super().act(action,browser_session,**kwargs)
    browser=Browser(headless=True,chromium_sandbox=True,use_cloud=False,enable_default_extensions=False,highlight_elements=False,dom_highlight_elements=False,browser_profile=BrowserProfile(demo_mode=False),permissions=[],keep_alive=False,executable_path="/usr/bin/chromium",allowed_domains=['https://'+h for h in config['allowed_hosts']],
                    proxy={'server':'http://gateway:8080','bypass':'gateway,localhost,127.0.0.1'},user_data_dir='/workspace/profile',downloads_path='/workspace/downloads')
    model=ChatOpenAI(model=config['model'],api_key=config['engine_token'],base_url='http://gateway:8080/v1',frequency_penalty=None,max_retries=0,timeout=35)
    agent=Agent(task=config['task'],llm=model,browser=browser,tools=GovernedTools(),use_vision=False,use_judge=False,calculate_cost=False,directly_open_url=False,max_actions_per_step=1,max_failures=1,enable_planning=False,file_system_path="/workspace/browser-files")
    try:
        history=await asyncio.wait_for(agent.run(max_steps=config['max_steps']),timeout=config['max_seconds'])
        return browser_result(history)
    except Exception:
        await browser_page_diagnostic(browser)
        raise
    finally:await browser.kill()


if __name__=='__main__':
    # The image/runtime boundary is enforced by the trusted broker, not by an
    # environment flag inside this executable.
    config=json.loads(sys.stdin.buffer.read(262145))
    result=software(config) if config['engine']=='openhands' else asyncio.run(browse(config))
    Path('/out/result.json').write_text(json.dumps(result))
