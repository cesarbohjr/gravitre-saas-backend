"""Encrypted durable journal with atomic leases and fail-closed replay semantics.

Use a private persistent volume. This is deliberately not an in-memory fallback.
Every caller supplies authenticated tenant/agent/run scope; payloads and results
are encrypted at rest, and neither tasks nor provider errors enter public status.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any
from contextlib import contextmanager
from uuid import uuid4
from cryptography.fernet import Fernet
from app.services.native_agent_adapters import AdapterScope

TERMINAL = frozenset({'delivered','completed','failed','cancelled','expired','uncertain','deleted'})


class LeaseLost(RuntimeError):
    pass


class Journal:
    def __init__(self, path: str, encryption_key: bytes):
        target=Path(path)
        if not target.is_absolute() or target.is_symlink() or str(target)==':memory:':
            raise ValueError('A private absolute persistent journal path is required')
        self.cipher=Fernet(encryption_key)
        if not target.parent.exists(): target.parent.mkdir(parents=True, mode=0o700)
        if target.parent.stat().st_mode & 0o077:
            raise ValueError('Journal directory must be private (0700)')
        fd=os.open(str(target),os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
        os.close(fd)
        if target.stat().st_mode & 0o077: raise ValueError('Journal file must be private (0600)')
        self.path=str(target)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, org TEXT NOT NULL, agent TEXT NOT NULL, run TEXT NOT NULL,
              kind TEXT NOT NULL, dedupe TEXT NOT NULL, fingerprint TEXT NOT NULL, payload BLOB, actor TEXT NOT NULL DEFAULT '',
              state TEXT NOT NULL, phase TEXT NOT NULL DEFAULT 'submit', attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL, next_at REAL NOT NULL, expires_at REAL NOT NULL,
              lease TEXT, lease_until REAL, error_code TEXT, result BLOB, created_at REAL NOT NULL,
              UNIQUE(org,agent,run,dedupe));
            CREATE TABLE IF NOT EXISTS telemetry_consent (org TEXT, agent TEXT, run TEXT, enabled INTEGER NOT NULL, expires_at REAL NOT NULL, PRIMARY KEY(org,agent,run));
            CREATE TABLE IF NOT EXISTS action_requests (id TEXT PRIMARY KEY, job TEXT NOT NULL, sequence INTEGER NOT NULL, digest TEXT NOT NULL, payload BLOB NOT NULL, state TEXT NOT NULL, UNIQUE(job,sequence));
            CREATE TABLE IF NOT EXISTS authority_uses (key TEXT PRIMARY KEY, operation TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS browser_checkpoints (job TEXT PRIMARY KEY, lease TEXT NOT NULL, sequence INTEGER NOT NULL, payload BLOB NOT NULL, created_at REAL NOT NULL);
            CREATE TRIGGER IF NOT EXISTS native_action_erase AFTER UPDATE OF payload ON jobs WHEN NEW.payload IS NULL BEGIN DELETE FROM action_requests WHERE job=NEW.id; END;
            CREATE INDEX IF NOT EXISTS native_jobs_ready ON jobs(kind,state,next_at);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level='IMMEDIATE')
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA secure_delete=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _seal(self, value: Any) -> bytes:
        return self.cipher.encrypt(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())

    def _open(self, value: bytes | None) -> Any:
        return json.loads(self.cipher.decrypt(value)) if value else None

    def enqueue(self, scope: AdapterScope, kind: str, dedupe: str, payload: dict, *,
                ttl: int=86400, max_attempts: int=8, now: float | None=None, actor: str='') -> str:
        if kind not in {'openhands','browser_use','langfuse','langfuse_delete'}: raise ValueError('Unknown native job kind')
        if not dedupe or len(dedupe)>256 or not 1<=ttl<=604800 or not 1<=max_attempts<=20: raise ValueError('Invalid queue bounds')
        stamp=time.time() if now is None else now
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>262144: raise ValueError('Oversized native payload')
        fingerprint=hashlib.sha256(raw).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO jobs(id,org,agent,run,kind,dedupe,fingerprint,payload,state,max_attempts,next_at,expires_at,created_at,actor) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (str(uuid4()),scope.org_id,scope.agent_id,scope.run_id,kind,dedupe,fingerprint,self._seal(payload),'queued',max_attempts,stamp,stamp+ttl,stamp,actor))
            row=db.execute('SELECT id,fingerprint,actor FROM jobs WHERE org=? AND agent=? AND run=? AND dedupe=?',
                (scope.org_id,scope.agent_id,scope.run_id,dedupe)).fetchone()
            if row['fingerprint']!=fingerprint or row['actor']!=actor: raise ValueError('Idempotency key reused with a different request')
            return row['id']

    def get(self, scope: AdapterScope, job_id: str, *, material: bool=False) -> dict | None:
        with self.connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=? AND org=? AND agent=? AND run=?',
                (job_id,scope.org_id,scope.agent_id,scope.run_id)).fetchone()
        if not row: return None
        value={k:row[k] for k in ('id','kind','state','phase','attempts','error_code','expires_at','actor')}
        if material: value.update(payload=self._open(row['payload']),result=self._open(row['result']))
        return value

    def claim(self, kind: str, *, lease_seconds: int=60, now: float | None=None) -> dict | None:
        if not 1<=lease_seconds<=600: raise ValueError('Invalid lease bound')
        stamp=time.time() if now is None else now
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Native execution is never blindly replayed after a lost worker. A
            # reconciler must remove the deterministic sandbox before retrying.
            db.execute("UPDATE jobs SET state='uncertain',error_code='worker_lease_lost',lease=NULL WHERE kind IN ('openhands','browser_use') AND state='running' AND lease_until<=?",(stamp,))
            db.execute("UPDATE jobs SET state='queued',lease=NULL WHERE kind IN ('langfuse','langfuse_delete') AND state='running' AND lease_until<=?",(stamp,))
            db.execute("UPDATE jobs SET state='expired',payload=NULL,result=NULL,lease=NULL WHERE kind IN ('openhands','browser_use') AND expires_at<=? AND state NOT IN ('deleted','expired')",(stamp,))
            db.execute("UPDATE jobs SET kind='langfuse_delete',state='queued',phase=CASE WHEN state='delivered' THEN 'delete_known' ELSE 'delete_unknown' END,next_at=?,expires_at=?,lease=NULL,attempts=0 WHERE kind='langfuse' AND expires_at<=? AND state!='deleted'",(stamp,stamp+604800,stamp))
            db.execute("UPDATE jobs SET state='failed',error_code='deletion_retention_expired',lease=NULL WHERE kind='langfuse_delete' AND expires_at<=? AND state IN ('queued','running')",(stamp,))
            row=db.execute("SELECT * FROM jobs WHERE kind=? AND state='queued' AND next_at<=? AND expires_at>? AND attempts<max_attempts ORDER BY created_at,id LIMIT 1",(kind,stamp,stamp)).fetchone()
            if not row:return None
            token=str(uuid4())
            db.execute("UPDATE jobs SET state='running',lease=?,lease_until=?,attempts=attempts+1 WHERE id=?",(token,stamp+lease_seconds,row['id']))
            return {'id':row['id'],'scope':AdapterScope(row['org'],row['agent'],row['run']),
                    'kind':row['kind'],'lease':token,'phase':row['phase'],'attempts':row['attempts']+1,
                    'created_at':row['created_at'],'expires_at':row['expires_at'],'payload':self._open(row['payload'])}

    def update(self, job: dict, state: str, *, phase: str | None=None, result: dict | None=None,
               error: str | None=None, retry_delay: float=0, now: float | None=None) -> None:
        if state not in TERMINAL|{'queued','running'}:raise ValueError('Invalid state')
        if error and (len(error)>64 or not all(c.islower() or c=='_' for c in error)):raise ValueError('Only sanitized error categories may be stored')
        stamp=time.time() if now is None else now
        with self.connect() as db:
            row=db.execute('SELECT attempts,max_attempts FROM jobs WHERE id=? AND lease=? AND state=? AND lease_until>?',
                (job['id'],job['lease'],'running',stamp)).fetchone()
            if not row:raise LeaseLost('Worker lease expired, cancelled or replaced')
            if state=='queued' and row['attempts']>=row['max_attempts']:state='failed'
            cursor=db.execute('UPDATE jobs SET state=?,phase=COALESCE(?,phase),result=COALESCE(?,result),error_code=?,next_at=?,lease=?,lease_until=? WHERE id=? AND lease=?',
                (state,phase,self._seal(result) if result is not None else None,error,stamp+retry_delay,
                 job['lease'] if state=='running' else None,stamp+60 if state=='running' else None,job['id'],job['lease']))
            if cursor.rowcount!=1:raise LeaseLost('Worker no longer owns this operation')

    def active(self, job: dict, *, now: float | None=None) -> bool:
        stamp=time.time() if now is None else now
        with self.connect() as db:
            row=db.execute("SELECT 1 FROM jobs WHERE id=? AND lease=? AND state='running' AND lease_until>? AND expires_at>?",
                (job['id'],job['lease'],stamp,stamp)).fetchone()
        return bool(row)

    def save_browser_checkpoint(self, job: dict, sequence: int, checkpoint: dict) -> None:
        """Persist a pre-effect checkpoint only while the browser lease is live."""
        if job.get('kind')!='browser_use' or type(sequence) is not int or not 0<=sequence<=100:
            raise ValueError('Invalid browser checkpoint')
        if not isinstance(checkpoint,dict) or len(json.dumps(checkpoint).encode())>32768:
            raise ValueError('Invalid checkpoint payload')
        stamp=time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            live=db.execute("SELECT 1 FROM jobs WHERE id=? AND lease=? AND state='running' AND lease_until>? AND expires_at>?",
                (job['id'],job['lease'],stamp,stamp)).fetchone()
            if not live:raise LeaseLost('Checkpoint worker lease no longer active')
            if db.execute("SELECT 1 FROM action_requests WHERE job=?",(job['id'],)).fetchone():
                raise PermissionError('Cannot checkpoint after an action has been requested')
            previous=db.execute("SELECT sequence FROM browser_checkpoints WHERE job=?",(job['id'],)).fetchone()
            if previous and sequence<=previous['sequence']:raise ValueError('Checkpoint sequence must increase')
            db.execute("INSERT INTO browser_checkpoints(job,lease,sequence,payload,created_at) VALUES(?,?,?,?,?) ON CONFLICT(job) DO UPDATE SET lease=excluded.lease,sequence=excluded.sequence,payload=excluded.payload,created_at=excluded.created_at",
                (job['id'],job['lease'],sequence,self._seal(checkpoint),stamp))

    def browser_checkpoint(self, scope: AdapterScope, job_id: str) -> dict | None:
        """Read scoped checkpoint metadata; never expose it to untrusted clients."""
        with self.connect() as db:
            row=db.execute("SELECT c.sequence,c.payload FROM browser_checkpoints c JOIN jobs j ON j.id=c.job WHERE j.id=? AND j.org=? AND j.agent=? AND j.run=?",
                (job_id,scope.org_id,scope.agent_id,scope.run_id)).fetchone()
        return {'sequence':row['sequence'],'checkpoint':self._open(row['payload'])} if row else None

    def fence_browser_for_fallback(self, job: dict, *, checkpoint_before_effect: bool) -> bool:
        """Atomically revoke the Browser Use lease and reserve reconciliation.

        This is a safety fence, NOT authorization to launch Playwright. A fresh
        checkpoint and independent effect reconciliation must precede handoff.
        """
        if job.get('kind') != 'browser_use' or type(checkpoint_before_effect) is not bool:
            raise ValueError('Browser Use lease and explicit checkpoint required')
        stamp=time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute(
                "SELECT state,lease,lease_until,expires_at FROM jobs WHERE id=? AND org=? AND agent=? AND run=?",
                (job['id'],job['scope'].org_id,job['scope'].agent_id,job['scope'].run_id)).fetchone()
            if not row or row['state']!='running' or row['lease']!=job['lease'] or row['lease_until']<=stamp or row['expires_at']<=stamp:
                raise LeaseLost('Cannot fence an inactive or stale browser worker')
            actions=db.execute("SELECT COUNT(*) FROM action_requests WHERE job=?",(job['id'],)).fetchone()[0]
            # Even an approved action can have committed externally; any action
            # history requires independent reconciliation, never blind replay.
            checkpoint=db.execute("SELECT 1 FROM browser_checkpoints WHERE job=? AND lease=?",(job['id'],job['lease'])).fetchone()
            safe=checkpoint_before_effect and actions==0 and checkpoint is not None
            phase='fallback_fenced' if safe else 'fallback_reconcile'
            changed=db.execute(
                "UPDATE jobs SET state='uncertain',phase=?,lease=NULL,lease_until=NULL,error_code='fallback_pending' WHERE id=? AND lease=? AND state='running'",
                (phase,job['id'],job['lease'])).rowcount
            if changed!=1:raise LeaseLost('Browser worker lost its execution authority')
            return safe

    def fallback_candidate(self, scope: AdapterScope, job_id: str) -> dict | None:
        """Return a fenced pre-effect candidate, never an executable job.

        This intentionally does not claim, enqueue or grant Playwright access.
        The recovery coordinator must independently verify the destination
        and current authorization before a new engine can be launched.
        """
        with self.connect() as db:
            row=db.execute("""
                SELECT j.state,j.phase,j.lease,j.expires_at,c.sequence,c.payload
                FROM jobs j JOIN browser_checkpoints c ON c.job=j.id
                WHERE j.id=? AND j.org=? AND j.agent=? AND j.run=?
                  AND j.kind='browser_use' AND j.state='uncertain'
                  AND j.phase='fallback_fenced' AND j.lease IS NULL
                  AND j.expires_at>?
                  AND NOT EXISTS (SELECT 1 FROM action_requests a WHERE a.job=j.id)
            """,(job_id,scope.org_id,scope.agent_id,scope.run_id,time.time())).fetchone()
        if not row:return None
        checkpoint=self._open(row['payload'])
        if checkpoint.get('before_effect') is not True:return None
        return {'sequence':row['sequence'],'checkpoint':checkpoint}

    def cancel(self, scope: AdapterScope, job_id: str) -> bool:
        with self.connect() as db:
            changed=db.execute("UPDATE jobs SET state='cancelled',lease=NULL,payload=NULL,result=NULL WHERE id=? AND org=? AND agent=? AND run=? AND kind IN ('openhands','browser_use') AND state IN ('queued','running','uncertain')",
                (job_id,scope.org_id,scope.agent_id,scope.run_id)).rowcount
        return changed==1

    def erase(self, scope: AdapterScope, job_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE jobs SET payload=NULL,result=NULL,state='deleted',lease=NULL,error_code=NULL WHERE id=? AND org=? AND agent=? AND run=?",
                (job_id,scope.org_id,scope.agent_id,scope.run_id))


    def consent(self, scope: AdapterScope, *, now: float | None=None) -> bool:
        with self.connect() as db:
            row=db.execute('SELECT enabled,expires_at FROM telemetry_consent WHERE org=? AND agent=? AND run=?',
                (scope.org_id,scope.agent_id,scope.run_id)).fetchone()
        return bool(row and row['enabled']==1 and row['expires_at']>(time.time() if now is None else now))

    def set_consent(self, scope: AdapterScope, enabled: bool, *, ttl: int=86400) -> None:
        if type(enabled) is not bool or not 1<=ttl<=604800:raise ValueError('Invalid consent bounds')
        with self.connect() as db:
            db.execute('INSERT INTO telemetry_consent VALUES(?,?,?,?,?) ON CONFLICT(org,agent,run) DO UPDATE SET enabled=excluded.enabled,expires_at=excluded.expires_at',
                (scope.org_id,scope.agent_id,scope.run_id,int(enabled),time.time()+ttl))
            if not enabled:
                db.execute("UPDATE jobs SET state='deleted',payload=NULL,result=NULL,lease=NULL WHERE org=? AND agent=? AND run=? AND kind='langfuse' AND state='queued' AND phase='submit'",(scope.org_id,scope.agent_id,scope.run_id))
                db.execute("UPDATE jobs SET kind='langfuse_delete',state='queued',phase=CASE WHEN state='delivered' THEN 'delete_known' ELSE 'delete_unknown' END,next_at=MAX(?,COALESCE(lease_until,0)+15),expires_at=?,lease=NULL,attempts=0 WHERE org=? AND agent=? AND run=? AND kind='langfuse' AND state!='deleted'",
                    (time.time(),time.time()+604800,scope.org_id,scope.agent_id,scope.run_id))

    def request_deletion(self, job: dict) -> None:
        with self.connect() as db:
            changed=db.execute("UPDATE jobs SET kind='langfuse_delete',state='queued',phase='delete_unknown',next_at=MAX(?,COALESCE(lease_until,0)+15),expires_at=?,lease=NULL,attempts=0 WHERE id=? AND lease=? AND state='running'",
                (time.time(),time.time()+604800,job['id'],job['lease'])).rowcount
        if changed!=1:raise LeaseLost('Deletion already scheduled or lease lost')


    def consume_authority(self, org: str, actor: str, reference: str, operation: str) -> None:
        key=hashlib.sha256(json.dumps([org,actor,reference],separators=(',',':')).encode()).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO authority_uses VALUES(?,?)',(key,operation))
            row=db.execute('SELECT operation FROM authority_uses WHERE key=?',(key,)).fetchone()
            if row['operation']!=operation:raise PermissionError('Approval cannot authorize another native operation')

    def request_action(self, job: dict, sequence: int, action: dict) -> dict:
        if type(sequence) is not int or not 0<=sequence<=100:raise ValueError('Invalid action sequence')
        raw=json.dumps(action,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(raw)>8192:raise ValueError('Oversized browser action')
        digest=hashlib.sha256(raw.encode()).hexdigest()
        with self.connect() as db:
            live=db.execute("SELECT 1 FROM jobs WHERE id=? AND lease=? AND state='running' AND lease_until>? AND expires_at>?",(job['id'],job['lease'],time.time(),time.time())).fetchone()
            if not live:raise LeaseLost('Cancelled native action')
            db.execute("INSERT OR IGNORE INTO action_requests VALUES(?,?,?,?,?,'pending')",(str(uuid4()),job['id'],sequence,digest,self._seal(action)))
            row=db.execute('SELECT id,digest,state FROM action_requests WHERE job=? AND sequence=?',(job['id'],sequence)).fetchone()
            if row['digest']!=digest:raise ValueError('Browser action changed after approval request')
            return {'id':row['id'],'digest':row['digest'],'state':row['state']}

    def actions(self, scope: AdapterScope, job_id: str) -> list[dict]:
        if not self.get(scope,job_id):return []
        with self.connect() as db:
            rows=db.execute('SELECT id,digest,payload,state,sequence FROM action_requests WHERE job=? ORDER BY sequence',(job_id,)).fetchall()
        return [{'id':r['id'],'digest':r['digest'],'action':self._open(r['payload']),'state':r['state']} for r in rows]

    def approve(self, scope: AdapterScope, job_id: str, request_id: str, digest: str, approved: bool) -> None:
        if type(approved) is not bool:raise ValueError('Explicit boolean decision required')
        with self.connect() as db:
            changed=db.execute("UPDATE action_requests SET state=? WHERE id=? AND job=? AND digest=? AND state='pending' AND EXISTS(SELECT 1 FROM jobs WHERE id=? AND org=? AND agent=? AND run=? AND state='running' AND expires_at>?)",('approved' if approved else 'denied',request_id,job_id,digest,job_id,scope.org_id,scope.agent_id,scope.run_id,time.time())).rowcount
        if changed!=1:raise PermissionError('Approval is stale, changed or outside tenant scope')
        if not approved:self.cancel(scope,job_id)


    def owners(self, scope: AdapterScope) -> set[str]:
        with self.connect() as db:
            rows=db.execute('SELECT DISTINCT actor FROM jobs WHERE org=? AND agent=? AND run=?',(scope.org_id,scope.agent_id,scope.run_id)).fetchall()
        return {r['actor'] for r in rows}

    def uncertain_jobs(self) -> list[str]:
        with self.connect() as db:
            return [r['id'] for r in db.execute("SELECT id FROM jobs WHERE kind IN ('openhands','browser_use') AND state IN ('uncertain','cancelled','expired','failed') AND phase!='reconciled'").fetchall()]


    def reconciled(self, id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE jobs SET phase='reconciled' WHERE id=? AND state IN ('uncertain','cancelled','expired','failed')",(id,))
