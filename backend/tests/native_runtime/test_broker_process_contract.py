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
