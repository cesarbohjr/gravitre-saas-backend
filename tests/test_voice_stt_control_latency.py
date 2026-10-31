import asyncio
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

spec = importlib.util.spec_from_file_location("latency", Path(__file__).resolve().parents[1] / "scripts/voice_stt_control_latency.py")
latency = importlib.util.module_from_spec(spec)
spec.loader.exec_module(latency)


class ControlLatencyTests(unittest.TestCase):
    def test_only_clear_control_word_is_reported(self):
        for text, expected in (("Cancel it.", True), ("uh-huh", False), ("stopwatch", False), (None, False)):
            with self.subTest(text=text):
                self.assertEqual(latency.observation(dict(type="TurnInfo", event="StartOfTurn", transcript=text), "flux"),
                                 (True, bool(text), expected))

    def test_nova_interim_and_speech_start_are_separate(self):
        self.assertEqual(latency.observation(dict(type="SpeechStarted"), "nova3"), (True, False, False))
        self.assertEqual(latency.observation(dict(type="Results", is_final=False,
            channel=dict(alternatives=[dict(transcript="cancel")])), "nova3"), (False, True, True))

    def test_scribe_original_transcripts_only_and_unbiased_pcm_transport(self):
        for event in ("partial_transcript", "committed_transcript"):
            self.assertEqual(latency.observation(dict(message_type=event, text="Cancel it."), "scribe"),
                             (False, True, True))
        self.assertEqual(latency.observation(dict(message_type="edited_transcript", text="cancel"), "scribe"),
                         (False, False, False))
        url, headers = latency.connection_config("test-key", "scribe")
        self.assertTrue(url.startswith("wss://api.elevenlabs.io/v1/speech-to-text/realtime?"))
        self.assertNotIn("test-key", url)
        self.assertNotIn("keyterms", url)
        self.assertNotIn("transcript_edit", url)
        self.assertEqual(headers, {"xi-api-key": "test-key"})
        data = json.loads(latency.audio_message(b"\x00\x01" * 320, "scribe"))
        self.assertEqual(base64.b64decode(data["audio_base_64"]), b"\x00\x01" * 320)
        self.assertFalse(data["commit"])
        self.assertEqual(data["sample_rate"], 16000)

    def test_wrong_fixture_format_fails_before_digest_or_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            with wave.open(str(Path(directory) / "cancel-input.wav"), "wb") as w:
                w.setparams((2, 2, 16000, 0, "NONE", "not compressed"))
                w.writeframes(bytes(6400))
            with self.assertRaisesRegex(ValueError, "format"):
                latency.fixture(Path(directory), "cancel")

    def test_changed_fixture_fails_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            with wave.open(str(Path(directory) / "cancel-input.wav"), "wb") as w:
                w.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                w.writeframes(bytes(6400))
            with patch.object(latency, "trial") as trial:
                with self.assertRaisesRegex(ValueError, "digest"):
                    asyncio.run(latency.run(Path(directory), "unused", "offline"))
                trial.assert_not_called()

    def test_all_matched_trials_retained_even_on_failures(self):
        async def fake_trial(key, model, case, pcm, repetition):
            return dict(status="TRANSPORT_OR_PROVIDER_ERROR", model=model, case=case, repetition=repetition)
        with patch.object(latency, "fixture", return_value=bytes(6400)), patch.object(latency, "trial", side_effect=fake_trial):
            report = asyncio.run(latency.run(Path("unused"), "unused", "offline"))
        self.assertEqual(len(report["trials"]), 18)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertFalse(report["certified"])
        self.assertFalse(report["runtime_changed"])

    def test_scribe_failures_retained_and_credentials_routed_to_own_provider(self):
        calls = []
        async def fake_trial(key, model, case, pcm, repetition):
            calls.append((key, model, case, repetition))
            return dict(status="TRANSPORT_OR_PROVIDER_ERROR", model=model, case=case, repetition=repetition)
        with patch.object(latency, "fixture", return_value=bytes(6400)), patch.object(latency, "trial", side_effect=fake_trial):
            report = asyncio.run(latency.run(Path("unused"), "deepgram-test", "offline", "scribe-test"))
        self.assertEqual(len(report["trials"]), 27)
        self.assertEqual({c[2] for c in calls}, {"cancel", "backchannel", "ordinary_request"})
        for key, model, _, _ in calls:
            self.assertEqual(key, "scribe-test" if model == "scribe" else "deepgram-test")
        self.assertNotIn("scribe-test", json.dumps(report))
        self.assertEqual(report["status"], "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
