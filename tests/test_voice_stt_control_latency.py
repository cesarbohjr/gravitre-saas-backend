import asyncio
import importlib.util
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
        self.assertEqual(len(report["trials"]), 12)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertFalse(report["certified"])
        self.assertFalse(report["runtime_changed"])


if __name__ == "__main__":
    unittest.main()
