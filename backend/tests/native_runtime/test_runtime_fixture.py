from pathlib import Path
import runpy


PAGE_CHECKS=('state_present','title_observed','host_observed','body_observed')

def page_ok(result):
    return all(result[key] for key in PAGE_CHECKS)


observe=runpy.run_path(str(Path(__file__).resolve().parents[2]/'native-workers/runtime_contract.py'))['browser_fixture_observation']


def state(title='Web form',body='Text input',url='https://www.selenium.dev/selenium/web/web-form.html',active='ABCD'):
    return '<browser_state>\nCurrent tab: '+active+'\nAvailable tabs:\nTab ABCD: '+url+' - '+title+'\nInteractive elements:\n'+body+'\n</browser_state>'


def test_browser_readback_uses_state_before_trailing_sdk_warning():
    messages=[{'role':'user','content':state()},{'role':'user','content':'Last step: finish now.'}]
    assert page_ok(observe(messages))


def test_task_and_history_markers_cannot_certify_a_page():
    assert not any(observe([{'role':'user','content':'Web form Text input https://www.selenium.dev/selenium/web/web-form.html'}]).values())
    result=observe([{'role':'user','content':state(title='Loading',body='empty page')+'\n<agent_history>Web form Text input</agent_history>'}])
    assert not result['title_observed'] and not result['body_observed']


def test_latest_empty_state_replaces_older_successful_page():
    assert not page_ok(observe([{'role':'user','content':state()},{'role':'user','content':state(title='Loading',body='empty page')}]))


def test_inactive_tab_wrong_origin_and_state_errors_cannot_pass():
    for content in (state(active='EEEE'),state(url='https://other.example/'),state(url='https://www.selenium.dev:8443/selenium/web/web-form.html'),state(url='https://user@www.selenium.dev/selenium/web/web-form.html'),state().replace('Interactive elements:','<browser_state_error>unavailable</browser_state_error>\nInteractive elements:')):
        assert not page_ok(observe([{'role':'user','content':content}]))


def test_text_content_parts_are_read_without_images_or_raw_history():
    assert page_ok(observe([{'role':'user','content':[{'type':'text','text':state()}]},{'role':'assistant','content':'untrusted scripted reply'}]))


def test_submit_index_and_completion_require_actual_latest_browser_state():
    form=observe([{'role':'user','content':state(body='Text input\n[17]<button type=submit>Submit</button>')}])
    assert page_ok(form) and form['submit_index']==17 and not form['submitted']
    submitted=observe([{'role':'user','content':state(title='Web form - target page',
        url='https://www.selenium.dev/selenium/web/submitted-form.html?my-text=',body='Received!')}])
    assert submitted['submitted'] and not page_ok(submitted)
    for url in ('https://evil.example/selenium/web/submitted-form.html',
                'http://www.selenium.dev/selenium/web/submitted-form.html',
                'https://www.selenium.dev:8443/selenium/web/submitted-form.html'):
        assert not observe([{'role':'user','content':state(url=url,body='Received!')}])['submitted']
