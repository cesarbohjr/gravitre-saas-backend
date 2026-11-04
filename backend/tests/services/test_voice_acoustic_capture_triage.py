"""Pure offline analysis contracts for explicit browser acoustic captures."""
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/analyze_voice_acoustic_capture.py"
spec = importlib.util.spec_from_file_location("acoustic_capture_triage", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def manifest(events):
    return {
        "schema": "gravitre.acoustic-acceptance.v1",
        "captured_audio_kind": "post_duck_browser_stream",
        "observations": [
            {"event": kind, "monotonic_ms": when,
             **({"state": state} if state is not None else {})}
            for kind, when, state in events
        ],
        "limits": {"observations_truncated": False},
    }


class AcousticTriageContracts(unittest.TestCase):
    def test_detects_distinct_candidate_signatures_not_quality_claims(self):
        rows = [
            ("context_state", 0, "running"),
            ("pcm_enqueue", 10, None),
            ("duck", 50, None),
            ("pcm_enqueue", 230, None),
            ("context_state", 275, "suspended"),
            ("unduck", 360, None),
            ("flush", 400, None),
        ]
        result = module.analyze(manifest(rows), audio=b"fixture")
        self.assertIn("long_client_pcm_arrival_gap__cause_unverified", result["candidate_signatures"])
        self.assertIn("sustained_duck__check_overlap_classification", result["candidate_signatures"])
        self.assertIn("audio_context_not_running__check_browser_output", result["candidate_signatures"])
        self.assertIn("flush_observed__correlate_stop_or_barge_in", result["candidate_signatures"])
        self.assertEqual(result["physical_speaker_quality"], "NOT_VERIFIED")
        self.assertEqual(result["independent_listening"], "NOT_RUN")
        self.assertEqual(len(result["audio_sha256"]), 64)

    def test_clean_stream_has_no_suspected_gap(self):
        result = module.analyze(manifest([
            ("pcm_enqueue", 0, None),
            ("pcm_enqueue", 40, None),
            ("pcm_enqueue", 80, None),
        ]))
        self.assertEqual(result["candidate_signatures"], [])
        self.assertEqual(result["maximum_pcm_arrival_gap_ms"], 40)
        self.assertIsNone(result["audio_sha256"])

    def test_flush_breaks_cross_reply_arrival_gap(self):
        result = module.analyze(manifest([
            ("pcm_enqueue", 10, None),
            ("flush", 25, None),
            ("pcm_enqueue", 1000, None),
        ]))
        self.assertNotIn("long_client_pcm_arrival_gap__cause_unverified", result["candidate_signatures"])

    def test_does_not_allow_bad_or_unbounded_manifest(self):
        with self.assertRaises(ValueError):
            module.analyze({"schema": "bad", "observations": []})
        with self.assertRaises(ValueError):
            module.analyze(manifest([("pcm_enqueue", 100, None), ("pcm_enqueue", 0, None)]))
        too_large = manifest([("pcm_enqueue", i, None) for i in range(12001)])
        with self.assertRaises(ValueError):
            module.analyze(too_large)


if __name__ == "__main__":
    unittest.main()
