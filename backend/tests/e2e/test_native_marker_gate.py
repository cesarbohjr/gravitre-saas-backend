import unittest
from tests.e2e.native_marker_gate import MarkerGate

class MarkerGateTests(unittest.TestCase):
    def test_single_frame_then_silence(self):
        gate=MarkerGate(2)
        for marker in [2,0,2,0,2,0]:
            self.assertFalse(gate.feed(marker))
    def test_ambiguous_and_changed_markers(self):
        gate=MarkerGate(2)
        for marker in [2,1,2,99,2]:
            self.assertFalse(gate.feed(marker))
        self.assertTrue(gate.feed(2))
        self.assertFalse(gate.feed(2))
    def test_confirmation_counts(self):
        for count in (2,3):
            gate=MarkerGate(count)
            self.assertEqual([gate.feed(2) for _ in range(count)],[False]*(count-1)+[True])

    def test_unsafe_single_frame_mode_rejected(self):
        with self.assertRaises(ValueError):
            MarkerGate(1)

    def test_no_premature_interruption_with_noise_and_single_frame(self):
        gate=MarkerGate(2)
        for marker in [0,2,0,2,99,2,1,2,0,2]:
            self.assertFalse(gate.feed(marker))
        self.assertTrue(gate.feed(2))
