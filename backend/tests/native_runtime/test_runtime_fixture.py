from pathlib import Path
import runpy


observe=runpy.run_path(str(Path(__file__).resolve().parents[2]/'native-workers/runtime_contract.py'))['browser_fixture_observation']


def state(title='Example Domain',body='Example Domain',url='https://example.com/',active='ABCD'):
    return '<browser_state>\nCurrent tab: '+active+'\nAvailable tabs:\nTab ABCD: '+url+' - '+title+'\nInteractive elements:\n'+body+'\n</browser_state>'


def test_browser_readback_uses_state_before_trailing_sdk_warning():
    messages=[{'role':'user','content':state()},{'role':'user','content':'Last step: finish now.'}]
    assert all(observe(messages).values())


def test_task_and_history_markers_cannot_certify_a_page():
    assert not any(observe([{'role':'user','content':'Example Domain https://example.com/'}]).values())
    result=observe([{'role':'user','content':state(title='Loading',body='empty page')+'\n<agent_history>Example Domain</agent_history>'}])
    assert not result['title_observed'] and not result['body_observed']


def test_latest_empty_state_replaces_older_successful_page():
    assert not all(observe([{'role':'user','content':state()},{'role':'user','content':state(title='Loading',body='empty page')}]).values())


def test_inactive_tab_wrong_origin_and_state_errors_cannot_pass():
    for content in (state(active='EEEE'),state(url='https://other.example/'),state().replace('Interactive elements:','<browser_state_error>unavailable</browser_state_error>\nInteractive elements:')):
        assert not all(observe([{'role':'user','content':content}]).values())


def test_text_content_parts_are_read_without_images_or_raw_history():
    assert all(observe([{'role':'user','content':[{'type':'text','text':state()}]},{'role':'assistant','content':'untrusted scripted reply'}]).values())
