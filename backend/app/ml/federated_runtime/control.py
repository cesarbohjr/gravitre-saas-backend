"""mTLS-only control plane for the optional Flower deployment.

The executable entrypoint requires mutual TLS. Run state and privacy reservations
are durable; a crash is not permission to redispatch a consumed round.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from app.ml.federated_learning import verified_privacy_profile
from app.ml.federated_runtime.privacy import runtime_settings, current_permission, data_root, feature_schema_digest

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_tasks: set[asyncio.Task] = set()


def database():
    db = sqlite3.connect(data_root()/"control.sqlite", timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS programs (program TEXT PRIMARY KEY, audit TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS rounds (round TEXT PRIMARY KEY, program TEXT, ordinal INTEGER, fingerprint TEXT, state TEXT, run_id TEXT, UNIQUE(program,ordinal))')
    if 'run_id' not in {row[1] for row in db.execute('PRAGMA table_info(rounds)')}:
        db.execute('ALTER TABLE rounds ADD COLUMN run_id TEXT')
    return db


class SealedParameters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = Field(alias='schema',ge=1,le=1)
    encrypted_key: str = Field(min_length=512,max_length=2048)
    nonce: str = Field(min_length=16,max_length=16)
    ciphertext: str = Field(min_length=24,max_length=2048)


class RoundRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    round_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    program_id: str = Field(min_length=1, max_length=512)
    audit_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    participants: list[UUID] = Field(min_length=100, max_length=100)
    feature_schema_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    sealed_contributions: dict[str,SealedParameters] = Field(min_length=100,max_length=100)


def runtime_profile():
    if os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('BLOB_READ_WRITE_TOKEN'):
        raise ValueError('Aggregation runtime must not hold source database or artifact master keys')
    settings = runtime_settings()
    from urllib.parse import urlparse
    parsed = urlparse(settings.federated_consent_service_url)
    if parsed.scheme != 'https' or not parsed.hostname or len(settings.federated_consent_service_secret) < 32:
        raise ValueError('Consent-only source service is not configured')
    from flwr.cli.flower_config import read_superlink_connection
    connection = read_superlink_connection('production')
    if connection.insecure or not connection.address:
        raise ValueError('Authenticated TLS SuperLink production connection required')
    profile, digest = verified_privacy_profile(settings)
    actual = os.environ.get('FEDERATED_DEPLOYMENT_SHA256', '')
    if actual != profile['deployment_sha256'] or feature_schema_digest() != profile['feature_schema_sha256']:
        raise ValueError('Runtime deployment/feature identity differs from independent audit')
    encoded = Path(os.environ['FEDERATED_NODE_REGISTRY_FILE']).read_bytes()
    if hashlib.sha256(encoded).hexdigest() != profile.get('node_registry_sha256'):
        raise ValueError('Enrolled-node registry differs from independent audit')
    return profile, digest


@app.get('/v1/attestation')
async def attestation():
    try:
        profile, digest = runtime_profile()
        with database() as db:
            pending = db.execute("SELECT round FROM rounds WHERE program=? AND state IN ('accepted','running','uncertain') AND run_id IS NOT NULL",(profile['program_id'],)).fetchall()
        for (pending_round,) in pending:
            await get_round(pending_round)
        with database() as db:
            record = db.execute('SELECT audit FROM programs WHERE program=?',(profile['program_id'],)).fetchone()
            if record and record[0] != digest:
                raise ValueError('An existing privacy program cannot reset its audit or expenditure')
            reserved = db.execute('SELECT count(*) FROM rounds WHERE program=?',(profile['program_id'],)).fetchone()[0]
            running = db.execute("SELECT count(*) FROM rounds WHERE program=? AND state IN ('accepted','running','uncertain')",(profile['program_id'],)).fetchone()[0]
            completed = [row[0] for row in db.execute("SELECT round FROM rounds WHERE program=? AND state='completed' ORDER BY ordinal",(profile['program_id'],))]
        return {'deployment_sha256':profile['deployment_sha256'], 'audit_digest':digest,
                'reserved_rounds':reserved, 'in_progress':bool(running), 'completed_rounds':completed}
    except Exception as exc:
        raise HTTPException(503, 'Audited privacy runtime unavailable: '+type(exc).__name__) from None


async def flower_json(*arguments):
    process = await asyncio.create_subprocess_exec('flwr',*arguments,'--format','json',
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    try:
        output,_ = await asyncio.wait_for(process.communicate(),timeout=60)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise ValueError('Flower control request outcome unconfirmed')
    if process.returncode != 0 or len(output) > 1_000_000:
        raise ValueError('Flower control request did not confirm a result')
    return json.loads(output)


async def run_round(round_id: str):
    with database() as db:
        db.execute("UPDATE rounds SET state='running' WHERE round=?",(round_id,))
    state = 'uncertain'
    try:
        # Official Flower 1.41 named SuperLink connection, not an invented
        # federation id. No raw training logs are copied into the control plane.
        started = await flower_json('run','/app/federated-runtime','production','--run-config',f'round-id="{round_id}"')
        run_id = started.get('run-id')
        if not started.get('success') or not isinstance(run_id,(str,int)) or not str(run_id).isdecimal():
            raise ValueError('Flower did not confirm a run identity')
        run_id = str(run_id)
        with database() as db:
            db.execute('UPDATE rounds SET run_id=? WHERE round=?',(run_id,round_id))
        for _ in range(120):
            record = await flower_json('ls','production','--run-id',run_id)
            rows = record.get('runs',[])
            row = next((item for item in rows if str(item.get('run-id')) == run_id),None)
            if row is None:
                raise ValueError('Flower source readback did not include the dispatched run')
            status = row.get('status','')
            if status == 'finished:completed':
                candidate = data_root()/f'candidate-{round_id}.json'
                if not candidate.is_file():
                    raise ValueError('Completed Flower run has no aggregate candidate')
                state = 'completed'
                break
            if status in {'finished:failed','finished:stopped'}:
                state = 'failed'  # Confirmed source state; privacy remains spent.
                break
            await asyncio.sleep(15)
    except Exception:
        pass  # Unknown dispatch/completion remains blocked pending readback.
    with database() as db:
        db.execute('UPDATE rounds SET state=? WHERE round=?',(state,round_id))


@app.post('/v1/rounds')
async def create_round(request: RoundRequest):
    try:
        profile, digest = runtime_profile()
        participants = sorted({str(value) for value in request.participants})
        if (len(participants) != 100 or set(request.sealed_contributions) != set(participants) or request.audit_digest != digest or request.program_id != profile['program_id']
                or request.feature_schema_sha256 != profile['feature_schema_sha256']):
            raise ValueError('Requested cohort/program differs from audited profile')
        settings = runtime_settings()
        for org_id in participants:
            await asyncio.to_thread(current_permission, org_id, settings, digest)
        content = {**request.model_dump(mode='json',by_alias=True), 'participants':participants}
        fingerprint = hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT fingerprint,state FROM rounds WHERE round=?',(request.round_id,)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError('Round identity cannot be reused with different participants or program')
                return {'round_id':request.round_id,'state':existing[1]}
            program = db.execute('SELECT audit FROM programs WHERE program=?',(request.program_id,)).fetchone()
            if program and program[0] != digest:
                raise ValueError('Existing privacy program cannot reset its audit')
            count = db.execute('SELECT count(*) FROM rounds WHERE program=?',(request.program_id,)).fetchone()[0]
            if count >= profile['max_rounds']:
                raise ValueError('Privacy round budget exhausted')
            if db.execute("SELECT count(*) FROM rounds WHERE program=? AND state IN ('accepted','running','uncertain')",(request.program_id,)).fetchone()[0]:
                raise ValueError('A privacy round is already running; reconcile before dispatch')
            expected_id = hashlib.sha256(f'{digest}:{count+1}'.encode()).hexdigest()
            if request.round_id != expected_id:
                raise ValueError('Nonsequential privacy reservation refused')
            destination = data_root()/f'round-{request.round_id}.json'
            with destination.open('x') as output:
                json.dump(content,output)
            os.chmod(destination,0o600)
            db.execute('INSERT OR IGNORE INTO programs VALUES (?,?)',(request.program_id,digest))
            db.execute('INSERT INTO rounds(round,program,ordinal,fingerprint,state) VALUES (?,?,?,?,?)',(request.round_id,request.program_id,count+1,fingerprint,'accepted'))
        task = asyncio.create_task(run_round(request.round_id))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        return {'round_id':request.round_id,'state':'accepted'}
    except Exception as exc:
        raise HTTPException(409, 'Federation round refused: '+type(exc).__name__) from None


@app.get('/v1/rounds/{round_id}')
async def get_round(round_id: str):
    runtime_profile()
    with database() as db:
        row = db.execute('SELECT state,run_id FROM rounds WHERE round=?',(round_id,)).fetchone()
    if not row:
        raise HTTPException(404,'Round not found')
    state,run_id = row
    # After a controller restart only source readback may unblock a reservation.
    # Missing dispatch identity is deliberately never permission to redispatch.
    if state in {'accepted','running','uncertain'} and run_id:
        try:
            result = await flower_json('ls','production','--run-id',run_id)
            source = next((item for item in result.get('runs',[]) if str(item.get('run-id')) == run_id),None)
            status = source.get('status') if source else None
            if status == 'finished:completed' and (data_root()/f'candidate-{round_id}.json').is_file():
                state = 'completed'
            elif status in {'finished:failed','finished:stopped'}:
                state = 'failed'
            else:
                state = 'uncertain'
            with database() as db:
                db.execute('UPDATE rounds SET state=? WHERE round=?',(state,round_id))
        except Exception:
            state = 'uncertain'
    return {'round_id':round_id,'state':state, 'candidate_available':state=='completed', 'model_promoted':False}


@app.get('/v1/rounds/{round_id}/candidate/{tenant_id}')
async def read_candidate(round_id: str, tenant_id: UUID):
    """Private aggregate only; caller identity is the source API's mTLS cert."""
    import re
    import math
    from app.core.safe_dict import safe_normalize_stored_dict
    if not re.fullmatch(r'[a-f0-9]{64}',round_id):
        raise HTTPException(404,'Round not found')
    profile,digest = runtime_profile()
    state = await get_round(round_id)
    if state['state'] != 'completed':
        raise HTTPException(409,'Round is not confirmed complete')
    request_path = data_root()/f'round-{round_id}.json'
    if not request_path.is_file() or request_path.stat().st_size > 1_000_000:
        raise HTTPException(409,'Bounded source round required')
    request = safe_normalize_stored_dict(request_path.read_text())
    if (not isinstance(request.get('participants'),list) or len(set(request['participants'])) != 100
            or str(tenant_id) not in request['participants'] or request['audit_digest'] != digest
            or request['program_id'] != profile['program_id']):
        raise HTTPException(403,'Current cohort membership required')
    await asyncio.to_thread(current_permission,str(tenant_id),runtime_settings(),digest)
    candidate = data_root()/f'candidate-{round_id}.json'
    if not candidate.is_file() or candidate.stat().st_size > 8192:
        raise HTTPException(409,'Bounded aggregate candidate required')
    artifact = safe_normalize_stored_dict(candidate.read_text())
    values = artifact.get('parameters')
    if (artifact.get('schema') != 1 or artifact.get('audit_digest') != digest
            or artifact.get('round_id') != round_id or artifact.get('feature_schema_sha256') != profile['feature_schema_sha256']
            or not isinstance(values,list) or len(values) != 5
            or any(type(value) not in {int,float} or not math.isfinite(value) for value in values)):
        raise HTTPException(409,'Aggregate candidate integrity failed')
    return artifact
