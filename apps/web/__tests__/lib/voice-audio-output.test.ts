import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const hook = readFileSync(resolve(webRoot, "hooks/use-voice-duplex-session.ts"), "utf8")
const aiWorkspace = readFileSync(resolve(webRoot, "app/ai/_components/ai-workspace.tsx"), "utf8")
const agentPlayback = readFileSync(resolve(webRoot, "hooks/use-agent-voice-playback.ts"), "utf8")

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
    expect(hook).toMatch(/Voice reply arrived, but no audio was received/)
    expect(hook).toMatch(/armAudioReplyWatchdog\(\)/)
    expect(hook).toMatch(/clearAudioReplyWatchdog\(\)/)
  })
})


describe("voice physical-output failure handling", () => {
  it("surfaces AudioContext suspension after the session has started", () => {
    expect(hook).toMatch(/addEventListener\("statechange", onOutputStateChange\)/)
    expect(hook).toMatch(/sessionWantedRef\.current && ctx\.state !== "running"/)
    expect(hook).toMatch(/removeEventListener\("statechange", stateHandler\)/)
  })

  it("does not silently drop PCM when WebAudio source scheduling fails", () => {
    expect(hook).toMatch(/Voice audio could not start\. Tap Enable sound, then try again\./)
    expect(hook).toMatch(/pcmBlockedQueueRef\.current\.unshift/)
    expect(hook).toMatch(/outputFailureNotifiedRef/)
  })

  it("captures Pipecat playback offset before stopping audio on barge-in", () => {
    const capture = hook.indexOf("const pcmOriginBeforeStop = pcmPlayOriginRef.current")
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
    expect(aiWorkspace).toMatch(/spokeDuringTurn \|\| recoveryOwnsTurn/)
  })

  it("resets recovery ownership at each new user turn and when leaving voice", () => {
    const resets = aiWorkspace.match(/voiceAudioRecoveryOwnsTurnRef\.current = false/g) || []
    expect(resets.length).toBeGreaterThanOrEqual(2)
  })
})
