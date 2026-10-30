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
