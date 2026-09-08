/**
 * Voice 3.0 Phase 1 — microphone capture, level telemetry, pre-roll, near/far profiles.
 */

import type { VoiceStatus } from "@/lib/tier1-voice-client"
import {
  getStoredMicDeviceId,
  resolveMicFieldProfile,
  type MicFieldProfile,
} from "@/lib/voice-mic-devices"

export type VoiceMicPhase1Flags = {
  agcV2: boolean
  micTelemetry: boolean
  prerollV2: boolean
  prerollMs: number
  micSelector: boolean
  nearFarV1: boolean
}

export type VoiceMicPhase2Flags = {
  silentTapV2: boolean
  echoTestMode: boolean
  krispEnabled: boolean
}

export type EchoLeakSnapshot = {
  agent_speaking_rms_peak: number
  agent_speaking_rms_avg: number
  samples: number
  echo_leak_suspected: boolean
}

export type MicEffectiveSettings = {
  deviceId?: string
  label?: string
  sampleRate?: number
  channelCount?: number
  echoCancellation?: boolean
  noiseSuppression?: boolean
  autoGainControl?: boolean
  latency?: number
  sampleSize?: number
}

export type MicLevelSnapshot = {
  rms: number
  peak: number
  noise_floor: number
  speech_rms: number
  snr: number
  clipping_pct: number
}

export type MicCaptureTuning = {
  profile: Exclude<MicFieldProfile, "auto">
  bargeInThreshold: number
  bargeInFrames: number
  speechOnsetRms: number
  speechReleaseRms: number
  softwareGain: number
  prerollMs: number
}

const DEFAULT_FLAGS: VoiceMicPhase1Flags = {
  agcV2: false,
  micTelemetry: false,
  prerollV2: false,
  prerollMs: 300,
  micSelector: false,
  nearFarV1: false,
}

export function voiceMicPhase2FlagsFromStatus(status?: VoiceStatus | null): VoiceMicPhase2Flags {
  const p2 = status?.phase2_echo_noise
  return {
    silentTapV2: p2?.mic_silent_tap_v2 !== false,
    echoTestMode: Boolean(p2?.echo_test_mode),
    krispEnabled: Boolean(p2?.krisp_enabled),
  }
}

export class EchoLeakMonitor {
  private sum = 0
  private count = 0
  private peak = 0

  observe(rms: number): void {
    this.sum += rms
    this.count += 1
    if (rms > this.peak) this.peak = rms
  }

  reset(): EchoLeakSnapshot {
    const avg = this.count > 0 ? this.sum / this.count : 0
    const out: EchoLeakSnapshot = {
      agent_speaking_rms_peak: round4(this.peak),
      agent_speaking_rms_avg: round4(avg),
      samples: this.count,
      echo_leak_suspected: this.peak > 0.025 || avg > 0.012,
    }
    this.sum = 0
    this.count = 0
    this.peak = 0
    return out
  }
}

export function voiceMicPhase1FlagsFromStatus(status?: VoiceStatus | null): VoiceMicPhase1Flags {
  const p1 = status?.phase1_mic_capture
  if (!p1) return { ...DEFAULT_FLAGS }
  return {
    agcV2: Boolean(p1.agc_v2),
    micTelemetry: Boolean(p1.mic_telemetry_v1),
    prerollV2: Boolean(p1.preroll_v2),
    prerollMs: typeof p1.preroll_ms === "number" && p1.preroll_ms > 0 ? p1.preroll_ms : 300,
    micSelector: Boolean(p1.mic_selector_v1),
    nearFarV1: Boolean(p1.near_far_v1),
  }
}

export function buildMicAudioConstraints(
  flags: VoiceMicPhase1Flags,
  options?: {
    deviceId?: string | null
    profileOverride?: MicFieldProfile | null
    deviceLabel?: string
  },
): MediaTrackConstraints {
  const profile =
    flags.nearFarV1 && options?.deviceLabel
      ? resolveMicFieldProfile(options.deviceLabel, options.profileOverride)
      : "far_field"

  const deviceId =
    flags.micSelector && options?.deviceId
      ? options.deviceId
      : flags.micSelector
        ? getStoredMicDeviceId() || undefined
        : undefined

  const base: MediaTrackConstraints = {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: profile === "far_field",
  }

  if (flags.agcV2) {
    base.autoGainControl = true
  }

  if (deviceId) {
    base.deviceId = { exact: deviceId }
  }

  return base
}

