"""Reference-only instrumentation for the pinned Pipecat 1.12.0 track.
No replacement of recv pacing, encoding or media clock.
"""
from collections import deque
import math
import struct
import time
from importlib.metadata import version

def frequency(data,rate):
    values=struct.unpack("<%dh"%(len(data)//2),data)
    if not values or max(abs(v) for v in values)<1000:
        return 0
    return round(sum(a<=0<b for a,b in zip(values,values[1:]))*rate/len(values))

class SenderProbe:
    def __init__(self,track,observe):
        if version("pipecat-ai")!="1.12.0" or not isinstance(track._chunk_queue,deque):
            raise RuntimeError("unsupported pinned sender contract")
        self.track=track
        self.observe=observe
        self.times={}
        add,recv=track.add_audio_bytes,track.recv
        def observed_add(data):
            before=len(track._chunk_queue)
            future=add(data)
            now=time.monotonic_ns()/1e6
            for item in list(track._chunk_queue)[before:]:
                self.times[id(item)]=now
            observe(boundary="track_enqueue",depth=len(track._chunk_queue),added=len(track._chunk_queue)-before)
            return future
        async def observed_recv():
            frame=await recv()
            # Original recv has completed its native dequeue; no await before snapshot.
            live={id(item) for item in track._chunk_queue}
            removed=[self.times.pop(k) for k in list(self.times) if k not in live]
            data=frame.to_ndarray().tobytes()
            observe(boundary="track_dequeue",depth=len(track._chunk_queue),frequency=frequency(data,frame.sample_rate),pts=frame.pts,residenceMs=time.monotonic_ns()/1e6-removed[0] if len(removed)==1 else None)
            return frame
        track.add_audio_bytes=observed_add
        track.recv=observed_recv

    def snapshot(self,phase):
        self.observe(boundary="track_interrupt_"+phase,depth=len(self.track._chunk_queue))

    def clear_cancelled(self):
        # Only valid for the isolated, entirely interruptible synthetic fixture.
        # Called after the upstream sender task has been cancelled by Pipecat.
        queue=self.track._chunk_queue
        dropped=len(queue)
        while queue:
            item=queue.popleft()
            self.times.pop(id(item),None)
            _,future=item
            if future is not None and not future.done():
                future.cancel()
        self.observe(boundary="track_clear",dropped=dropped,depth=len(queue))
        return dropped
