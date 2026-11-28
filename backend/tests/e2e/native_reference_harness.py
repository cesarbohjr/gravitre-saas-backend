"""Loopback-only synthetic native WebRTC transport test; no vendor requests."""
import asyncio
import math
import struct
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, InterruptionFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams

app = FastAPI()
tasks = set()

class ScriptedAudio(FrameProcessor):
    """Detect synthetic input tones, emit deterministic distinct reply tones."""
    def __init__(self):
        super().__init__()
        self.active = None
        self.last = 0
        self.generation = 0

    async def emit(self, freq, generation):
        rate = 24000
        for n in range(100):
            if generation != self.generation:
                return
            pcm = struct.pack("<480h", *(int(8000*math.sin(2*math.pi*freq*(n*480+i)/rate)) for i in range(480)))
            await self.push_frame(OutputAudioRawFrame(audio=pcm, sample_rate=rate, num_channels=1))
            await asyncio.sleep(.02)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            samples = struct.unpack("<%dh" % (len(frame.audio)//2), frame.audio)
            if samples and max(abs(s) for s in samples) > 1000:
                crossings = sum(a <= 0 < b for a,b in zip(samples,samples[1:]))
                hz = crossings * frame.sample_rate / len(samples)
                marker = 1 if 350 < hz < 550 else 2 if 650 < hz < 950 else 0
                if marker and marker != self.last:
                    self.last = marker
                    self.generation += 1
                    if self.active:
                        self.active.cancel()
                        await asyncio.gather(self.active, return_exceptions=True)
                        await self.push_frame(InterruptionFrame())
                    self.active = asyncio.create_task(self.emit(1100 if marker == 1 else 1700, self.generation))
            return
        await self.push_frame(frame, direction)

@app.get("/", response_class=HTMLResponse)
async def index():
    return Path(__file__).with_name("native_reference_browser.html").read_text()

@app.post("/offer")
async def offer(body: dict):
    connection = SmallWebRTCConnection(ice_servers=[])
    await connection.initialize(body["sdp"], body["type"])
    transport = SmallWebRTCTransport(webrtc_connection=connection, params=TransportParams(audio_in_enabled=True,audio_out_enabled=True))
    script = ScriptedAudio()
    task = PipelineTask(Pipeline([transport.input(),script,transport.output()]), params=PipelineParams())
    @transport.event_handler("on_client_disconnected")
    async def disconnected(*_):
        if script.active:
            script.active.cancel()
        await task.cancel()
    running = asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
    tasks.add(running)
    running.add_done_callback(tasks.discard)
    return connection.get_answer()
