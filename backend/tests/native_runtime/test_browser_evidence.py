from types import SimpleNamespace
from unittest.mock import Mock
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
    history=SimpleNamespace(is_done=lambda:done,is_successful=lambda:success,urls=lambda:urls,final_result=lambda:summary,errors=lambda:['ValueError: operation not permitted PRIVATE-PAYLOAD'])
    with pytest.raises((RuntimeError,ValueError)):browser_result(history)
    assert 'PRIVATE-PAYLOAD' not in capsys.readouterr().err


def test_browser_result_uses_actual_observed_page_without_fallback():
    from app.services.native_runtime.engine import browser_result
    history=SimpleNamespace(is_done=lambda:True,is_successful=lambda:True,urls=lambda:['about:blank','https://example.com/observed'],final_result=lambda:'Observed fixture result')
    assert browser_result(history)=={'observations':[{'summary':'Observed fixture result','url':'https://example.com/observed'}]}
