"""Zero-credit regression for the acoustic cancellation promotion guard."""
import unittest
from scripts.pr587_local_acoustic_candidate import cancel_decision, expected_label
from pathlib import Path

class AcousticPromotionSafetyTests(unittest.TestCase):
    def test_only_complete_explicit_cancel_commands_match(self):
        for phrase in ("cancel", "cancel it", "abort", "never mind"):
            self.assertTrue(cancel_decision(phrase), phrase)
        for phrase in ("don't cancel", "do not cancel", "stop talking",
                       "stop talking but keep working", "can you cancel",
                       "cancer", "council", "she said cancel", "yes", "uh huh"):
            self.assertFalse(cancel_decision(phrase), phrase)

    def test_required_negative_fixtures_are_distinguished(self):
        for name in ("backchannel-input.wav", "speech_stop.wav", "negation.wav"):
            self.assertEqual(expected_label(Path(name)), "not_task_cancel")
        self.assertEqual(expected_label(Path("cancel-input.wav")), "task_cancel")

if __name__ == "__main__":
    unittest.main()
