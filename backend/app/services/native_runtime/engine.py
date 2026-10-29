"""Disposable SDK entrypoint. Never run directly on a backend/worker host."""
from __future__ import annotations
import asyncio
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys
import time
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


def browser_evidence(state,requested):
    # Bind approval to both visible pixels and the current indexed DOM. A
    # visually identical page with a changed target must invalidate approval.
    dom=state.dom_state.llm_representation()
    if not state.screenshot or len(state.screenshot)>4194304 or len(dom)>2097152:
        raise PermissionError('Bounded fresh browser evidence required')
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
    fingerprint=hashlib.sha256((state.url+'\n'+state.screenshot+'\n'+dom).encode()).hexdigest()
    return {'page_fingerprint':fingerprint,'page_title':str(state.title)[:300],'targets':targets}


async def browse(config):
    from browser_use import Agent,Browser,ChatOpenAI,Tools
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
            before=await browser_session.get_browser_state_summary(include_screenshot=True,cached=False)
            evidence=browser_evidence(before,requested)
            details={'actions':requested,'url':before.url,**evidence}
            sequence=self.sequence
            deadline=time.monotonic()+config['max_seconds']
            while True:
                status=await asyncio.to_thread(gateway,config,'/action',{'sequence':sequence,'action':details})
                if status['state']=='approved':break
                if status['state']=='denied' or time.monotonic()>=deadline:raise PermissionError('Browser action not approved')
                await asyncio.sleep(0.5)
            after=await browser_session.get_browser_state_summary(include_screenshot=True,cached=False)
            if browser_evidence(after,requested)!=evidence:
                raise PermissionError('Browser context changed after approval; a new review is required')
            self.sequence+=1
            return await super().act(action,browser_session,**kwargs)
    browser=Browser(headless=True,chromium_sandbox=True,use_cloud=False,enable_default_extensions=False,permissions=[],keep_alive=False,executable_path="/usr/bin/chromium",allowed_domains=['https://'+h for h in config['allowed_hosts']],
                    proxy={'server':'http://gateway:8080','bypass':'gateway,localhost,127.0.0.1'},user_data_dir='/workspace/profile',downloads_path='/workspace/downloads')
    model=ChatOpenAI(model=config['model'],api_key=config['engine_token'],base_url='http://gateway:8080/v1',frequency_penalty=None,max_retries=0,timeout=35)
    agent=Agent(task=config['task'],llm=model,browser=browser,tools=GovernedTools(),use_vision=False,use_judge=False,calculate_cost=False,directly_open_url=False,max_actions_per_step=1,max_failures=1,enable_planning=False,file_system_path="/workspace/browser-files")
    try:
        history=await asyncio.wait_for(agent.run(max_steps=config['max_steps']),timeout=config['max_seconds'])
        summary=str(history.final_result() or 'No final browser result was supplied.')[:2000]
        urls=history.urls()
        url=next((u for u in reversed(urls) if isinstance(u,str) and u.startswith('https://')),'https://'+config['allowed_hosts'][0])
        return {'observations':[{'summary':summary,'url':url}]}
    finally:await browser.kill()


if __name__=='__main__':
    # The image/runtime boundary is enforced by the trusted broker, not by an
    # environment flag inside this executable.
    config=json.loads(sys.stdin.buffer.read(262145))
    result=software(config) if config['engine']=='openhands' else asyncio.run(browse(config))
    Path('/out/result.json').write_text(json.dumps(result))
