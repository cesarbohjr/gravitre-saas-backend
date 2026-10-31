"""Actual production ASGI route + live acceptance Auth/membership negatives.

Uses a disposable Auth actor for revocation; never changes the shared actor.
No voice input, business actions, external messaging or application worker.
"""
import json
import os
from pathlib import Path
import secrets
import time
import uuid

from voice_paired_live import TARGET, guard


def main():
    guard(os.environ)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    import jwt
    from supabase import create_client
    from app.config import get_settings
    from app.auth.jwt_verify import decode_supabase_jwt
    from app.routers.pipecat_voice import router
    from app.services.org_membership import list_member_org_ids
    settings = get_settings()
    if settings.supabase_url.rstrip('/') != TARGET or not settings.voice_pipecat_enabled:
        raise ValueError('isolated route configuration missing')
    client = create_client(TARGET, settings.supabase_service_role_key)
    org = os.environ['ISOLATED_CONVERSATION_TEST_ORG_ID']
    shared_actor = os.environ['ISOLATED_CONVERSATION_TEST_USER_ID']
    token = os.environ['PLATFORM_LIVE_BEARER_TOKEN']
    if org != 'f07e57c0-1501-4000-8000-c04e57a00001':
        raise ValueError('isolated org mismatch')
    claims = decode_supabase_jwt(token, settings)
    if str(claims['sub']) != shared_actor or str(client.auth.get_user(token).user.id) != shared_actor:
        raise ValueError('shared actor identity mismatch')
    flags = client.table('organizations').select('settings').eq('id', org).single().execute().data['settings']
    if any(flags.get(k) is not True for k in ('never_customer_visible', 'isolated_conversation_test_org')):
        raise ValueError('isolated org flags missing')
    app = FastAPI()
    app.include_router(router)
    result = {'git_sha': os.environ.get('ACCEPTANCE_SOURCE_SHA'), 'status': 'FAIL',
        'scope': 'production Pipecat ASGI route, live Auth and membership; not RTC token issuance or in-flight tool reauthorization',
        'certified': False, 'cases': []}
    output = Path('acceptance-results/voice-route-authorization.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    disposable = None

    def denied(browser, name, value, target, expected, membership_error=False):
        headers = {'authorization': 'Bearer ' + value} if value else {}
        with browser.websocket_connect('/api/voice/pipecat/ws?org_id=' + target, headers=headers) as socket:
            message = socket.receive_json()
            if message.get('type') != 'error' or message.get('error_class') != expected:
                raise AssertionError('route did not refuse expected boundary')
            if membership_error and message.get('error') != 'Not a member of the requested organization':
                raise AssertionError('membership refusal was not authoritative')
            try:
                socket.receive_json()
            except WebSocketDisconnect as closed:
                if closed.code != 1008:
                    raise AssertionError('incorrect policy close code')
            else:
                raise AssertionError('refused route stayed open')
        result['cases'].append({'case': name, 'status': 'PASS', 'error_class': expected, 'close_code': 1008})

    try:
        with TestClient(app) as browser:
            denied(browser, 'missing_token', '', org, 'auth')
            head, payload, signature = token.split('.')
            tampered = head + '.' + payload + '.' + ('A' if signature[0] != 'A' else 'B') + signature[1:]
            denied(browser, 'tampered_token', tampered, org, 'auth')
            old = {**claims, 'iat': int(time.time()) - 240, 'nbf': int(time.time()) - 240, 'exp': int(time.time()) - 120}
            expired = jwt.encode(old, settings.supabase_jwt_secret, algorithm='HS256')
            denied(browser, 'expired_token', expired, org, 'auth')
            foreign = '42ef9d33-05fb-47f5-89a6-bc310fe5482d'
            if foreign in list_member_org_ids(client, shared_actor):
                raise AssertionError('foreign-org fixture is not foreign')
            denied(browser, 'foreign_org', token, foreign, 'forbidden', True)

            fixture_email = 'smoke+voice-revoke-' + uuid.uuid4().hex + '@gravitre.app'
            user = client.auth.admin.create_user({'email': fixture_email,
                'password': secrets.token_urlsafe(40), 'email_confirm': True}).user
            disposable = str(user.id)
            client.table('organization_members').insert({'org_id': org, 'user_id': disposable, 'role': 'member'}).execute()
            temporary_claims = {**claims, 'sub': disposable, 'email': fixture_email, 'iat': int(time.time()),
                'nbf': int(time.time()) - 1, 'exp': int(time.time()) + 300}
            temporary_token = jwt.encode(temporary_claims, settings.supabase_jwt_secret, algorithm='HS256')
            if str(client.auth.get_user(temporary_token).user.id) != disposable:
                raise AssertionError('disposable token did not authenticate')
            if org not in list_member_org_ids(client, disposable):
                raise AssertionError('disposable membership was not provisioned')
            client.table('organization_members').delete().eq('org_id', org).eq('user_id', disposable).execute()
            if org in list_member_org_ids(client, disposable):
                raise AssertionError('membership revocation not durable')
            denied(browser, 'revoked_membership_with_valid_token', temporary_token, org, 'forbidden', True)
        result['status'] = 'PASS'
    except Exception as error:
        result['error_type'] = type(error).__name__
        raise
    finally:
        try:
            if disposable:
                client.auth.admin.delete_user(disposable)
                result['disposable_actor_removed'] = True
        except Exception as error:
            result.update(status='FAIL', cleanup_error_type=type(error).__name__)
            raise
        finally:
            output.write_text(json.dumps(result, indent=2))
            print(json.dumps(result))


if __name__ == '__main__':
    main()
