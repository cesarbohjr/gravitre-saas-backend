import asyncio
import unittest
from pipecat.transports.smallwebrtc.transport import RawAudioTrack
from tests.e2e.native_sender_probe import SenderProbe

class SenderProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_native_write_leaves_chunks_and_clear_cancels_remaining(self):
        track=RawAudioTrack(24000)
        events=[]
        probe=SenderProbe(track,lambda **kw:events.append(kw))
        first=track.add_audio_bytes(bytes(480*4))
        first.cancel()
        self.assertEqual(len(track._chunk_queue),4)
        second=track.add_audio_bytes(bytes(480*2))
        self.assertEqual(probe.clear_cancelled(),6)
        self.assertTrue(second.cancelled())
        self.assertEqual(len(track._chunk_queue),0)
        self.assertEqual((await track.recv()).pts,0)
        fresh=track.add_audio_bytes(bytes(480))
        self.assertEqual((await track.recv()).pts,240)
        self.assertTrue(fresh.result())
        self.assertTrue(any(e['boundary']=='track_dequeue' for e in events))
        track.stop()
