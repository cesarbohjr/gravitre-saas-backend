import importlib.util
from pathlib import Path
import unittest

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


if __name__ == '__main__': unittest.main()
