from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from cryptography.fernet import Fernet
from app.services.native_agent_adapters import AdapterScope
from app.services.native_runtime.store import Journal,LeaseLost
S=AdapterScope('tenant-a','agent-a','run-a')
@pytest.fixture
def journal(tmp_path):
    root=tmp_path/'private';root.mkdir(mode=0o700)
    return Journal(str(root/'queue.sqlite'),Fernet.generate_key())

def test_encrypted_restart_idempotency_and_scope(journal):
    job=journal.enqueue(S,'openhands','request',{'task':'SECRET-CUSTOMER-TASK'},now=10)
    assert journal.enqueue(S,'openhands','request',{'task':'SECRET-CUSTOMER-TASK'},now=10)==job
    with pytest.raises(ValueError):journal.enqueue(S,'openhands','request',{'task':'changed'},now=10)
    assert journal.get(AdapterScope('other','agent-a','run-a'),job,material=True) is None
    db=sqlite3.connect(journal.path)
    assert b'SECRET-CUSTOMER-TASK' not in db.execute('SELECT payload FROM jobs').fetchone()[0]
    db.close()
    assert journal.get(S,job,material=True)['payload']=={'task':'SECRET-CUSTOMER-TASK'}
    assert 'payload' not in journal.get(S,job)

def test_atomic_claim_and_stale_worker_cannot_commit(journal):
    journal.enqueue(S,'langfuse','one',{'metrics':{}},now=10)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=list(pool.map(lambda _:journal.claim('langfuse',now=10,lease_seconds=1),range(2)))
    first=next(j for j in jobs if j)
    assert sum(j is not None for j in jobs)==1
    second=journal.claim('langfuse',now=12)
    assert second and first['lease']!=second['lease']
    with pytest.raises(LeaseLost):journal.update(first,'delivered',now=12)
    journal.update(second,'delivered',now=12)

def test_native_lease_loss_never_replays_execution(journal):
    id=journal.enqueue(S,'openhands','one',{},now=10)
    job=journal.claim('openhands',now=10,lease_seconds=1)
    assert journal.claim('openhands',now=12) is None
    assert journal.get(S,id)['state']=='uncertain'
    assert not journal.active(job,now=12)

def test_cancellation_fences_results_and_clears_task(journal):
    id=journal.enqueue(S,'browser_use','one',{'task':'private'})
    job=journal.claim('browser_use')
    assert journal.cancel(S,id)
    assert not journal.active(job)
    assert journal.get(S,id,material=True)['payload'] is None
    with pytest.raises(LeaseLost):journal.update(job,'completed',result={'secret':'not written'})

def test_consent_expiry_schedules_deletion_instead_of_false_erasure(journal):
    id=journal.enqueue(S,'langfuse','one',{'trace_id':'ref'},now=10,ttl=1)
    assert journal.claim('langfuse',now=12) is None
    job=journal.claim('langfuse_delete',now=12)
    assert job and job['id']==id and job['payload']=={'trace_id':'ref'}

def test_no_in_memory_or_insecure_storage(tmp_path):
    with pytest.raises(ValueError):Journal(':memory:',Fernet.generate_key())
    folder=tmp_path/'public';folder.mkdir(mode=0o755)
    with pytest.raises(ValueError):Journal(str(folder/'q'),Fernet.generate_key())


def test_telemetry_deletion_keeps_the_original_idempotency_identity(journal):
    scope=AdapterScope('org','agent','run')
    payload={'metrics':'bounded'}
    id=journal.enqueue(scope,'langfuse','stable-receipt',payload,actor='actor')
    job=journal.claim('langfuse')
    journal.request_deletion(job)
    assert journal.enqueue(scope,'langfuse','stable-receipt',payload,actor='actor')==id
    assert journal.get(scope,id)['kind']=='langfuse_delete'
