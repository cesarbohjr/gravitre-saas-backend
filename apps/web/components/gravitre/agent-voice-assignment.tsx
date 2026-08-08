"use client"

/**
 * Functional voice assignment: preset library + Custom Voice Design v3.
 * Visual polish (waveform, card styling) is deferred to the v0 handoff.
 */

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/fetcher"
import type { AgentVoiceProfile } from "@/types/api"
import { toast } from "sonner"
import { Loader2, Play } from "lucide-react"

type LibraryVoice = {
  voice_id: string
  key: string
  name: string
  personality?: { descriptor?: string; tone?: string; energy?: string }
  categories?: string[]
  models?: string[]
  languages?: string[]
}

type Props = {
  value: AgentVoiceProfile
  onChange: (profile: AgentVoiceProfile) => void
  department?: string
  className?: string
}

export function AgentVoiceAssignment({ value, onChange, department, className }: Props) {
  const [tab, setTab] = useState<"preset" | "custom">("preset")
  const [voices, setVoices] = useState<LibraryVoice[]>([])
  const [loading, setLoading] = useState(false)
  const [previewing, setPreviewing] = useState<string | null>(null)
  const [description, setDescription] = useState("")
  const [designBusy, setDesignBusy] = useState(false)
  const [previews, setPreviews] = useState<
    Array<{ generated_voice_id: string; audio_base_64?: string; media_type?: string }>
  >([])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const res = await apiFetch("/api/voice/library", { timeoutMs: 20_000 })
        if (!res.ok) return
        const data = (await res.json()) as { voices?: LibraryVoice[] }
        if (!cancelled) setVoices(data.voices || [])
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const previewVoice = useCallback(async (voiceId: string, model?: string) => {
    setPreviewing(voiceId)
    try {
      const res = await apiFetch("/api/voice/preview", {
        method: "POST",
        headers: { "content-type": "application/json", accept: "audio/mpeg" },
        body: JSON.stringify({
          voice: voiceId,
          model: model || value.tts_model || "eleven_flash_v2_5",
        }),
        timeoutMs: 45_000,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        toast.error(
          typeof err?.detail === "object"
            ? err.detail.detail || "Preview failed"
            : "Preview failed — check voice billing/credits",
        )
        return
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      await audio.play()
      audio.onended = () => URL.revokeObjectURL(url)
    } finally {
      setPreviewing(null)
    }
  }, [value.tts_model])

  const selectPreset = (v: LibraryVoice) => {
    onChange({
      ...value,
      voice_source: "preset_library",
      voice_id: v.voice_id,
      voice_key: v.key,
      tts_model: value.tts_model || "eleven_flash_v2_5",
      personality_attributes: {
        descriptor: v.personality?.descriptor || "",
        tone: v.personality?.tone || "",
        energy: v.personality?.energy || "",
      },
      language: (v.languages || ["en"])[0],
      turn_sensitivity: value.turn_sensitivity || "normal",
    })
  }

  const runDesign = async () => {
    if (!description.trim()) {
      toast.error("Describe the voice in plain English")
      return
    }
    setDesignBusy(true)
    try {
      const res = await apiFetch("/api/voice/design", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          voice_description: description.trim(),
          model_id: "eleven_ttv_v3",
          should_enhance: true,
        }),
        timeoutMs: 120_000,
      })
      if (!res.ok) {
        toast.error("Voice Design failed — check ElevenLabs credits")
        return
      }
      const data = (await res.json()) as { previews?: typeof previews }
      setPreviews(data.previews || [])
      toast.success("Previews ready — listen, then save")
    } finally {
      setDesignBusy(false)
    }
  }

  const saveCustom = async (generatedVoiceId: string) => {
    const name = `Custom ${department || "agent"} voice`
    const res = await apiFetch("/api/voice/design/save", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        generated_voice_id: generatedVoiceId,
        name,
        description: description.trim(),
      }),
      timeoutMs: 60_000,
    })
    if (!res.ok) {
      toast.error("Could not save custom voice")
      return
    }
    const data = (await res.json()) as { voice_id?: string }
    if (!data.voice_id) {
      toast.error("Save returned no voice id")
      return
    }
    onChange({
      ...value,
      voice_source: "custom_voice_v3",
      voice_id: data.voice_id,
      voice_key: data.voice_id,
      tts_model: "eleven_flash_v2_5",
      turn_sensitivity: value.turn_sensitivity || "normal",
    })
    toast.success("Custom voice saved — reusable across agents in this org")
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div>
        <Label className="text-sm font-medium">Voice</Label>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Preset library is the fast path. Custom Voice (Design v3) is a full equal path.
          Live preview is required before confirming.
        </p>
      </div>
      <div className="inline-flex rounded-lg border border-border/70 p-0.5">
        <Button
          type="button"
          size="sm"
          variant={tab === "preset" ? "secondary" : "ghost"}
          onClick={() => setTab("preset")}
        >
          Preset library
        </Button>
        <Button
          type="button"
          size="sm"
          variant={tab === "custom" ? "secondary" : "ghost"}
          onClick={() => setTab("custom")}
        >
          Custom Voice
        </Button>
      </div>

      {tab === "preset" ? (
        <div className="space-y-2">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading library…
            </div>
          ) : (
            <div className="grid max-h-64 gap-2 overflow-y-auto sm:grid-cols-2">
              {voices.map((v) => {
                const selected = value.voice_id === v.voice_id
                return (
                  <div
                    key={v.voice_id}
                    className={cn(
                      "flex items-start justify-between gap-2 rounded-lg border p-3 text-left",
                      selected ? "border-foreground/40 bg-muted/50" : "border-border/60",
                    )}
                  >
                    <button type="button" className="min-w-0 flex-1 text-left" onClick={() => selectPreset(v)}>
                      <p className="truncate text-sm font-medium">{v.name}</p>
                      <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                        {v.personality?.descriptor || "Shared library voice"}
                      </p>
                    </button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 shrink-0"
                      disabled={previewing === v.voice_id}
                      onClick={() => previewVoice(v.voice_id)}
                      aria-label={`Preview ${v.name}`}
                    >
                      {previewing === v.voice_id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>
                )
              })}
            </div>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <Label className="text-xs">TTS model</Label>
              <select
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                value={value.tts_model || "eleven_flash_v2_5"}
                onChange={(e) => onChange({ ...value, tts_model: e.target.value })}
              >
                <option value="eleven_flash_v2_5">Flash v2.5</option>
                <option value="eleven_v3">Eleven v3</option>
                <option value="eleven_multilingual_v2">Multilingual v2</option>
              </select>
            </div>
            <div>
              <Label className="text-xs">Turn-taking</Label>
              <select
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                value={value.turn_sensitivity || "normal"}
                onChange={(e) =>
                  onChange({
                    ...value,
                    turn_sensitivity: e.target.value as AgentVoiceProfile["turn_sensitivity"],
                  })
                }
              >
                <option value="eager">Eager</option>
                <option value="normal">Normal (default)</option>
                <option value="patient">Patient</option>
              </select>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <Label className="text-xs">Describe the voice</Label>
            <Textarea
              className="mt-1"
              rows={3}
              placeholder="A calm American woman in her 30s, clear and direct…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <Button type="button" size="sm" disabled={designBusy} onClick={runDesign}>
            {designBusy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
            Generate previews
          </Button>
          {previews.length > 0 ? (
            <div className="space-y-2">
              {previews.map((p) => (
                <div
                  key={p.generated_voice_id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border/60 p-2"
                >
                  <Input readOnly value={p.generated_voice_id} className="h-8 text-xs" />
                  <div className="flex gap-1">
                    {p.audio_base_64 ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          const src = `data:${p.media_type || "audio/mpeg"};base64,${p.audio_base_64}`
                          void new Audio(src).play()
                        }}
                      >
                        <Play className="h-3.5 w-3.5" />
                      </Button>
                    ) : null}
                    <Button type="button" size="sm" onClick={() => saveCustom(p.generated_voice_id)}>
                      Save
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {value.voice_id ? (
        <p className="text-xs text-muted-foreground">
          Selected: {value.voice_source || "preset"} · {value.voice_id}
          {" · "}
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => previewVoice(value.voice_id!)}
          >
            Preview again
          </button>
        </p>
      ) : (
        <p className="text-xs text-warning">Select and preview a voice before creating the agent.</p>
      )}
    </div>
  )
}
