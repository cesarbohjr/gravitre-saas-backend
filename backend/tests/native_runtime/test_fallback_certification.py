"""Independent process/receiver acceptance for cross-adapter recovery fencing.

These tests use the real encrypted SQLite journal, real SIGKILL broker child
and a separate HTTP receiver with its own durable SQLite write counter.
They do NOT certify a production tenant, real Chromium handoff or identity
provider revocation; those require the native worker live acceptance job.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest
from cryptography.fernet import Fernet
from app.services.native_agent_adapters import AdapterScope
from app.services.native_runtime.store import Journal, LeaseLost

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"native-workers"))
from broker_process_contract import IndependentFixture, CrashBroker


def setup_job(tmp_path):
    private=tmp_path/"journal"
    private.mkdir(mode=0o700)
    j=Journal(str(private/"db.sqlite3"),Fernet.generate_key())
    scope=AdapterScope("org","agent","run")
    jid=j.enqueue(scope,"browser_use","request",{"task":{"allowed_hosts":["example.com"]}},actor="actor")
    old=j.claim("browser_use")
    j.save_browser_checkpoint(old,0,{"before_effect":True,
        "url":"https://example.com/","page_fingerprint":"a"*64})
    assert j.fence_browser_for_fallback(old,checkpoint_before_effect=True)
    return j,scope,jid,old


def record_audit(case, actual_writes, expected_writes, *, restarted, blocked_replay):
    """Persist receiver-owned counts for certification artifacts, not SDK claims."""
    target=os.environ.get("RECOVERY_AUDIT_PATH")
    if not target:return
    root=Path(target)
    root.mkdir(parents=True,exist_ok=True)
    result={"case":case,"actual_external_writes":actual_writes,
            "expected_external_writes":expected_writes,
            "unauthorized_or_duplicate_writes":max(0,actual_writes-expected_writes),
            "broker_restarted":restarted,"stale_replay_blocked":blocked_replay,
            "passed":actual_writes==expected_writes and blocked_replay}
    (root/(case+".json")).write_text(json.dumps(result,sort_keys=True))


def post(fixture, capability):
    req=Request(fixture.origin+"/write",data=json.dumps({"cap":capability}).encode(),
        headers={"Content-Type":"application/json"},method="POST")
    with urlopen(req,timeout=4) as result:
        assert result.status==204


def test_cancel_before_reservation_blocks_all_handoffs(tmp_path):
    journal,scope,jid,old=setup_job(tmp_path)
    assert journal.cancel(scope,jid)
    with pytest.raises(LeaseLost):journal.claim_fenced_handoff(scope,jid)
    assert not journal.active(old)


def test_cancel_after_reservation_blocks_activation(tmp_path):
    journal,scope,jid,_=setup_job(tmp_path)
    reservation=journal.claim_fenced_handoff(scope,jid)
    assert journal.cancel(scope,jid)
    with pytest.raises(LeaseLost):journal.activate_fenced_handoff(scope,jid,reservation)


def test_cancel_after_activation_blocks_action_gate_and_approval(tmp_path):
    journal,scope,jid,_=setup_job(tmp_path)
    reservation=journal.claim_fenced_handoff(scope,jid)
    active=journal.activate_fenced_handoff(scope,jid,reservation)
    request=journal.request_action(active,0,{"click":{"index":1}})
    assert request["state"]=="pending"
    assert journal.cancel(scope,jid)
    with pytest.raises(LeaseLost):journal.request_action(active,1,{"click":{"index":2}})
    with pytest.raises(PermissionError):
        journal.approve(scope,jid,request["id"],request["digest"],True)


def test_expired_or_revoked_lease_denies_approval(tmp_path):
    journal,scope,jid,_=setup_job(tmp_path)
    active=journal.activate_fenced_handoff(scope,jid,journal.claim_fenced_handoff(scope,jid))
    request=journal.request_action(active,0,{"click":{"index":1}})
    # Explicit persisted revocation, as occurs when the broker withdraws
    # authority. This is a lease fencing check, not a live IAM test.
    with journal.connect() as db:
        db.execute("UPDATE jobs SET lease=NULL WHERE id=?",(jid,))
    with pytest.raises(PermissionError):
        journal.approve(scope,jid,request["id"],request["digest"],True)
    assert not journal.active(active)


def test_concurrent_recovery_claims_issue_exactly_one_executable_lease(tmp_path):
    journal,scope,jid,old=setup_job(tmp_path)
    def attempt(_):
        try:
            reservation=journal.claim_fenced_handoff(scope,jid)
            return journal.activate_fenced_handoff(scope,jid,reservation)
        except LeaseLost:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(attempt,range(4)))
    winners=[r for r in results if r]
    assert len(winners)==1
    assert journal.active(winners[0])
    assert not journal.active(old)
    assert journal.get(scope,jid)["attempts"]==2


@pytest.mark.parametrize("crash_after_effect,expected_writes",[(False,0),(True,1)])
def test_real_sigkill_never_replays_independent_effect(tmp_path,crash_after_effect,expected_writes):
    case=tmp_path/"case"
    case.mkdir()
    token="approved-case"
    receiver=IndependentFixture(case/"independent.sqlite3",b"<h1>Evidence</h1>",capability=token)
    broker=CrashBroker(case/"broker-private")
    try:
        request=broker.approve({"actions":{"click":{"index":1}},
                                "page_fingerprint":"a"*64})
        assert request["state"]=="approved" and broker.authorized()
        if crash_after_effect:post(receiver,token)
        assert receiver.writes==expected_writes
        outcome=broker.kill_and_restart()
        assert outcome["broker_sigkill"] and outcome["new_broker_pid"]
        assert outcome["replayed_claims"]==0
        assert outcome["journal_state"]=="uncertain"
        assert not broker.authorized()
        # No regenerated approval is present to authorize another write.
        for _ in range(3):
            if broker.authorized():post(receiver,token)
        assert receiver.writes==expected_writes
        with pytest.raises(HTTPError) as denied:
            post(receiver,"stale-or-unscoped")
        assert denied.value.code==403
        assert receiver.writes==expected_writes
        record_audit("sigkill_"+("after" if crash_after_effect else "before")+"_effect",
            receiver.writes,expected_writes,restarted=True,blocked_replay=not broker.authorized())
    finally:
        broker.close()
        receiver.close()


def test_lost_submit_ack_does_not_authorize_second_write(tmp_path):
    case=tmp_path/"ack"
    case.mkdir()
    token="approved-case"
    receiver=IndependentFixture(case/"independent.sqlite3",b"<h1>Evidence</h1>",capability=token)
    broker=CrashBroker(case/"broker-private")
    try:
        broker.approve({"actions":{"click":{"index":1}},
                        "page_fingerprint":"a"*64})
        receiver.hold=True
        import threading
        errors=[]
        def send():
            try:post(receiver,token)
            except Exception as error:errors.append(type(error).__name__)
        thread=threading.Thread(target=send,daemon=True)
        thread.start()
        deadline=time.monotonic()+4
        while receiver.writes!=1 and time.monotonic()<deadline:time.sleep(.025)
        assert receiver.writes==1
        evidence=broker.kill_and_restart()
        assert evidence["journal_state"]=="uncertain" and evidence["replayed_claims"]==0
        assert not broker.authorized()
        receiver.hold=False
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert receiver.writes==1
        record_audit("lost_submit_ack",receiver.writes,1,
                     restarted=True,blocked_replay=not broker.authorized())
    finally:
        receiver.hold=False
        broker.close()
        receiver.close()


def test_runtime_revocation_between_actions_blocks_second_effect(tmp_path):
    """Actual runtime guard must deny actions after authority is withdrawn."""
    from app.services.native_runtime.runtime import NativeRuntime
    private=tmp_path/"runtime-journal"
    private.mkdir(mode=0o700)
    journal=Journal(str(private/"db.sqlite3"),Fernet.generate_key())
    scope=AdapterScope("org","agent","run")
    claims={"scope":{"org_id":"org","agent_id":"agent","run_id":"run"},
            "actor":"actor","engine":"browser_use"}
    job_id=journal.enqueue(scope,"browser_use","revocation",
        {"claims":claims,"task":{"allowed_hosts":["example.com"]}},
        actor="actor")
    original=journal.claim("browser_use")
    journal.save_browser_checkpoint(original,0,{"before_effect":True,
        "url":"https://example.com/","page_fingerprint":"a"*64})
    assert journal.fence_browser_for_fallback(original,checkpoint_before_effect=True)
    authority={"valid":True}
    class GuardedRunner:
        def __init__(self):
            self.attempted=0
        def cleanup(self,_):
            pass
        def execute(self,job,*,guard,action_gate):
            first=action_gate(0,{"click":{"index":1}})
            assert first["state"]=="pending"
            authority["valid"]=False
            self.attempted+=1
            # This must fail in host runtime before a second request/write.
            action_gate(1,{"click":{"index":2}})
            raise AssertionError("Revoked action incorrectly authorized")
    runner=GuardedRunner()
    runtime=NativeRuntime(journal,None,None,runner,lambda _:None)
    def authorize(_):
        if not authority["valid"]:raise PermissionError("revoked")
        return "same-route"
    runtime.authorize=authorize
    assert runtime._run_verified_playwright_fallback(original)=="fallback_reconciliation_required"
    assert runner.attempted==1
    assert len(journal.actions(scope,job_id))==1
    assert journal.get(scope,job_id)["state"]=="uncertain"
