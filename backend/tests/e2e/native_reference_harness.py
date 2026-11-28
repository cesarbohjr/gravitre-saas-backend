"""Loopback-only synthetic native WebRTC transport test; no vendor requests."""
import asyncio
import math
import struct
import time
from pathlib import Path
from fastapi import HTTPException, Query
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from pipecat.frames.frames import StartFrame
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
observations = []

def observe(**values):
    observations.append(dict(monotonicMs=time.monotonic_ns()/1e6, **values))

class ScriptedAudio(FrameProcessor):
    """Detect synthetic input tones, emit deterministic distinct reply tones."""
    def __init__(self):
        super().__init__()
        self.active = None
        self.last = 0
        self.generation = 0
        self.pending_marker = 0
        self.marker_count = 0

    async def emit(self, freq, generation):
        rate = 24000
        for n in range(100):
            if generation != self.generation:
                return
            pcm = struct.pack("<480h", *(int(8000*math.sin(2*math.pi*freq*(n*480+i)/rate)) for i in range(480)))
            if n == 0:
                observe(boundary='server_output',generation=generation,frequency=freq)
            await self.push_frame(OutputAudioRawFrame(audio=pcm, sample_rate=rate, num_channels=1))
            await asyncio.sleep(.02)

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            samples = struct.unpack("<%dh" % (len(frame.audio)//2), frame.audio)
            if samples and max(abs(s) for s in samples) > 1000:
                crossings = sum(a <= 0 < b for a,b in zip(samples,samples[1:]))
                hz = crossings * frame.sample_rate / len(samples)
                observe(boundary='server_input',peak=max(abs(s) for s in samples),frequency=hz)
                marker = 1 if 350 < hz < 550 else 2 if 650 < hz < 950 else 0
                self.marker_count = self.marker_count + 1 if marker == self.pending_marker else 1
                self.pending_marker = marker
                if marker and marker != self.last and self.marker_count >= 3:
                    observe(boundary='marker_committed',marker=marker)
                    self.last = marker
                    self.generation += 1
                    if self.active:
                        observe(boundary='cancel_requested',generation=self.generation-1)
                        self.active.cancel()
                        await asyncio.gather(self.active, return_exceptions=True)
                        observe(boundary='producer_cancelled',generation=self.generation-1)
                        await self.push_frame(InterruptionFrame())
                        observe(boundary='interrupt_forwarded',generation=self.generation-1)
                    self.active = asyncio.create_task(self.emit(1100 if marker == 1 else 1700, self.generation))
            return
        await self.push_frame(frame, direction)

@app.get("/", response_class=HTMLResponse)
async def index():
    return Path(__file__).with_name("native_reference_browser.html").read_text()

@app.get("/reference-client.js")
async def client_bundle():
    return FileResponse(Path(__file__).with_name("reference-client.bundle.js"), media_type="application/javascript")

@app.get("/clock")
async def clock():
    return {"monotonicMs":time.monotonic_ns()/1e6}

@app.get("/observations")
async def diagnostics():
    return observations[-5000:]

@app.post("/offer")
async def offer(body: dict, chunk_ms: int | None = Query(None)):
    if chunk_ms is not None and chunk_ms not in (10,20,40):
        raise HTTPException(400, 'unsupported native chunk size')
    if 'audio_out_10ms_chunks' not in TransportParams.model_fields:
        raise RuntimeError('pinned SDK lacks native output chunk parameter')
    observations.clear()
    connection = SmallWebRTCConnection(ice_servers=[])
    await connection.initialize(body["sdp"], body["type"])
    transport = SmallWebRTCTransport(webrtc_connection=connection, params=TransportParams(audio_in_enabled=True,audio_out_enabled=True,**({'audio_out_10ms_chunks':chunk_ms//10} if chunk_ms is not None else {})))
    output = transport.output()
    # Observe SDK methods, do not clear or replace their queues. Frame identity may
    # change during native rechunking; residence is reported only for exact matches.
    enqueue = {}
    original_process = output.process_frame
    original_write = output.write_audio_frame
    async def observed_process(frame, direction):
        if isinstance(frame, OutputAudioRawFrame):
            enqueue[frame.id] = time.monotonic_ns()/1e6
            observe(boundary='output_ingress',frameId=frame.id,bytes=len(frame.audio))
        if isinstance(frame, InterruptionFrame):
            observe(boundary='output_interrupt_enter',pendingIngress=len(enqueue))
            try:
                return await original_process(frame,direction)
            finally:
                observe(boundary='output_interrupt_exit',pendingIngress=len(enqueue))
        return await original_process(frame,direction)
    async def observed_write(frame):
        entered = time.monotonic_ns()/1e6
        start = enqueue.pop(frame.id,None)
        observe(boundary='native_write_enter',frameId=frame.id,bytes=len(frame.audio),residenceMs=entered-start if start is not None else None)
        try:
            return await original_write(frame)
        finally:
            observe(boundary='native_write_exit',frameId=frame.id)
    output.process_frame = observed_process
    output.write_audio_frame = observed_write
    observe(boundary='configuration',chunkMs=chunk_ms)
    script = ScriptedAudio()
    task = PipelineTask(Pipeline([transport.input(),script,output]), params=PipelineParams())
    @transport.event_handler("on_client_disconnected")
    async def disconnected(*_):
        if script.active:
            script.active.cancel()
        await task.cancel()
    running = asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
    tasks.add(running)
    running.add_done_callback(tasks.discard)
    return connection.get_answer()
