"""Real child-process and server-owned counter contracts (no SDK mocks)."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'native-workers'))
from broker_process_contract import IndependentFixture, CrashBroker


def test_independent_server_commits_only_actual_http_writes(tmp_path):
    path=tmp_path/'counter.sqlite3'
    fixture=IndependentFixture(path,b'<button id="commit">Commit</button>')
    try:
        assert fixture.pid!=os.getpid() and fixture.writes==0
        with urllib.request.urlopen(fixture.origin+'/page') as response:
            assert response.status==200
        assert fixture.writes==0
        with urllib.request.urlopen(urllib.request.Request(fixture.origin+'/write',data=b'',method='POST')) as response:
            assert response.status==204
        assert fixture.writes==1
        fixture.mutated=True
        with urllib.request.urlopen(fixture.origin+'/state') as response:
            assert json.load(response)=={'mutated':True}
        assert fixture.writes==1
    finally:fixture.close()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM writes').fetchone()[0]==1


def test_real_broker_sigkill_new_pid_and_durable_no_replay(tmp_path):
    broker=CrashBroker(tmp_path/'private')
    try:
        assert broker.ready['pid']!=os.getpid()
        request=broker.approve({'actions':{'click':{'index':1}},'page_fingerprint':'a'*64})
        assert request['state']=='approved' and broker.authorized()
        recovered=broker.kill_and_restart()
        assert recovered=={'broker_sigkill':True,'new_broker_pid':True,
            'journal_state':'uncertain','replayed_claims':0,'persisted_action_count':1}
        assert not broker.authorized()
    finally:broker.close()


def test_shared_session_helpers_do_not_require_broker_test_module():
    import subprocess
    script='''import importlib.abc, sys
class NoBroker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'broker_process_contract':
            raise ModuleNotFoundError('broker helper absent from candidate image')
sys.meta_path.insert(0, NoBroker())
import browser_adapter_benchmark
assert browser_adapter_benchmark.PlaywrightSession
'''
    import os
    environment={**os.environ,'PYTHONPATH':os.pathsep.join(sys.path)}
    result=subprocess.run([sys.executable,'-c',script],env=environment,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr.decode()


def test_capability_protected_receiver_rejects_unauthorized_effect(tmp_path):
    from urllib.error import HTTPError
    fixture=IndependentFixture(tmp_path/'counter.sqlite3',b'<h1>Fixture</h1>',capability='fixture-capability')
    try:
        for token in ('','incorrect'):
            request=urllib.request.Request(fixture.origin+'/write',data=json.dumps({'cap':token}).encode(),
                headers={'Content-Type':'application/json'},method='POST')
            try:urllib.request.urlopen(request,timeout=2)
            except HTTPError as error:assert error.code==403
            else:raise AssertionError('Unauthorized receiver write accepted')
        assert fixture.writes==0
        with urllib.request.urlopen(urllib.request.Request(fixture.origin+'/write',
            data=b'{"cap":"fixture-capability"}',headers={'Content-Type':'application/json'},method='POST'),timeout=2) as response:
            assert response.status==204
        assert fixture.writes==1
        fixture.register_capability('second-case')
        assert fixture.count('fixture-capability')==1 and fixture.count('second-case')==0
        with urllib.request.urlopen(urllib.request.Request(fixture.origin+'/write',
            data=b'{"cap":"second-case"}',headers={'Content-Type':'application/json'},method='POST'),timeout=2) as response:
            assert response.status==204
        assert fixture.count('fixture-capability')==1 and fixture.count('second-case')==1 and fixture.writes==2
    finally:fixture.close()


def test_receiver_commit_precedes_delayed_acknowledgement(tmp_path):
    import threading,time
    fixture=IndependentFixture(tmp_path/'counter.sqlite3',b'<h1>Fixture</h1>',capability='fixture-capability')
    response=[]
    try:
        fixture.hold=True
        def post():
            with urllib.request.urlopen(urllib.request.Request(fixture.origin+'/write',
                data=b'{"cap":"fixture-capability"}',headers={'Content-Type':'application/json'},method='POST'),timeout=5) as value:
                response.append(value.status)
        thread=threading.Thread(target=post);thread.start()
        deadline=time.monotonic()+3
        while fixture.writes!=1 and time.monotonic()<deadline:time.sleep(.05)
        assert fixture.writes==1 and not response
        fixture.hold=False;thread.join(timeout=3)
        assert response==[204]
    finally:fixture.hold=False;fixture.close()


def test_real_broker_restart_fences_independent_receiver_writes_before_and_after_effect(tmp_path):
    """SIGKILL a separate approval broker around a committed HTTP side effect.

    The receiver, not the browser adapter or test, owns the durable write count.
    A restarted broker cannot reclaim the original intent or replay that effect.
    """
    import pytest
    from urllib.error import HTTPError

    for crash_after_effect in (False, True):
        case = tmp_path / ('after' if crash_after_effect else 'before')
        case.mkdir()
        token = 'isolated-' + case.name
        receiver = IndependentFixture(case / 'writes.sqlite3', b'<h1>Fixture</h1>', capability=token)
        broker = CrashBroker(case / 'private')
        try:
            request = broker.approve({'actions': {'click': {'index': 1}}, 'page_fingerprint': 'a' * 64})
            assert request['state'] == 'approved' and broker.authorized()

            def effect(cap):
                payload = json.dumps({'cap': cap}).encode()
                call = urllib.request.Request(receiver.origin + '/write', data=payload,
                    headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(call, timeout=3) as response:
                    assert response.status == 204

            if crash_after_effect:
                effect(token)
                assert receiver.writes == 1
            else:
                assert receiver.writes == 0

            recovery = broker.kill_and_restart()
            assert recovery['broker_sigkill'] and recovery['new_broker_pid']
            assert recovery['journal_state'] == 'uncertain'
            assert recovery['replayed_claims'] == 0 and recovery['persisted_action_count'] == 1
            assert not broker.authorized()

            # No old approval may authorize another external side effect.
            for _ in range(2):
                if broker.authorized():
                    effect(token)
            assert receiver.writes == (1 if crash_after_effect else 0)

            # Independent receiver rejects an unscoped write even after restart.
            denied = urllib.request.Request(receiver.origin + '/write',
                data=b'{"cap":"wrong-capability"}',
                headers={'Content-Type': 'application/json'}, method='POST')
            with pytest.raises(HTTPError) as rejected:
                urllib.request.urlopen(denied, timeout=3)
            assert rejected.value.code == 403
            assert receiver.writes == (1 if crash_after_effect else 0)
        finally:
            broker.close()
            receiver.close()
