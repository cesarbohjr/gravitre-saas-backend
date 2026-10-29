from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import pytest
from app.services.native_runtime.engine import browser_evidence


def page(*,dom='indexed DOM',label='Submit'):
    node=SimpleNamespace(attributes={'aria-label':label,'value':'DO-NOT-READ-VALUE'},node_name='BUTTON',get_all_children_text=Mock(return_value='Submit'))
    state=SimpleNamespace(url='https://allowed.example',title='Review page',screenshot='fresh-pixels',dom_state=SimpleNamespace(llm_representation=lambda:dom,selector_map={12:node}))
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
    history=SimpleNamespace(is_done=lambda:True,is_successful=lambda:True,urls=lambda:['about:blank','https://example.com/observed'],final_result=lambda:'Observed fixture result')
    assert browser_result(history)=={'observations':[{'summary':'Observed fixture result','url':'https://example.com/observed'}]}


@pytest.mark.asyncio
async def test_fresh_browser_evidence_requests_uncached_screenshot():
    from app.services.native_runtime.engine import fresh_browser_evidence
    state=page();browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=state))
    observed,evidence=await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert observed is state and len(evidence['page_fingerprint'])==64
    browser.get_browser_state_summary.assert_awaited_once_with(include_screenshot=True,cached=False)


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
    first,second=blank_page(),blank_page();image=b'\x89PNG\r\n\x1a\nfixture-pixels'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[first,second]),take_screenshot=AsyncMock(return_value=image))
    observed,evidence=await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert first.screenshot is None and second.screenshot is None
    assert base64.b64decode(observed.screenshot)==image and len(evidence['page_fingerprint'])==64
    browser.take_screenshot.assert_awaited_once_with(full_page=False,format='png')
    assert browser.get_browser_state_summary.await_count==2


@pytest.mark.asyncio
@pytest.mark.parametrize('change',['page','target','capture_error'])
async def test_missing_ordinary_page_or_indexed_evidence_cannot_use_blank_page_recovery(change):
    from app.services.native_runtime.engine import fresh_browser_evidence
    state=blank_page()
    if change=='page':state.url='https://example.com/'
    if change=='target':state.dom_state.selector_map={1:object()}
    if change=='capture_error':state.state_error='capture failed'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=state),take_screenshot=AsyncMock())
    with pytest.raises(PermissionError):await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    browser.take_screenshot.assert_not_awaited()


@pytest.mark.asyncio
async def test_initial_page_change_during_screenshot_capture_invalidates_evidence():
    from app.services.native_runtime.engine import fresh_browser_evidence
    first,second=blank_page(),blank_page();second.url='https://example.com/changed'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[first,second]),take_screenshot=AsyncMock(return_value=b'\x89PNG\r\n\x1a\nfixture-pixels'))
    with pytest.raises(PermissionError,match='changed during'):await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert second.screenshot is None


@pytest.mark.asyncio
@pytest.mark.parametrize('image',[b'',b'not-png',b'\x89PNG\r\n\x1a\n'+bytes(3145721)])
async def test_blank_page_capture_must_be_bounded_actual_png(image):
    from app.services.native_runtime.engine import fresh_browser_evidence
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(return_value=blank_page()),take_screenshot=AsyncMock(return_value=image))
    with pytest.raises(PermissionError,match='actual blank-page screenshot'):await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert browser.get_browser_state_summary.await_count==1


@pytest.mark.asyncio
async def test_newer_sdk_screenshot_is_preserved_after_initial_blank_capture():
    from app.services.native_runtime.engine import fresh_browser_evidence
    first,second=blank_page(),blank_page();second.screenshot='newer-sdk-capture'
    browser=SimpleNamespace(get_browser_state_summary=AsyncMock(side_effect=[first,second]),take_screenshot=AsyncMock(return_value=b'\x89PNG\r\n\x1a\nolder-fixture-capture'))
    observed,_=await fresh_browser_evidence(browser,{'navigate':{'url':'https://example.com/'}},'before_approval')
    assert observed.screenshot=='newer-sdk-capture' and second.screenshot=='newer-sdk-capture'
