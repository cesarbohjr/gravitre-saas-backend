"""Matched real-audio native assignment staging/cancel/approve/replay.

Acceptance DB only. No execution worker is launched. Created assignment rows
are retired after durable readback; job outcome/learning remains NOT RUN.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import traceback
import uuid

from voice_paired_live import (TARGET, Capture, SanitizedDiagnostics, guard, livekit_trial,
    websocket_trial, verified_fixture, wav)


async def main():
    guard(os.environ)
    from app.config import get_settings
    from app.core.db import get_supabase_client
    from app.services.conversation_state_service import get_conversation_state_service
    from supabase import create_client
    settings = get_settings()
    if settings.supabase_url.rstrip('/') != TARGET:
        raise ValueError('acceptance target mismatch')
    from urllib.parse import urlparse
    if urlparse(str(settings.redis_url or '')).hostname not in (None, 'localhost', '127.0.0.1', 'redis'):
        raise ValueError('external execution queue forbidden')
    writer = get_supabase_client(settings)
    reader = create_client(TARGET, settings.supabase_service_role_key)
    org, actor = (os.environ[k] for k in ('ISOLATED_CONVERSATION_TEST_ORG_ID', 'ISOLATED_CONVERSATION_TEST_USER_ID'))
    if org != 'f07e57c0-1501-4000-8000-c04e57a00001':
        raise ValueError('isolated org mismatch')
    if str(reader.auth.get_user(os.environ['PLATFORM_LIVE_BEARER_TOKEN']).user.id) != actor:
        raise ValueError('actor mismatch')
    members = reader.table('organization_members').select('user_id').eq('org_id', org).eq('user_id', actor).execute().data
    flags = reader.table('organizations').select('settings').eq('id', org).single().execute().data['settings']
    if not members or any(flags.get(k) is not True for k in ('never_customer_visible', 'isolated_conversation_test_org')):
        raise ValueError('acceptance membership missing')
    started = datetime.now(timezone.utc).isoformat()
    trace = 'acceptance orchard violet harbor marigold amber'
    phrases = {'stage': ('Create an internal Gravitre assignment to draft a two sentence welcome note for Alex. '
        'Use the reference ' + trace + '. Do not contact anyone. Ask for my confirmation before creating it.'),
        'cancel': 'Cancel.', 'approve': 'Yes.'}
    output = Path(os.environ.get('ACCEPTANCE_NATIVE_ARTIFACT_DIR', 'acceptance-results/paired-native-assignment'))
    output.mkdir(parents=True, exist_ok=True)
    logging.getLogger().addHandler(SanitizedDiagnostics(output / 'pipeline-failures.json'))
    report = {'git_sha': os.environ.get('ACCEPTANCE_SOURCE_SHA'), 'trace': trace,
        'scope': 'real transports and native product action; no worker execution',
        'certified': False, 'outcome_learning': 'NOT RUN', 'trials': [], 'recordings': {},
        'input_origin': 'run 41141376937 artifact 13019106451; exact PCM reused'}
    manifest = output / 'manifest.json'
    pcm = {}
    fixture_root = Path(os.environ['ACCEPTANCE_NATIVE_RECORDINGS_DIR'])
    digests = {'stage': 'c0dc49c1c7cc00a291f140697629efeab9860ae9eed166536a9f2749499e7853',
        'cancel': '6879be0f25bf1d150c0e3dddd06d0b5298462dde65b75942b2b05da4001eff9f',
        'approve': '91e37080c6122a0e5df30858e72bffcbeb34e4a4415597771f7fa78382bb2133'}
    for name, text in phrases.items():
        pcm[name] = verified_fixture(fixture_root / (name + '.wav'), digests[name])
        wav(output / (name + '.wav'), pcm[name], 16000)
        report['recordings'][name] = {'pcm_sha256': hashlib.sha256(pcm[name]).hexdigest(), 'source_text': text}
    state_service = get_conversation_state_service(settings)

    def jobs(cid):
        rows = reader.table('agent_jobs').select('id,status,payload').eq('org_id', org).eq('created_by', actor).contains('payload', {'context': {'conversation_id': cid}}).gte('created_at', started).limit(1000).execute().data
        if len(rows) >= 1000:
            raise AssertionError('job read truncated')
        return {str(r['id']): r for r in rows}

    async def speak(engine, trial, cid, phrase, label):
        capture = Capture()
        # Require authoritative completed turn, rather than a filler ACK.
        capture.scenario = 'baseline'
        try:
            await trial(settings, org, actor, cid, pcm[phrase], capture)
        finally:
            wav(output / (engine + '-' + label + '.wav'), capture.pcm, 24000)
            (output / (engine + '-' + label + '-timing.json')).write_text(json.dumps({
                'events': capture.event_timeline, 'stages': capture.interruption_timeline,
                'errors': capture.errors}, indent=2))
        if capture.errors or capture.first is None:
            raise AssertionError('voice pipeline failed')
        return await state_service.get_task_state(cid, org, client=reader, strict=True)

    try:
        for engine, trial in (('pipecat', websocket_trial), ('livekit', livekit_trial)):
            for decision in ('cancel', 'approve'):
                row = {'engine': engine, 'scenario': decision, 'status': 'FAIL'}
                report['trials'].append(row)
                cid = str(uuid.uuid4())
                row['conversation_id'] = cid
                writer.table('conversations').insert({'id': cid, 'org_id': org, 'user_id': actor,
                    'title': 'Internal native voice acceptance'}).execute()
                before = jobs(cid)
                try:
                    state = await speak(engine, trial, cid, 'stage', decision + '-stage')
                    pending = state.get('pending_task') or {}
                    row['staged_pending_type'] = pending.get('type')
                    row['staged_pending_status'] = pending.get('status')
                    if pending.get('type') != 'create_assignment' or pending.get('status') != 'awaiting_confirm':
                        raise AssertionError('assignment not durably awaiting approval')
                    if set(jobs(cid)) != set(before):
                        raise AssertionError('assignment created before approval')
                    row['staged_without_write'] = True
                    state = await speak(engine, trial, cid, decision, decision)
                    after = jobs(cid)
                    created = set(after) - set(before)
                    row['new_job_ids'] = sorted(created)
                    if decision == 'cancel':
                        if created or state.get('pending_task'):
                            raise AssertionError('cancel did not clear staged assignment without writes')
                        row['cancelled_effects'] = 0
                    else:
                        pending = state.get('pending_task') or {}
                        row['approved_pending_status'] = pending.get('status')
                        entity = str((pending.get('result') or {}).get('entity_id') or '')
                        if len(created) != 1 or entity not in created or pending.get('status') != 'executed':
                            raise AssertionError('approval did not create exactly one durable assignment')
                        row['approved_effects'] = 1
                        if (after[entity].get('payload') or {}).get('context', {}).get('source') != 'approved_chat_assignment':
                            raise AssertionError('unexpected assignment provenance')
                        audit = reader.table('audit_events').select('id,action,resource_id').eq('org_id', org).eq('resource_id', entity).eq('action', 'assignment.created').execute().data
                        if not audit:
                            raise AssertionError('independent assignment creation audit missing')
                        row['independent_write_audit_ids'] = [r['id'] for r in audit]
                        await speak(engine, trial, cid, 'approve', 'approval-replay')
                        if set(jobs(cid)) != set(after):
                            raise AssertionError('approval replay created another assignment')
                        row['duplicate_effects'] = 0
                    row['status'] = 'PASS'
                except Exception as error:
                    row['error_type'] = type(error).__name__
                finally:
                    # Only IDs independently observed as new in this isolated
                    # actor's bounded trial. No execution worker is launched.
                    for job_id in set(jobs(cid)) - set(before):
                        writer.table('agent_jobs').update({'status': 'cancelled',
                            'error': 'synthetic voice acceptance retired; worker not executed'}).eq('org_id', org).eq('id', job_id).execute()
                    manifest.write_text(json.dumps(report, indent=2))
    finally:
        manifest.write_text(json.dumps(report, indent=2))
    if len(report['trials']) != 4 or any(r['status'] != 'PASS' for r in report['trials']):
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as error:
        path = Path(os.environ.get('ACCEPTANCE_NATIVE_ARTIFACT_DIR', 'acceptance-results/paired-native-assignment')) / 'startup-failure.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__,
            'http_status': getattr(error, 'upstream_status', None),
            'frames': [{'file': Path(f.filename).name, 'line': f.lineno, 'function': f.name}
                for f in traceback.extract_tb(error.__traceback__)[-20:]]}, indent=2))
        raise SystemExit(1)
