from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import pytest
import base64,io
from PIL import Image
from app.services.native_runtime.engine import browser_evidence


def encoded_pixels(*,color='white',compression=6,size=(4,4)):
    buffer=io.BytesIO()
    Image.new('RGB',size,color).save(buffer,format='PNG',compress_level=compression)
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def page(*,dom='indexed DOM',label='Submit'):
    node=SimpleNamespace(attributes={'aria-label':label,'value':'DO-NOT-READ-VALUE'},node_name='BUTTON',get_all_children_text=Mock(return_value='Submit'))
    state=SimpleNamespace(url='https://allowed.example',title='Review page',screenshot=encoded_pixels(),dom_state=SimpleNamespace(llm_representation=lambda:dom,selector_map={12:node}))
    return state


def test_approval_binds_visible_and_dom_targets_without_input_values():
    action={'click':{'index':12}}
    first=browser_evidence(page(),action)
    assert first['targets']==[{'index':12,'tag':'BUTTON','label':'Submit'}]
    assert 'DO-NOT-READ-VALUE' not in str(first)
    assert first!=browser_evidence(page(dom='DOM changed but pixels identical'),action)
    assert first!=browser_evidence(page(label='Delete all'),action)


def test_ambiguous_coordinate_or_missing_target_cannot_be_approved():
    for action in [{'click':{'coordinate_x':1,'coordinate_y':2}},{'click':{'index':99}},{'click':{'index':12,'coordinate_x':1}}]:
        with pytest.raises(PermissionError):browser_evidence(page(),action)
    state=page();state.screenshot=None
    with pytest.raises(PermissionError):browser_evidence(state,{'click':{'index':12}})


@pytest.mark.parametrize('done,success,urls,summary',[
    (False,None,[],None),(True,False,['https://example.com/'],'failed'),
    (True,None,['https://example.com/'],'unverified'),
    (True,True,[],'no observed page'),(True,True,['https://example.com/'],None),
])
def test_incomplete_browser_history_cannot_become_a_completed_observation(done,success,urls,summary,capsys):
    from app.services.native_runtime.engine import browser_result
    history=SimpleNamespace(is_done=lambda:done,is_successful=lambda:success,urls=lambda:urls,final_result=lambda:summary,errors=lambda:['ValueError: operation not permitted PRIVATE-PAYLOAD TenantSecretError: hidden'])
    with pytest.raises((RuntimeError,ValueError)):browser_result(history)
    diagnostic=capsys.readouterr().err
    assert 'PRIVATE-PAYLOAD' not in diagnostic and 'TenantSecretError' not in diagnostic


def test_browser_result_uses_actual_observed_page_without_fallback():
    from app.services.native_runtime.engine import browser_result
    history=SimpleNamespace(is_done=lambda:True,is_successful=lambda:True,errors=lambda:[],urls=lambda:['about:blank','https://example.com/observed'],final_result=lambda:'Observed fixture result')
    assert browser_result(history)=={'observations':[{'summary':'Observed fixture result','url':'https://example.com/observed'}]}


@pytest.mark.asyncio
async def test_approval_collects_uncached_dom_and_actual_viewport_pixels():
    from app.services.native_runtime.engine import fresh_browser_evidence
    state=page();browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=state),take_screenshot=AsyncMock(return_value=base64.b64decode(encoded_pixels())))
    observed,evidence=await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert observed is not state and len(evidence['page_fingerprint'])==64
    assert browser.get_browser_state_summary.await_count==2
    assert all(call.kwargs=={'include_screenshot':False,'cached':False} for call in browser.get_browser_state_summary.await_args_list)
    browser.take_screenshot.assert_awaited_once_with(full_page=False,format='png')


@pytest.mark.asyncio
async def test_browser_evidence_failure_exposes_only_safe_stage_and_source(capsys):
    from app.services.native_runtime.engine import fresh_browser_evidence
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=ValueError('PRIVATE-PAGE-CONTENT')))
    with pytest.raises(ValueError):await fresh_browser_evidence(browser,{},'before_approval')
    diagnostic=capsys.readouterr().err
    assert 'before_approval' in diagnostic and 'ValueError' in diagnostic
    assert 'PRIVATE-PAGE-CONTENT' not in diagnostic


def blank_page():
    state=page(dom='empty current page DOM');state.url='about:blank';state.screenshot=None;state.dom_state.selector_map={}
    return state


@pytest.mark.asyncio
async def test_initial_navigation_approval_uses_real_capture_without_mutating_sdk_cache():
    import base64
    from app.services.native_runtime.engine import fresh_browser_evidence
    first,second=blank_page(),blank_page();image=base64.b64decode(encoded_pixels())
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[first,second]),take_screenshot=AsyncMock(return_value=image))
    observed,evidence=await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert first.screenshot is None and second.screenshot is None
    assert base64.b64decode(observed.screenshot)==image and len(evidence['page_fingerprint'])==64
    browser.take_screenshot.assert_awaited_once_with(full_page=False,format='png')
    assert browser.get_browser_state_summary.await_count==2


@pytest.mark.asyncio
@pytest.mark.parametrize('context',['ordinary','indexed','initial'])
async def test_model_preview_cannot_replace_missing_actual_viewport_evidence(context):
    from app.services.native_runtime.engine import fresh_browser_evidence
    state=page() if context!='initial' else blank_page()
    state.screenshot='SDK-MODEL-PREVIEW'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=state),take_screenshot=AsyncMock(return_value=None))
    action={'click':{'index':12}} if context=='indexed' else {'navigate':{'url':'https://example.com/'}}
    with pytest.raises(PermissionError):await fresh_browser_evidence(browser,action,'before_approval')
    browser.take_screenshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_unavailable_dom_cannot_be_replaced_by_viewport_capture():
    from app.services.native_runtime.engine import fresh_browser_evidence
    state=page();state.state_error='capture failed'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=state),take_screenshot=AsyncMock())
    with pytest.raises(PermissionError):await fresh_browser_evidence(browser,{'click':{'index':12}},'before_approval')
    browser.take_screenshot.assert_not_awaited()