export function readEffectiveMicSettings(track: MediaStreamTrack): MicEffectiveSettings {
  const settings = track.getSettings?.() ?? {}
  // `latency` is present in Chromium getSettings() but not in all TS DOM lib versions.
  const latencyMs = (settings as MediaTrackSettings & { latency?: number }).latency
  return {
    deviceId: settings.deviceId,
    label: track.label || undefined,
    sampleRate: settings.sampleRate,
    channelCount: settings.channelCount,
    echoCancellation: settings.echoCancellation,
    noiseSuppression: settings.noiseSuppression,
    autoGainControl: settings.autoGainControl,
    latency: latencyMs,
    sampleSize: settings.sampleSize,
  }
}

export function resolveMicCaptureTuning(
  flags: VoiceMicPhase1Flags,
  profile: Exclude<MicFieldProfile, "auto">,
): MicCaptureTuning {
  const prerollMs = flags.prerollV2 ? flags.prerollMs : 0
  if (profile === "near_field") {
    return {
      profile,
      bargeInThreshold: 0.035,
      bargeInFrames: 3,
      speechOnsetRms: 0.012,
      speechReleaseRms: 0.008,
      softwareGain: 1,
      prerollMs,
    }
  }
  return {
    profile: "far_field",
    bargeInThreshold: 0.03,
    bargeInFrames: 3,
    speechOnsetRms: 0.01,
    speechReleaseRms: 0.007,
    softwareGain: 1.15,
    prerollMs,
  }
}

/** Rolling PCM16 @ 16 kHz pre-roll buffer for first-word capture. */
export class AudioPreRollBuffer {
  private readonly maxSamples: number
  private chunks: Int16Array[] = []
  private total = 0

  constructor(prerollMs: number, sampleRate = 16000) {
    this.maxSamples = Math.max(1, Math.floor((sampleRate * prerollMs) / 1000))
  }

  push(pcm: Int16Array): void {
    if (this.maxSamples <= 0 || pcm.length === 0) return
    this.chunks.push(pcm)
    this.total += pcm.length
    while (this.total > this.maxSamples && this.chunks.length > 0) {
      const first = this.chunks.shift()
      if (first) this.total -= first.length
    }
  }

  snapshot(): Int16Array {
    if (this.total <= 0) return new Int16Array(0)
    const out = new Int16Array(this.total)
    let offset = 0
    for (const chunk of this.chunks) {
      out.set(chunk, offset)
      offset += chunk.length
    }
    return out
  }

  clear(): void {
    this.chunks = []
    this.total = 0
  }
}

export class MicLevelTracker {
  private noiseFloor = 0.002
  private speechRms = 0
  private clipCount = 0
  private frameCount = 0

  update(input: Float32Array, gain = 1): MicLevelSnapshot {
    let sumSq = 0
    let peak = 0
    let clips = 0
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, (input[i] ?? 0) * gain))
      const a = Math.abs(s)
      if (a > peak) peak = a
      sumSq += s * s
      if (a >= 0.98) clips += 1
    }
    const rms = Math.sqrt(sumSq / Math.max(1, input.length))
    this.frameCount += 1
    this.clipCount += clips

    if (rms < this.speechOnsetThreshold()) {
      this.noiseFloor = this.noiseFloor * 0.92 + rms * 0.08
    } else {
      this.speechRms = this.speechRms * 0.85 + rms * 0.15
    }

    const snr = this.noiseFloor > 0 ? rms / this.noiseFloor : rms > 0 ? 99 : 0
    return {
      rms: round4(rms),
      peak: round4(peak),
      noise_floor: round4(this.noiseFloor),
      speech_rms: round4(this.speechRms),
      snr: round2(snr),
      clipping_pct: round2((this.clipCount / Math.max(1, this.frameCount * input.length)) * 100),
    }
  }

  private speechOnsetThreshold(): number {
    return Math.max(0.006, this.noiseFloor * 2.5)
  }
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

export function concatPcm16(a: Int16Array, b: Int16Array): Int16Array {
  if (a.length === 0) return b
  if (b.length === 0) return a
  const out = new Int16Array(a.length + b.length)
  out.set(a, 0)
  out.set(b, a.length)
  return out
}

export type SpeechGateState = {
  active: boolean
  prerollFlushed: boolean
}

export function updateSpeechGate(
  gate: SpeechGateState,
  rms: number,
  tuning: MicCaptureTuning,
): SpeechGateState {
  if (!tuning.prerollMs) return gate
  if (gate.active) {
    if (rms < tuning.speechReleaseRms) {
      return { active: false, prerollFlushed: false }
    }
    return gate
  }
  if (rms >= tuning.speechOnsetRms) {
    return { active: true, prerollFlushed: false }
  }
  return gate
}

