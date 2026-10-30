import importlib.util
from pathlib import Path
import unittest
import asyncio
import time
import hashlib
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_pinned_recording_rejects_changed_pcm(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.wav'
            original = bytes(640)
            paired.wav(path, original, 16000)
            digest = hashlib.sha256(original).hexdigest()
            self.assertEqual(paired.verified_fixture(path, digest), original)
            paired.wav(path, b'\x01\x00' * 320, 16000)
            with self.assertRaises(ValueError):
                paired.verified_fixture(path, digest)

    def test_cancel_requires_a_final_stt_transcript(self):
        capture = paired.Capture()
        with patch('app.services.spoken_write_approval.classify_spoken_write_approval',
                   return_value=SimpleNamespace(decision='reject', invoke_allowed=False)) as classify:
            capture.event({'type': 'transcript', 'text': 'Cancel it. Do not send anything.', 'final': False})
            self.assertFalse(capture.cancel_recognized)
            classify.assert_not_called()
            capture.event({'type': 'transcript', 'text': 'Cancel it. Do not send anything.', 'final': True})
            self.assertTrue(capture.cancel_recognized)
            classify.assert_called_once_with('Cancel it. Do not send anything.')


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
            capture.event({'type': 'bot-llm-stopped'})
            capture.event({'type': 'assistant_turn.complete'})
            capture.event({'type': 'bot-stopped-speaking'})
            await asyncio.wait_for(settling, .5)
        finally:
            running.cancel()
            settling.cancel()
            await asyncio.gather(running, settling, return_exceptions=True)

    async def test_ack_stop_before_turn_completion_cannot_end_final_capture(self):
        capture = paired.Capture()
        capture.first = capture.last = time.monotonic() - 10
        capture.event({'type': 'bot-llm-stopped'})
        capture.event({'type': 'bot-stopped-speaking'})
        capture.event({'type': 'assistant_turn.complete'})
        running = asyncio.create_task(asyncio.Event().wait())
        settling = asyncio.create_task(capture.settle(running))
        try:
            await asyncio.sleep(.02)
            self.assertFalse(settling.done())
            capture.event({'type': 'bot-stopped-speaking'})
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
