"""Isolated real adapter pipeline probe; never changes live voice selection."""
import argparse
import asyncio
import json
import math
import statistics
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
RATE = 24000
MODEL = "eleven_v3"
FLASH = "eleven_flash_v2_5"
FIXTURE_VERSION = "interrupt-recovery-v3"
TRIALS = 3
LONG = "This is a synthetic voice test. " + "We are checking a continuous spoken response with several separate sentences. " * 6
RECOVERY = "The second response is ready. Thank you for waiting."
MAX_VOICES = 12

def candidate_ids(manifest, sha):
    if not sha or manifest.get("source_sha") != sha or manifest.get("activation_authorized") is not False:
        raise ValueError("manifest identity mismatch")
    ids = [row["candidate_id"] for row in manifest["mapping"] if row.get("candidate_id")]
    if not ids or len(ids) > MAX_VOICES or len(set(ids)) != len(ids) or any(
        not isinstance(v,str) or not re.fullmatch(r"[A-Za-z0-9]{16,64}",v) for v in ids):
        raise ValueError("invalid candidate set")
    return ids

def distribution(values):
    if not values or any(type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in values):
        return None
    ordered = sorted(values)
    return {"count":len(ordered),"p50":statistics.median(ordered),
            "p95":ordered[math.ceil(.95*len(ordered))-1],"max":ordered[-1]}

def cadence(events):
    """Downstream PCM delivery timing, not network packets or audible gaps.

    A virtual real-time consumer starts at the first frame, with no additional
    startup reserve. Deficits quantify delivery pressure, not browser underruns.
    """
    if not events:
        return {"status":"NOT RUN"}
    if any(e["rate"] != RATE or e["channels"] != 1 or e["bytes"] <= 0
           or e["bytes"] % 2 for e in events):
        return {"status":"FAIL"}
    arrivals = [(e["at"]-events[0]["at"])*1000 for e in events]
    gaps = [b-a for a,b in zip(arrivals,arrivals[1:])]
    if any(not math.isfinite(v) or v < 0 for v in gaps):
        return {"status":"FAIL"}
    cursor = 0.0
    deficit = 0.0
    starvation_events = 0
    for at,e in zip(arrivals,events):
        if at > cursor:
            deficit += at-cursor
            starvation_events += 1
        cursor = max(cursor,at)+e["bytes"]/2/RATE*1000
    return {"status":"MEASURED","frames":len(events),"interarrival_ms":distribution(gaps),
            "virtual_zero_reserve_deficit_ms":round(deficit,3),
            "virtual_starvation_events":starvation_events}

