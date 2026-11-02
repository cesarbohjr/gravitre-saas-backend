"""Live acceptance-only repository cancellation race, not approval certification.

No worker is started or enqueued. The positive row is retired immediately.
An independent client reads back the unique trace after both threads finish.
"""
import asyncio
import json
import os
from pathlib import Path
import threading
import uuid

from voice_paired_live import TARGET, guard


async def main():
    guard(os.environ)
    from app.config import get_settings
    from app.core.db import get_supabase_client
    from app.operators.agent_jobs import create_job
    from app.services.tool_types import ToolValidationError
    from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
    from supabase import create_client

    settings = get_settings()
    if settings.supabase_url.rstrip('/') != TARGET:
        raise ValueError('acceptance settings mismatch')
    writer = get_supabase_client(settings)
    reader = create_client(TARGET, settings.supabase_service_role_key)
    org = os.environ['ISOLATED_CONVERSATION_TEST_ORG_ID']
    actor = os.environ['ISOLATED_CONVERSATION_TEST_USER_ID']
    if org != 'f07e57c0-1501-4000-8000-c04e57a00001':
        raise ValueError('smoke org mismatch')
    if str(reader.auth.get_user(os.environ['PLATFORM_LIVE_BEARER_TOKEN']).user.id) != actor:
        raise ValueError('actor mismatch')
    membership = reader.table('organization_members').select('user_id').eq('org_id', org).eq('user_id', actor).execute().data
    flags = reader.table('organizations').select('settings').eq('id', org).single().execute().data['settings']
    if not membership or any(flags.get(k) is not True for k in ('never_customer_visible', 'isolated_conversation_test_org')):
        raise ValueError('acceptance scope missing')
    trace = 'native-cancel-' + uuid.uuid4().hex
    report = {'trace': trace, 'git_sha': os.environ.get('ACCEPTANCE_SOURCE_SHA'),
        'scope': 'native agent_jobs insert boundary, no approval or worker execution',
        'certified': False, 'status': 'FAIL'}
    out = Path('acceptance-results/native-assignment-cancellation.json')
    out.parent.mkdir(parents=True, exist_ok=True)

    def insert(case):
        # No created_by: this repository probe deliberately avoids notification
        # fanout. The authenticated actor is recorded in the synthetic payload.
        return create_job(writer, org, environment='acceptance', max_attempts=1,
            payload={'acceptance_trace': trace, 'case': case, 'acceptance_actor': actor,
                'task': 'Synthetic cancellation acceptance sentinel. Do not execute.'})

    try:
        with bound_turn_cancellation(TurnCancellation()):
            positive = await asyncio.to_thread(insert, 'positive')
        writer.table('agent_jobs').update({'status': 'cancelled', 'error': 'acceptance sentinel retired; never queued for execution'}).eq('org_id', org).eq('id', positive['id']).execute()
        report['positive_job_id'] = positive['id']
        started, release = threading.Event(), threading.Event()
        token = TurnCancellation()

        def late_worker():
            with bound_turn_cancellation(token):
                started.set()
                if not release.wait(5):
                    raise TimeoutError('worker release')
                try:
                    insert('cancelled')
                except ToolValidationError as error:
                    return error.code
                return 'WRITE_WAS_NOT_BLOCKED'

        task = asyncio.create_task(asyncio.to_thread(late_worker))
        try:
            while not started.is_set():
                if task.done():
                    await task
                await asyncio.sleep(.005)
            token.cancel('acceptance_cancel')
            # Simulate a new turn without releasing the old worker's authority.
            with bound_turn_cancellation(TurnCancellation()):
                release.set()
                report['cancelled_worker_result'] = await asyncio.wait_for(task, 10)
        finally:
            release.set()
        rows = reader.table('agent_jobs').select('id,status,payload').eq('org_id', org).contains('payload', {'acceptance_trace': trace}).execute().data
        report['independent_rows'] = [{'id': r['id'], 'status': r['status'], 'case': r['payload']['case']} for r in rows]
        report['cancelled_effects'] = sum(r['payload']['case'] == 'cancelled' for r in rows)
        report['positive_effects'] = sum(r['payload']['case'] == 'positive' for r in rows)
        if (report['cancelled_worker_result'] != 'write_commit_interrupted' or
                report['cancelled_effects'] != 0 or report['positive_effects'] != 1 or
                any(r['status'] != 'cancelled' for r in rows)):
            raise AssertionError('native durable write race failed')
        report['status'] = 'PASS'
    except Exception as error:
        report['error_type'] = type(error).__name__
        raise
    finally:
        # Even a failing regression must leave no queued acceptance sentinel.
        try:
            writer.table('agent_jobs').update({'status': 'cancelled'}).eq('org_id', org).contains('payload', {'acceptance_trace': trace}).execute()
        finally:
            out.write_text(json.dumps(report, indent=2))
            print(json.dumps(report))


if __name__ == '__main__':
    asyncio.run(main())
