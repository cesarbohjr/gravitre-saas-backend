import unittest
from scripts.pr587_kws_qualification import evaluate_trials, inspect_manifest, REQUIRED

class KwsQualificationTests(unittest.TestCase):
    def test_missing_assets_and_labels_block(self):
        problems = inspect_manifest({"model": {"trained_phrase": "cancel"}, "recordings": []}, __import__("pathlib").Path("/tmp"))
        self.assertIn("trained_model_asset_missing_or_unpinned", problems)
        self.assertIn("model_not_trained_for_distinct_cancel_command", problems)
        self.assertIn("recording_manifest_empty", problems)
        for label in REQUIRED:
            self.assertIn("missing_label:" + label, problems)

    def test_false_cancel_blocks(self):
        trials = [
            {"recording_sha256": "a", "label": "negation", "fired": True, "detection_wall_ms": 120}
            for _ in range(3)
        ]
        self.assertIn("false_task_cancel", evaluate_trials(trials))

    def test_recognition_late_blocks(self):
        trials = [{"recording_sha256": "b", "label": "task_cancel", "fired": True, "detection_wall_ms": 351} for _ in range(3)]
        self.assertIn("missed_or_late_positive", evaluate_trials(trials))

    def test_single_repetition_blocks(self):
        trials = [{"recording_sha256": "c", "label": "task_cancel", "fired": True, "detection_wall_ms": 140}]
        self.assertIn("insufficient_repetitions", evaluate_trials(trials))

if __name__ == "__main__":
    unittest.main()
