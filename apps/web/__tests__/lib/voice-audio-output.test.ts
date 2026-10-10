import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const hook = readFileSync(resolve(webRoot, "hooks/use-voice-duplex-session.ts"), "utf8")
const aiWorkspace = readFileSync(resolve(webRoot, "app/(app)/ai/_components/ai-workspace.tsx"), "utf8")
const player = readFileSync(resolve(webRoot, "lib/voice-pcm-player.ts"), "utf8")
const dsp = readFileSync(resolve(webRoot, "public/voice-worklets/voice-dsp.js"), "utf8")
const agentPlayback = readFileSync(resolve(webRoot, "hooks/use-agent-voice-playback.ts"), "utf8")
const outputDiagnosticsRoute = readFileSync(
  resolve(webRoot, "app/api/voice/output-diagnostics/route.ts"),
  "utf8",
)

describe("voice duplex audible output contract", () => {
  it("reuses the AudioContext unlocked by the user gesture", () => {
    expect(hook).toMatch(/getSharedPlaybackContext/)
    expect(hook).toMatch(/audioCtxSharedRef/)
    expect(hook).toMatch(/sharedOutput \?\? new AC\(\)/)
  })

  it("does not silently schedule Pipecat PCM onto a suspended context", () => {
    expect(hook).toMatch(/ctx\.state !== "running" \|\| playbackBlockedRef\.current/)
    expect(hook).toMatch(/pcmBlockedQueueRef/)
    expect(hook).toMatch(/setPlaybackBlocked\(true\)/)
  })

  it("retries queued PCM after an explicit sound-unlock gesture", () => {
    expect(hook).toMatch(/const queuedPcm = pcmBlockedQueueRef\.current\.splice\(0\)/)
    expect(hook).toMatch(/enqueuePcm\(chunk\.pcm, chunk\.sampleRate\)/)
  })

  it("does not close the shared output context when a voice session ends", () => {
    expect(hook).toMatch(/if \(!audioCtxSharedRef\.current\) \{/)
    expect(hook).toMatch(/outputCtx\?\.close\(\)/)
    expect(hook).toMatch(/removeEventListener\("statechange", stateHandler\)/)
  })

  it("fails visibly when assistant text arrives but Pipecat never sends audio", () => {
    expect(hook).toMatch(/audioReplyWatchdogRef/)
    expect(hook).toMatch(/audioFramesReceivedRef/)
    expect(hook).toMatch(/Voice reply arrived, but audible audio was not received/)
    expect(hook).toMatch(/armAudioReplyWatchdog\(\)/)
    expect(hook).toMatch(/clearAudioReplyWatchdog\(\)/)
  })
})


describe("voice physical-output failure handling", () => {
  it("surfaces AudioContext suspension after the session has started", () => {
    expect(hook).toMatch(/addEventListener\("statechange", onOutputStateChange\)/)
    expect(hook).toMatch(/if \(!sessionWantedRef\.current\) return/)
    // iOS "interrupted" output is resumed before asking for a tap.
    expect(hook).toMatch(/ensureAudioOutputRunning\(ctx\)\.then/)
    expect(hook).toMatch(/removeEventListener\("statechange", stateHandler\)/)
  })

  it("does not silently drop PCM when WebAudio source scheduling fails", () => {
    expect(hook).toMatch(/Voice audio could not start\. Tap Enable sound, then try again\./)
    expect(hook).toMatch(/pcmBlockedQueueRef\.current\.unshift/)
    expect(hook).toMatch(/outputFailureNotifiedRef/)
  })

  it("captures Pipecat playback offset before stopping audio on barge-in", () => {
    const capture = hook.indexOf("const pcmOriginBeforeStop = pcmPlayerRef.current?.originTime() ?? null")
    const stop = hook.indexOf("stopPlayback()", capture)
    const send = hook.indexOf("encodePipecatInterrupt({ playbackOffsetMs })", capture)
    expect(capture).toBeGreaterThan(-1)
    expect(stop).toBeGreaterThan(capture)
    expect(send).toBeGreaterThan(stop)
  })
})


describe("voice playback proof vs provider TTFA", () => {
  it("records browser playback only after WebAudio or HTMLAudio actually starts", () => {
    expect(hook).toMatch(/browserAudioPlaybackStartedRef\.current = true/)
    expect(hook).toMatch(/browser_audio_playback_started: true/)
  })

  it("resets browser playback proof at the beginning of a new turn", () => {
    expect(hook).toMatch(/browserAudioPlaybackStartedRef\.current = false/)
    expect(hook).toMatch(/browser_audio_playback_started: false/)
  })

  it("does not treat server TTFA as proof the human heard audio", () => {
    expect(aiWorkspace).toMatch(/result\.latency\?\.browser_audio_playback_started === true/)
    expect(aiWorkspace).not.toMatch(/spokeDuringTurn = typeof result\.latency\?\.session_ttfa_ms/)
  })
})


describe("voice text-only fallback recovery", () => {
  it("hands a text-only Pipecat turn to the existing HTTP TTS path", () => {
    expect(hook).toMatch(/onAudioMissing\?: \(assistantText: string\) => void/)
    expect(hook).toMatch(/audioFallbackTriggeredRef\.current = true/)
    expect(hook).toMatch(/recover\(assistantText\)/)
    expect(hook).toMatch(/agentSpeakingRef\.current = true/)
    expect(aiWorkspace).toMatch(/onAudioMissing: \(assistantText\)/)
    expect(aiWorkspace).toMatch(/speakAgentVoice\(assistantText/)
  })

  it("drops late Pipecat PCM after fallback ownership transfers", () => {
    expect(hook).toMatch(/if \(audioFallbackTriggeredRef\.current\) return/)
    expect(hook).toMatch(/audioFallbackTriggeredRef\.current = false/)
  })
})


describe("voice recovery TTS physical output", () => {
  it("prefers the user-unlocked shared WebAudio context before HTMLAudio fallback", () => {
    expect(agentPlayback).toMatch(/const outputCtx = await unlockVoicePlayback\(\)/)
    expect(agentPlayback).toMatch(/outputCtx\.decodeAudioData/)
    expect(agentPlayback).toMatch(/outputCtx\.createBufferSource\(\)/)
    expect(agentPlayback).toMatch(/source\.connect\(outputCtx\.destination\)/)
    expect(agentPlayback).toMatch(/source\.start\(0\)/)
  })

  it("retains HTMLAudio as codec fallback and exposes an explicit sound-recovery action", () => {
    expect(agentPlayback).toMatch(/Fall through to the retained HTMLAudio recovery path/)
    expect(agentPlayback).toMatch(/new Audio\(url\)/)
    expect(agentPlayback).toMatch(/Tap Enable sound/)
  })

  it("tears down WebAudio recovery sources when playback stops", () => {
    expect(agentPlayback).toMatch(/webAudioSourceRef/)
    expect(agentPlayback).toMatch(/webAudioSourceRef\.current\.stop\(\)/)
    expect(agentPlayback).toMatch(/webAudioSourceRef\.current\.disconnect\(\)/)
  })
})


describe("voice text-only recovery ownership", () => {
  it("prevents post-session auto-TTS from replaying a recovered turn", () => {
    expect(aiWorkspace).toMatch(/voiceAudioRecoveryOwnsTurnRef/)
    expect(aiWorkspace).toMatch(/voiceAudioRecoveryOwnsTurnRef\.current = true/)
    expect(aiWorkspace).toMatch(/const recoveryOwnsTurn = voiceAudioRecoveryOwnsTurnRef\.current/)
    expect(aiWorkspace).toMatch(/spokeDuringTurn \\|\\| duplexOwnsTurn \\|\\| recoveryOwnsTurn/)
  })

  it("resets recovery ownership at each new user turn and when leaving voice", () => {
    const resets = aiWorkspace.match(/voiceAudioRecoveryOwnsTurnRef\.current = false/g) || []
    expect(resets.length).toBeGreaterThanOrEqual(2)
  })
})


describe("voice physical-output telemetry", () => {
  it("proxies browser diagnostics to the FastAPI persistence endpoint", () => {
    expect(outputDiagnosticsRoute).toMatch(/proxyVoiceJson/)
    expect(outputDiagnosticsRoute).toMatch(/\/api\/voice\/output-diagnostics/)
  })

  it("records browser playback lifecycle evidence without audio payloads", () => {
    expect(hook).toMatch(/postVoiceOutputDiagnostics/)
    expect(hook).toMatch(/"audio_silent" : "audio_missing"/)
    expect(hook).toMatch(/emitOutputDiagnostic\("playback_blocked"\)/)
    expect(hook).toMatch(/emitOutputDiagnostic\("playback_started"\)/)
    expect(hook).toMatch(/emitOutputDiagnostic\("playback_recovered"\)/)
  })
})


describe("voice silent-PCM recovery", () => {
  it("does not treat non-empty silent PCM as audible output", () => {
    expect(hook).toMatch(/inspectPcm16Energy\(pcm\)/)
    expect(hook).toMatch(/audibleAudioFramesRef/)
    expect(hook).toMatch(/energy\.audible/)
    expect(hook).toMatch(/audioFramesReceivedRef\.current > 0 \? "audio_silent" : "audio_missing"/)
  })

  it("clears the no-audio watchdog only after audible PCM energy arrives", () => {
    const energy = hook.indexOf("if (energy.audible)")
    const clear = hook.indexOf("clearAudioReplyWatchdog()", energy)
    expect(energy).toBeGreaterThan(-1)
    expect(clear).toBeGreaterThan(energy)
  })
})


describe("voice live turn completion lifecycle", () => {
  it("commits each Pipecat turn while the websocket remains open", () => {
    expect(hook).toMatch(/kind === "assistant_turn\.complete"/)
    expect(hook).toMatch(/pipecatTurnCompletionDispatchedRef/)
    expect(hook).toMatch(/optsRef\.current\.onTurnComplete\?\.\(/)
    expect(hook).toMatch(/duplex_transport_owned: true/)
  })

  it("uses socket close only as a fallback for an uncommitted partial turn", () => {
    expect(hook).toMatch(/!pipecatTurnCompletionDispatchedRef\.current/)
  })

  it("prevents closing Talk from replaying a turn already owned by duplex delivery", () => {
    expect(aiWorkspace).toMatch(/duplexOwnsTurn/)
    expect(aiWorkspace).toMatch(/spokeDuringTurn \|\| duplexOwnsTurn \|\| recoveryOwnsTurn/)
  })

  it("schedules streamed PCM through the jitter buffer, not a 10 ms lead", () => {
    // Playback goes through the player (AudioWorklet queue, or the
    // buffer-source fallback), both of which use the jitter lead policy.
    expect(hook).toMatch(/player\.enqueue\(pcm, sampleRate \|\| 16000\)/)
    expect(player).toMatch(/schedulePcmStart\(/)
    expect(dsp).toMatch(/initialLeadS \?\? 0\.12/)
    expect(hook).not.toMatch(/Math\.max\(ctx\.currentTime \+ 0\.01/)
  })

  it("drops queued reply audio when the server reports a barge-in", () => {
    const handler = hook.slice(hook.indexOf('kind === "speech.interrupted"'))
    expect(handler.slice(0, 1000)).toMatch(/stopPcmPlayback\(\)/)
  })

  it("never replays or resumes a reply the user interrupted", () => {
    const handler = hook.slice(hook.indexOf('kind === "speech.interrupted"'))
    // The no-audio fallback would otherwise speak the whole reply again.
    expect(handler.slice(0, 600)).toMatch(/clearAudioReplyWatchdog\(\)/)
    // Frames are dropped by the interrupted reply's id; the time window is
    // only a fallback for servers that send no id.
    expect(handler.slice(0, 900)).toMatch(/interruptedReplyIdRef\.current = Math\.max\(/)
    expect(handler.slice(0, 900)).toMatch(/dropAudioUntilRef\.current = performance\.now\(\) \+ INTERRUPTED_AUDIO_DROP_MS/)
    const audio = hook.slice(hook.indexOf('kind === "audio"'))
    expect(audio.slice(0, 400)).toMatch(/if \(isInterruptedReplyAudio\(msg\.reply_id\)\) return/)
    expect(hook).toMatch(/return cut !== null && replyId <= cut/)
    // A reconnect starts a new server session whose reply ids restart.
    expect(hook).toMatch(/Reply ids restart with every server session\.\n\s+interruptedReplyIdRef\.current = null/)
    // The next reply's no-audio fallback still arms inside the drop window.
    const text = hook.slice(hook.indexOf('kind === "assistant_text"'))
    expect(text.slice(0, 900)).toMatch(/if \(firstAssistantText && audibleAudioFramesRef\.current === 0\) \{\s+armAudioReplyWatchdog\(\)/)
    // A new user turn lets audio through again, and the mute is time-bounded
    // so an out-of-order transcript can never silence the next answer.
    expect(hook).toMatch(/if \(msg\.final\) \{\s+dropAudioUntilRef\.current = 0/)
    expect(hook).toMatch(/const INTERRUPTED_AUDIO_DROP_MS = \d{3,4}\n/)
  })
})
