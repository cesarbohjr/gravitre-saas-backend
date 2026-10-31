"""The real battery's first protected request carries a valid smoke JWT."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import jwt


class InjectionSmokeAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_uuid_subject_issuer_and_short_lifetime_on_actual_request(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/verify-unified-turn-prompt-injection-live.py'
        spec = importlib.util.spec_from_file_location('injection_battery', path)
        battery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(battery)
        target = 'https://aadnwmjzrmbvadszroqt.supabase.co'
        actor = 'e8e63c9b-8b3e-4245-9356-103e2dc9988a'
        secret = 'offline-signing-secret-that-is-at-least-thirty-two-bytes'

        class RequestObserved(Exception):
            pass

        class Client:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, *args, **kwargs):
                return SimpleNamespace(json=lambda: {'git_sha': 'offline'})
            async def post(client_self, url, *, headers, **kwargs):
                token = headers['Authorization'].removeprefix('Bearer ')
                claims = jwt.decode(token, secret, algorithms=['HS256'],
                    audience='authenticated', issuer=target + '/auth/v1',
                    options={'require': ['sub', 'iss', 'iat', 'exp', 'aud']})
                self.assertEqual(claims['sub'], actor)
                self.assertEqual(claims['email'], 'conversation-smoke-sa@gravitre.app')
                self.assertEqual(claims['exp'] - claims['iat'], 600)
                raise RequestObserved()

        with ExitStack() as stack:
            # No outbound provider/Auth/DB access, including accidental calls.
            for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.getaddrinfo'):
                stack.enter_context(patch(name, side_effect=AssertionError('outbound network forbidden')))
            stack.enter_context(patch.object(battery, 'load_env', return_value=dict(
                SUPABASE_URL=target, SUPABASE_SERVICE_ROLE_KEY='unused', SUPABASE_JWT_SECRET=secret)))
            stack.enter_context(patch.object(battery, 'create_client', return_value=object()))
            stack.enter_context(patch.object(battery, 'resolve_isolated_conversation_actor',
                return_value=('f07e57c0-1501-4000-8000-c04e57a00001', actor, 'conversation-smoke-sa@gravitre.app')))
            stack.enter_context(patch.object(battery, 'EXPECT_SHA', ''))
            stack.enter_context(patch.object(battery.httpx, 'AsyncClient', Client))
            with self.assertRaises(RequestObserved):
                await battery.main()


if __name__ == '__main__':
    unittest.main()