def summarize(events, start, cut, recovery, finished):
    # The sink records actual downstream frames, not elapsed reply span.
    first = [e for e in events if e["reply"] == 1 and e["at"] < cut]
    second = [e for e in events if e["reply"] == 2 and e["at"] >= recovery]
    stale = [e for e in events if e["reply"] != 2 and e["at"] >= cut]
    valid = all(e["rate"] == RATE and e["channels"] == 1 and e["bytes"] > 0
                and e["bytes"] % 2 == 0 and e["context"] for e in events)
    contexts1 = {e["context"] for e in first}
    contexts2 = {e["context"] for e in second}
    return {"first_audio_ms": round((first[0]["at"]-start)*1000) if first else None,
            "recovery_first_audio_ms": round((second[0]["at"]-recovery)*1000) if second else None,
            "first_pcm_frames": sum(e["bytes"]//2 for e in first),
            "recovery_pcm_frames": sum(e["bytes"]//2 for e in second),
            "stale_pcm_frames": sum(e["bytes"]//2 for e in stale),
            "contexts_disjoint": bool(contexts1 and contexts2 and not contexts1 & contexts2),
            "frame_format_valid": valid,
            "recovery_stop_observed": finished,
            "initial_cadence":cadence(first),"recovery_cadence":cadence(second),
            "sink_status": "PASS" if first and second and not stale and valid and finished
            and contexts1 and contexts2 and not contexts1 & contexts2 else "FAIL"}

async def probe_voice(key, voice_id, model=MODEL, stt_key=None):
    from pipecat.frames.frames import (Frame, InterruptionFrame, LLMFullResponseStartFrame,
        LLMFullResponseEndFrame, TextFrame, TTSAudioRawFrame, TTSStoppedFrame, EndFrame, ErrorFrame)
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    from app.services.pipecat_voice.tts_factory import build_live_tts_service
    from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
    from app.services.pipecat_voice.json_audio_serializer import ReplyAudioStampProcessor, REPLY_ID_ATTR
    from app.services.pipecat_voice.tts_context_cancel import cancel_elevenlabs_tts_context

    session = VoicePipelineSession()
    adapter = build_live_tts_service(api_key=key, voice_id=voice_id, model=model, sample_rate=RATE)
    stamp = ReplyAudioStampProcessor(voice_session=session)
    events = []
    upstream_audio = []
    first_audio = asyncio.Event()
    interrupted = asyncio.Event()
    recovered = asyncio.Event()
    errors = []
    stops = set()
    recovery_contexts = set()
    recovery_pcm = bytearray()
    recovery_end = asyncio.Event()
    reply2_open = False

    class AdapterTap(FrameProcessor):
        async def process_frame(self, frame: Frame, direction: FrameDirection):
            await super().process_frame(frame,direction)
            if direction == FrameDirection.DOWNSTREAM and isinstance(frame,TTSAudioRawFrame):
                upstream_audio.append({"context":getattr(frame,"context_id",None),
                                       "at":time.monotonic(),"bytes":len(frame.audio)})
            if isinstance(frame,ErrorFrame):
                errors.append(type(frame).__name__)
            await self.push_frame(frame,direction)

    class Sink(FrameProcessor):
        async def process_frame(self, frame: Frame, direction: FrameDirection):
            await super().process_frame(frame,direction)
            if isinstance(frame, ErrorFrame):
                errors.append(type(frame).__name__)
            nonlocal reply2_open
            if direction == FrameDirection.DOWNSTREAM:
                if isinstance(frame, LLMFullResponseStartFrame) and getattr(frame, REPLY_ID_ATTR, None) == 2:
                    reply2_open = True
                if isinstance(frame, LLMFullResponseEndFrame) and reply2_open:
                    recovery_end.set()
                if isinstance(frame, InterruptionFrame):
                    interrupted.set()
                if isinstance(frame, TTSAudioRawFrame):
                    rid = getattr(frame, REPLY_ID_ATTR, None)
                    context = getattr(frame,"context_id",None)
                    events.append({"reply":rid,"context":context,"at":time.monotonic(),
                                   "bytes":len(frame.audio),"rate":frame.sample_rate,"channels":frame.num_channels})
                    if rid == 1:
                        first_audio.set()
                    if rid == 2 and context:
                        recovery_contexts.add(context)
                        if len(recovery_pcm) + len(frame.audio) > RATE * 2 * 30:
                            errors.append("oversized_recovery")
                        else:
                            recovery_pcm.extend(frame.audio)
                if isinstance(frame,TTSStoppedFrame):
                    ctx = getattr(frame,"context_id",None)
                    stops.add(ctx)
                    if ctx in recovery_contexts:
                        recovered.set()
            await self.push_frame(frame,direction)

    task = PipelineTask(Pipeline([adapter,AdapterTap(),stamp,Sink()]),
        params=PipelineParams(audio_out_sample_rate=RATE, enable_metrics=True))
    runner = asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
    async def send(text):
        rid = session.begin_reply()
        frame = LLMFullResponseStartFrame()
        setattr(frame,REPLY_ID_ATTR,rid)
        await task.queue_frames([frame,TextFrame(text),LLMFullResponseEndFrame()])

    try:
        start = time.monotonic()
        await send(LONG)
        await asyncio.wait_for(first_audio.wait(),20)
        # Do not claim mid-synthesis interruption if the provider already
        # completed the context before the cut.
        first_context = events[0]["context"]
        active_at_cut = bool(first_context and first_context not in stops)
        cut = time.monotonic()
        session.cancel_reply_audio(1)
        # Start the production cancellation hook before queuing the interrupt;
        # otherwise Pipecat may clear the context before the hook can inspect it.
        cancel_task = asyncio.create_task(cancel_elevenlabs_tts_context(adapter))
        await asyncio.sleep(0)
        await task.queue_frame(InterruptionFrame())
        cancel = await asyncio.wait_for(cancel_task,5)
        cancel_ms = round((time.monotonic()-cut)*1000)
        await asyncio.wait_for(interrupted.wait(),5)
        await asyncio.sleep(.25)
        recovery = time.monotonic()
        await send(RECOVERY)
        await asyncio.wait_for(recovered.wait(),20)
        await asyncio.wait_for(recovery_end.wait(),20)
        await asyncio.sleep(.25)
        result = summarize(events,start,cut,recovery,recovered.is_set())
        result.update({"voice_id":voice_id,"model":model,"fixture_version":FIXTURE_VERSION,"active_context_at_cut":active_at_cut,
                       "cancel_hook_reported":cancel.get("cancelled") is True,
                       "cancel_method":cancel.get("method"),"dropped_frames":stamp.dropped_frames,
                       "error_count":len(errors),
                       "scope":"actual adapter downstream PCM; not device playback or full conversation"})
        result["cancel_hook_ms"] = cancel_ms
        result["adapter_old_context_pcm_after_hook"] = sum(e["bytes"]//2 for e in upstream_audio
            if e["context"] == first_context and e["at"] >= cut + cancel_ms/1000)
        result["remote_cancel_confirmation"] = "NOT ESTABLISHED"
        result["cancel_context_matches"] = cancel.get("context_id") == first_context
        result["cancel_session_kept"] = cancel.get("session_kept") is True
        result["recovery_all_contexts_stopped"] = bool(recovery_contexts and recovery_contexts <= stops)
        result["recovery_end_observed"] = recovery_end.is_set()
        result["recovery_wer"] = None
        if stt_key and recovery_pcm:
            try:
                result["recovery_wer"] = await asyncio.to_thread(recovery_wer, stt_key, bytes(recovery_pcm))
            except Exception as exc:
                result["stt_error_type"] = type(exc).__name__
        result["status"] = evaluate_status(result)
        return result
    finally:
        if not runner.done():
            try:
                await task.queue_frame(EndFrame())
                await asyncio.wait_for(runner,5)
            except Exception:
                runner.cancel()
                await asyncio.gather(runner,return_exceptions=True)

def recovery_wer(key, pcm):
    import io
    import wave
    import httpx
    from voice3_acoustic_eval import word_error_rate
    buf = io.BytesIO()
    with wave.open(buf,"wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm)
    with httpx.Client(timeout=15,follow_redirects=False) as client:
        response = client.post("https://api.deepgram.com/v1/listen",
            params={"model":"nova-3","language":"en"},
            headers={"Authorization":"Token "+key,"Content-Type":"audio/wav"},
            content=buf.getvalue())
        response.raise_for_status()
        transcript = response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]
    return word_error_rate(RECOVERY,transcript)

def evaluate_status(row):
    # Hook acknowledgement is necessary, not proof the remote provider stopped.
    required = ("active_context_at_cut","cancel_hook_reported","cancel_context_matches",
                "cancel_session_kept","recovery_all_contexts_stopped","recovery_end_observed")
    if row.get("sink_status") != "PASS" or row.get("error_count") != 0 or not all(row.get(k) is True for k in required):
        return "FAIL"
    wer = row.get("recovery_wer")
    if wer is None:
        return "NOT RUN"
    # Strict synthetic phrase completeness screen, not general speech quality.
    return "PASS" if type(wer) in (int,float) and wer == 0 else "FAIL"

def compare_latency(flash, dialogue):
    keys = ("first_audio_ms","recovery_first_audio_ms","cancel_hook_ms")
    if any(type(row.get(k)) not in (int,float) or not 0 <= row[k] <= 60000
           for row in (flash,dialogue) for k in keys):
        return {"status":"NOT RUN"}
    return {"status":"MEASURED","delta_ms":{k:dialogue[k]-flash[k] for k in keys},
            "performance_gate":"NOT RUN","reason":"single paired observation; release budget not calibrated"}

def trial_summary(flash, dialogue):
    keys = ("first_audio_ms","recovery_first_audio_ms","cancel_hook_ms")
    if len(flash) != TRIALS or len(dialogue) != TRIALS:
        return {"status":"NOT RUN","performance_gate":"NOT RUN"}
    metrics = {}
    for key in keys:
        a,b = distribution([r.get(key) for r in flash]),distribution([r.get(key) for r in dialogue])
        if a is None or b is None:
            return {"status":"NOT RUN","performance_gate":"NOT RUN"}
        metrics[key] = {"flash":a,"dialogue":b,"p50_delta":b["p50"]-a["p50"],
                        "p95_delta":b["p95"]-a["p95"]}
    return {"status":"MEASURED","performance_gate":"NOT RUN","metrics":metrics,
            "reason":"three paired cold-start trials; nearest-rank p95 is the maximum, not a calibrated tail estimate"}

async def run(env, manifest):
    result = {"source_sha":env.get("GITHUB_SHA",""),"model":MODEL,"fixture_version":FIXTURE_VERSION,
              "status":"NOT RUN","rows":[],"activation_authorized":False}
    if not env.get("ELEVENLABS_API_KEY"):
        return result
    try:
        ids = candidate_ids(manifest,result["source_sha"])
    except (ValueError,KeyError,TypeError):
        result["status"]="FAIL"
        return result
    for voice in ids:
        pair = {FLASH:[],MODEL:[]}
        for trial in range(TRIALS):
            # Alternate order to reduce systematic warm-up/provider load bias.
            for model in ((FLASH,MODEL) if trial%2 == 0 else (MODEL,FLASH)):
                try:
                    row = await asyncio.wait_for(probe_voice(env["ELEVENLABS_API_KEY"],voice,model,env.get("DEEPGRAM_API_KEY")),60)
                except Exception as exc:
                    row = {"voice_id":voice,"model":model,"status":"FAIL","error_type":type(exc).__name__}
                pair[model].append({**row,"trial":trial})
        result["rows"].append({"voice_id":voice,"flash_trials":pair[FLASH],"dialogue_trials":pair[MODEL],
            "comparison":trial_summary(pair[FLASH],pair[MODEL]),
            "status":"PASS" if all(r["status"]=="PASS" for rows in pair.values() for r in rows) else "FAIL"})
    result["status"]="PASS" if all(r["status"]=="PASS" for r in result["rows"]) else "FAIL"
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    try:
        result=asyncio.run(run(os.environ,json.loads(args.manifest.read_text())))
    except Exception as exc:
        result={"status":"FAIL","source_sha":os.getenv("GITHUB_SHA",""),"error_type":type(exc).__name__}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(result["status"])
    return 0 if result["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
