import importlib.util
from pathlib import Path
import unittest
import asyncio
import time

spec = importlib.util.spec_from_file_location('paired', Path(__file__).resolve().parents[1] / 'scripts/voice_paired_live.py')
paired = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paired)


class IsolationTests(unittest.TestCase):
    def env(self):
        return dict(GRAVITRE_VOICE_ISOLATED='1', SUPABASE_URL=paired.TARGET,
            E2E_SUPABASE_ALLOWED_URL=paired.TARGET, ANTHROPIC_API_KEY='offline',
            DEEPGRAM_API_KEY='offline', ELEVENLABS_API_KEY='offline',
            SUPABASE_SERVICE_ROLE_KEY='offline', PLATFORM_LIVE_BEARER_TOKEN='offline',
            ISOLATED_CONVERSATION_TEST_ORG_ID='org', ISOLATED_CONVERSATION_TEST_USER_ID='actor')

    def test_production_target_refused_before_any_client(self):
        env = self.env()
        env['SUPABASE_URL'] = 'https://production.supabase.co'
        with self.assertRaises(ValueError): paired.guard(env)

    def test_allowlist_must_match(self):
        env = self.env()
        env.pop('E2E_SUPABASE_ALLOWED_URL')
        with self.assertRaises(ValueError): paired.guard(env)

    def test_explicit_isolation_required(self):
        env = self.env()
        env['GRAVITRE_VOICE_ISOLATED'] = '0'
        with self.assertRaises(ValueError): paired.guard(env)

    def test_exact_acceptance_config(self):
        paired.guard(self.env())

    def test_silence_is_not_first_speech(self):
        capture = paired.Capture()
        capture.started = 1
        capture.audio(bytes(960))
        self.assertIsNone(capture.first)


class CompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_filler_silence_without_completion_does_not_finish(self):
        capture = paired.Capture()
        capture.first = time.monotonic() - 10
        capture.last = capture.first
        running = asyncio.create_task(asyncio.Event().wait())
        settling = asyncio.create_task(capture.settle(running))
        try:
            await asyncio.sleep(.02)
            self.assertFalse(settling.done())
            capture.events = {'bot-llm-stopped': 1, 'bot-stopped-speaking': 1}
            await asyncio.wait_for(settling, .5)
        finally:
            running.cancel()
            settling.cancel()
            await asyncio.gather(running, settling, return_exceptions=True)

    async def test_error_diagnostics_do_not_retain_message_body(self):
        capture = paired.Capture()
        capture.event({'type': 'error', 'message': 'private-body anthropic 401'})
        self.assertEqual(capture.errors[0]['categories'], ['anthropic', '401'])
        self.assertNotIn('private-body', str(capture.errors))


if __name__ == '__main__': unittest.main()
