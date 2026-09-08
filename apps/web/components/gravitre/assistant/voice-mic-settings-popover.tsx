"use client"

/**
 * Mic selector + level test for Voice 3.0 Phase 1 (flag-gated via voice status).
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { Mic, Settings2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import {
  acquireVoiceMicrophoneStream,
  type MicEffectiveSettings,
  type MicLevelSnapshot,
  voiceMicPhase1FlagsFromStatus,
} from "@/lib/voice-mic-capture"
import {
  getStoredMicDeviceId,
  listMicInputDevices,
  setStoredMicDeviceId,
  type MicDeviceOption,
  type MicFieldProfile,
} from "@/lib/voice-mic-devices"
import type { VoiceStatus } from "@/lib/tier1-voice-client"

type Props = {
  voiceStatus?: VoiceStatus | null
  selectedDeviceId?: string | null
  onDeviceChange?: (deviceId: string | null) => void
  profileOverride?: MicFieldProfile
  onProfileChange?: (profile: MicFieldProfile) => void
  liveLevels?: MicLevelSnapshot | null
  effectiveSettings?: MicEffectiveSettings | null
  className?: string
}

export function VoiceMicSettingsPopover({
  voiceStatus,
  selectedDeviceId,
  onDeviceChange,
  profileOverride = "auto",
  onProfileChange,
  liveLevels,
  effectiveSettings,
  className,
}: Props) {
  const flags = voiceMicPhase1FlagsFromStatus(voiceStatus)
  const enabled = flags.micSelector || flags.micTelemetry || flags.agcV2
  const [devices, setDevices] = useState<MicDeviceOption[]>([])
  const [testing, setTesting] = useState(false)
  const [testLevels, setTestLevels] = useState<MicLevelSnapshot | null>(null)
  const testStreamRef = useRef<MediaStream | null>(null)
  const testRafRef = useRef<number | null>(null)

  useEffect(() => {
    if (!enabled || !flags.micSelector) return
    void listMicInputDevices().then(setDevices).catch(() => setDevices([]))
  }, [enabled, flags.micSelector])

  const stopTest = useCallback(() => {
    if (testRafRef.current != null) {
      cancelAnimationFrame(testRafRef.current)
      testRafRef.current = null
    }
    testStreamRef.current?.getTracks().forEach((t) => t.stop())
    testStreamRef.current = null
    setTesting(false)
  }, [])

  useEffect(() => () => stopTest(), [stopTest])

  const runTest = useCallback(async () => {
    stopTest()
    setTesting(true)
    setTestLevels(null)
    try {
      const { stream } = await acquireVoiceMicrophoneStream({
        flags,
        deviceId: selectedDeviceId ?? getStoredMicDeviceId(),
        profileOverride,
      })
      testStreamRef.current = stream
      const ctx = new AudioContext()
      await ctx.resume()
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      const data = new Float32Array(analyser.fftSize)
      const started = performance.now()
      const tick = () => {
        analyser.getFloatTimeDomainData(data)
        let sumSq = 0
        let peak = 0
        for (let i = 0; i < data.length; i++) {
          const s = data[i] ?? 0
          const a = Math.abs(s)
          if (a > peak) peak = a
          sumSq += s * s
        }
        const rms = Math.sqrt(sumSq / data.length)
        setTestLevels({
          rms: Math.round(rms * 1000) / 1000,
          peak: Math.round(peak * 1000) / 1000,
          noise_floor: 0,
          speech_rms: rms,
          snr: 0,
          clipping_pct: 0,
        })
        if (performance.now() - started < 4000) {
          testRafRef.current = requestAnimationFrame(tick)
        } else {
          stopTest()
          void ctx.close()
        }
      }
      testRafRef.current = requestAnimationFrame(tick)
    } catch {
      setTesting(false)
    }
  }, [flags, profileOverride, selectedDeviceId, stopTest])

  if (!enabled) return null

  const levels = liveLevels || testLevels

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className={cn("h-8 w-8 shrink-0 text-muted-foreground", className)}
          aria-label="Microphone settings"
        >
          <Settings2 className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-3 p-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Mic className="h-4 w-4" aria-hidden />
          Microphone
        </div>

        {flags.micSelector ? (
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Input device</label>
            <Select
              value={selectedDeviceId || getStoredMicDeviceId() || "default"}
              onValueChange={(v) => {
                const id = v === "default" ? null : v
                setStoredMicDeviceId(id)
                onDeviceChange?.(id)
              }}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Default microphone" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">System default</SelectItem>
                {devices.map((d) => (
                  <SelectItem key={d.deviceId} value={d.deviceId}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {flags.nearFarV1 ? (
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Mic context</label>
            <Select
              value={profileOverride}
              onValueChange={(v) => onProfileChange?.(v as MicFieldProfile)}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto detect</SelectItem>
                <SelectItem value="near_field">Headset / close mic</SelectItem>
                <SelectItem value="far_field">Laptop / room mic</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}

        {flags.micTelemetry ? (
          <div className="rounded-md border bg-muted/30 px-2 py-1.5 text-[11px] leading-relaxed text-muted-foreground">
            <div>RMS: {levels?.rms?.toFixed(3) ?? "—"}</div>
            <div>Peak: {levels?.peak?.toFixed(3) ?? "—"}</div>
            <div>SNR: {levels?.snr?.toFixed(1) ?? "—"}</div>
            <div>Clip: {levels?.clipping_pct?.toFixed(2) ?? "0"}%</div>
          </div>
        ) : null}

        {effectiveSettings ? (
          <div className="text-[10px] text-muted-foreground">
            AGC: {String(effectiveSettings.autoGainControl ?? "—")} · EC:{" "}
            {String(effectiveSettings.echoCancellation ?? "—")} · NS:{" "}
            {String(effectiveSettings.noiseSuppression ?? "—")}
          </div>
        ) : null}

        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="w-full"
          disabled={testing}
          onClick={() => void runTest()}
        >
          {testing ? "Testing…" : "Test microphone"}
        </Button>
      </PopoverContent>
    </Popover>
  )
}