@pytest.mark.asyncio
async def test_initial_page_change_during_screenshot_capture_invalidates_evidence():
    from app.services.native_runtime.engine import fresh_browser_evidence
    first,second=blank_page(),blank_page();second.url='https://example.com/changed'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[first,second]),take_screenshot=AsyncMock(return_value=base64.b64decode(encoded_pixels())))
    with pytest.raises(PermissionError,match='changed during'):await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert second.screenshot is None


@pytest.mark.asyncio
@pytest.mark.parametrize('image',[b'',b'not-png',b'\x89PNG\r\n\x1a\n'+bytes(3145721)])
async def test_viewport_capture_must_be_bounded_actual_png(image):
    from app.services.native_runtime.engine import fresh_browser_evidence
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=blank_page()),take_screenshot=AsyncMock(return_value=image))
    with pytest.raises(PermissionError,match='actual viewport screenshot'):await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert browser.get_browser_state_summary.await_count==1


@pytest.mark.asyncio
async def test_sdk_preview_is_not_mixed_with_approval_viewport_capture():
    from app.services.native_runtime.engine import fresh_browser_evidence
    first,second=blank_page(),blank_page();second.screenshot=encoded_pixels(compression=9)
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[first,second]),take_screenshot=AsyncMock(return_value=base64.b64decode(encoded_pixels(compression=0))))
    observed,_=await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert base64.b64decode(observed.screenshot)==base64.b64decode(encoded_pixels(compression=0))
    assert second.screenshot==encoded_pixels(compression=9)


@pytest.mark.asyncio
@pytest.mark.parametrize('change',['dom','title','target'])
async def test_same_pixels_cannot_mask_context_or_target_changes_during_capture(change):
    from app.services.native_runtime.engine import fresh_browser_evidence
    before,after=page(),page()
    if change=='dom':after.dom_state.llm_representation=lambda:'changed DOM'
    if change=='title':after.title='changed page title'
    if change=='target':after.dom_state.selector_map[12].attributes['aria-label']='Delete all'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[before,after]),take_screenshot=AsyncMock(return_value=base64.b64decode(encoded_pixels())))
    with pytest.raises(PermissionError,match='changed during'):await fresh_browser_evidence(browser,{'click':{'index':12}},'after_approval')


def test_pixel_fingerprint_ignores_encoding_metadata_but_keeps_pixels_dimensions_and_dom():
    first,second=page(),page();first.screenshot=encoded_pixels(compression=0);second.screenshot=encoded_pixels(compression=9)
    assert first.screenshot!=second.screenshot
    assert browser_evidence(first,{})==browser_evidence(second,{})
    changed=page();changed.screenshot=encoded_pixels(color='black')
    assert browser_evidence(first,{})!=browser_evidence(changed,{})
    changed.screenshot=encoded_pixels(size=(2,8))
    assert browser_evidence(first,{})!=browser_evidence(changed,{})
    assert browser_evidence(first,{})!=browser_evidence(page(dom='changed DOM'),{})


@pytest.mark.parametrize('encoded',['not-base64',base64.b64encode(b'not-an-image').decode()])
def test_invalid_pixel_evidence_cannot_be_approved(encoded):
    state=page();state.screenshot=encoded
    with pytest.raises(PermissionError):browser_evidence(state,{})


def test_self_reported_done_cannot_hide_browser_action_errors(capsys):
    from app.services.native_runtime.engine import browser_result
    history=SimpleNamespace(is_done=lambda:True,is_successful=lambda:True,errors=lambda:['PermissionError: PRIVATE-PAGE'],urls=lambda:['https://example.com/'],final_result=lambda:'claimed success')
    with pytest.raises(RuntimeError):browser_result(history)
    assert 'PRIVATE-PAGE' not in capsys.readouterr().err


@pytest.mark.asyncio
async def test_initial_paint_must_stabilize_before_review(monkeypatch):
    from app.services.native_runtime import engine
    first,settled=page(),page()
    first.screenshot=encoded_pixels(color='black')
    captures=AsyncMock(side_effect=[(first,browser_evidence(first,{})),(settled,browser_evidence(settled,{})),(settled,browser_evidence(settled,{}))])
    monkeypatch.setattr(engine,'fresh_browser_evidence',captures)
    monkeypatch.setattr(engine.asyncio,'sleep',AsyncMock())
    state,evidence=await engine.stable_browser_evidence(object(),{})
    assert state is settled and evidence==browser_evidence(settled,{})
    assert captures.await_count==3
    assert all(call.args[2]=='before_approval' for call in captures.await_args_list)


@pytest.mark.asyncio
async def test_animated_or_changing_page_has_bounded_review_failure(monkeypatch):
    from app.services.native_runtime import engine
    captures=AsyncMock(side_effect=[(page(),{'page_fingerprint':str(i)}) for i in range(6)])
    monkeypatch.setattr(engine,'fresh_browser_evidence',captures)
    monkeypatch.setattr(engine.asyncio,'sleep',AsyncMock())
    with pytest.raises(PermissionError,match='did not stabilize'):
        await engine.stable_browser_evidence(object(),{})
    assert captures.await_count==6