export async function acquireVoiceMicrophoneStream(options: {
  flags: VoiceMicPhase1Flags
  deviceId?: string | null
  profileOverride?: MicFieldProfile | null
}): Promise<{
  stream: MediaStream
  effective: MicEffectiveSettings
  tuning: MicCaptureTuning
  profile: Exclude<MicFieldProfile, "auto">
}> {
  const constraints = buildMicAudioConstraints(options.flags, {
    deviceId: options.deviceId,
    profileOverride: options.profileOverride,
  })
  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: constraints })
  } catch (err) {
    if (constraints.deviceId) {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: buildMicAudioConstraints(options.flags, { profileOverride: options.profileOverride }),
      })
    } else {
      throw err
    }
  }
  const track = stream.getAudioTracks()[0]
  const effective = readEffectiveMicSettings(track)
  const profile = options.flags.nearFarV1
    ? resolveMicFieldProfile(effective.label || track.label || "", options.profileOverride)
    : "far_field"
  const tuning = resolveMicCaptureTuning(options.flags, profile)
  if (typeof console !== "undefined" && console.info) {
    console.info("[gravitre-voice] mic effective settings", {
      requested: constraints,
      effective,
      capabilities: track.getCapabilities?.() ?? null,
      profile,
      tuning,
    })
  }
  return { stream, effective, tuning, profile }
}

export type VoiceMicProcessorHandle = {
  processor: ScriptProcessorNode
  levelTracker: MicLevelTracker
  getLastLevels: () => MicLevelSnapshot | null
  getSpeechGate: () => SpeechGateState
}

/** Shared ScriptProcessor wiring for Pipecat + HTTP duplex paths. */
export function createVoiceMicProcessor(options: {
  ctx: AudioContext
  stream: MediaStream
  tuning: MicCaptureTuning
  prerollEnabled: boolean
  onPcm: (pcm: Int16Array) => void
  onSpeechActivity?: (active: boolean) => void
  onLevels?: (snapshot: MicLevelSnapshot) => void
  agentSpeaking?: () => boolean
  onBargeIn?: () => void
  /** Phase 2: route mic tap through gain=0 to avoid speaker echo leak. */
  silentTapV2?: boolean
}): VoiceMicProcessorHandle {
  const source = options.ctx.createMediaStreamSource(options.stream)
  const processor = options.ctx.createScriptProcessor(4096, 1, 1)
  const levelTracker = new MicLevelTracker()
  const preroll = new AudioPreRollBuffer(options.tuning.prerollMs)
  let lastLevels: MicLevelSnapshot | null = null
  let speechGate: SpeechGateState = { active: false, prerollFlushed: false }
  let speakingEnergy = 0

  processor.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0)
    const levels = levelTracker.update(input, options.tuning.softwareGain)
    lastLevels = levels
    options.onLevels?.(levels)

    if (options.agentSpeaking?.() && options.onBargeIn) {
      let sum = 0
      for (let i = 0; i < input.length; i++) sum += Math.abs(input[i] ?? 0)
      const avg = sum / Math.max(1, input.length)
      if (avg > options.tuning.bargeInThreshold) {
        speakingEnergy += 1
        if (speakingEnergy >= options.tuning.bargeInFrames) {
          speakingEnergy = 0
          options.onBargeIn()
        }
      } else {
        speakingEnergy = 0
      }
    } else {
      speakingEnergy = 0
    }

    const pcm = downsampleTo16k(input, options.ctx.sampleRate, options.tuning.softwareGain)

    if (options.prerollEnabled && options.tuning.prerollMs > 0) {
      preroll.push(pcm)
      const prev = speechGate.active
      speechGate = updateSpeechGate(speechGate, levels.rms, options.tuning)
      if (speechGate.active && !prev) {
        options.onSpeechActivity?.(true)
      } else if (!speechGate.active && prev) {
        options.onSpeechActivity?.(false)
      }
      if (speechGate.active && !speechGate.prerollFlushed) {
        const snap = preroll.snapshot()
        speechGate = { ...speechGate, prerollFlushed: true }
        options.onPcm(concatPcm16(snap, pcm))
        return
      }
    }

    options.onPcm(pcm)
  }

  source.connect(processor)
  const tapGain = options.ctx.createGain()
  tapGain.gain.value = options.silentTapV2 !== false ? 0 : 1
  processor.connect(tapGain)
  tapGain.connect(options.ctx.destination)

  return {
    processor,
    levelTracker,
    getLastLevels: () => lastLevels,
    getSpeechGate: () => speechGate,
  }
}

function downsampleTo16k(input: Float32Array, inputRate: number, gain = 1): Int16Array {
  if (inputRate === 16000) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, (input[i] ?? 0) * gain))
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return out
  }
  const ratio = inputRate / 16000
  const newLen = Math.max(1, Math.floor(input.length / ratio))
  const out = new Int16Array(newLen)
  for (let i = 0; i < newLen; i++) {
    const s = Math.max(-1, Math.min(1, (input[Math.floor(i * ratio)] ?? 0) * gain))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out
}
