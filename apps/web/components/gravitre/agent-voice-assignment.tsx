"use client"

/**
 * Voice assignment for the CONFIGURE seat: preset library + Custom Voice Design v3.
 *
 * This pass is presentation only. Every request path (/api/voice/library,
 * /api/voice/preview, /api/voice/design, /api/voice/design/save), the
 * AgentVoiceProfile payload shape, and the value/onChange contract are unchanged
 * — only layout, hierarchy, and the preview affordance were reworked.
 *
 * Seat gating is intentionally absent: the host (/agents/new) decides via
 * canConfigureVoice and renders short locked copy instead of this component, so
 * a Lite seat never sees a non-functional picker.
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/fetcher"
import type { AgentVoiceProfile } from "@/types/api"
import { toast } from "sonner"
import { useReducedMotion } from "framer-motion"
import { VoiceWaveform } from "@/components/gravitre/assistant/voice-session-presence"
import { Check, Loader2, Play, Sparkles } from "lucide-react"

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

/** Quiet metadata chip for tone / energy. Never competes with the voice name. */
function Trait({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded border border-border/60 bg-muted/40 px-1.5 py-px text-[10px] uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  )
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
  // Which voices the operator has actually heard. Local presentation state only:
  // it drives the "preview first" affordance and is never sent anywhere.
  const [heard, setHeard] = useState<string[]>([])
  const reduceMotion = useReducedMotion()

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
      setHeard((prev) => (prev.includes(voiceId) ? prev : [...prev, voiceId]))
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

  const isCustom = value.voice_source === "custom_voice_v3"
  // Human-readable identity for the footer. The raw voice_id stays out of the UI
  // — it is an ElevenLabs handle, not information an operator can act on.
  const selectedName = useMemo(() => {
    if (!value.voice_id) return null
    if (isCustom) return `Custom ${department || "agent"} voice`
    return voices.find((v) => v.voice_id === value.voice_id)?.name ?? "Selected voice"
  }, [value.voice_id, isCustom, department, voices])
  const selectedHeard = value.voice_id ? heard.includes(value.voice_id) : false

  return (
    <div className={cn("rounded-lg border border-border bg-card", className)}>
      <div className="border-b border-border/70 px-4 py-3">
        <Label className="text-sm font-medium">Voice</Label>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
          Pick a library voice or design a custom one. Both are full paths — listen
          before you confirm.
        </p>
      </div>

      {/* Equal-weight paths: one segmented control, two same-width halves, so
          Custom never reads as a buried advanced toggle. */}
      <div className="px-4 pt-3">
        <div className="grid grid-cols-2 gap-0.5 rounded-lg border border-border/70 bg-muted/40 p-0.5">
          {(["preset", "custom"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={cn(
                "flex h-8 items-center justify-center gap-1.5 rounded-md text-xs font-medium transition-colors",
                tab === t
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t === "custom" ? <Sparkles className="h-3.5 w-3.5" /> : null}
              {t === "preset" ? "Preset library" : "Custom voice"}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        {tab === "preset" ? (
          <div className="space-y-4">
            {loading ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading library…
              </div>
            ) : (
              <div className="grid max-h-72 gap-2 overflow-y-auto pr-0.5 sm:grid-cols-2">
                {voices.map((v) => {
                  const selected = value.voice_id === v.voice_id
                  const isPreviewing = previewing === v.voice_id
                  return (
                    <div
                      key={v.voice_id}
                      className={cn(
                        "flex items-start gap-2 rounded-lg border p-3 transition-colors",
                        selected
                          ? "border-success/40 bg-success/[0.05]"
                          : "border-border/60 hover:border-border hover:bg-muted/30",
                      )}
                    >
                      <button
                        type="button"
                        className="min-w-0 flex-1 text-left"
                        onClick={() => selectPreset(v)}
                        aria-pressed={selected}
                      >
                        <span className="flex items-center gap-1.5">
                          {selected ? (
                            <Check className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
                          ) : null}
                          <span className="truncate text-sm font-medium text-foreground">
                            {v.name}
                          </span>
                        </span>
                        <span className="mt-0.5 block line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                          {v.personality?.descriptor || "Shared library voice"}
                        </span>
                        {v.personality?.tone || v.personality?.energy ? (
                          <span className="mt-1.5 flex flex-wrap gap-1">
                            {v.personality?.tone ? <Trait>{v.personality.tone}</Trait> : null}
                            {v.personality?.energy ? <Trait>{v.personality.energy}</Trait> : null}
                          </span>
                        ) : null}
                      </button>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className={cn("h-8 w-8 shrink-0", isPreviewing && "text-success")}
                        disabled={isPreviewing}
                        onClick={() => previewVoice(v.voice_id)}
                        aria-label={`Preview ${v.name}`}
                      >
                        {isPreviewing ? (
                          // Decorative: the same waveform motif as the chat
                          // presence, standing in for a spinner while audio plays.
                          <VoiceWaveform active travelling reduceMotion={reduceMotion} />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Secondary controls: smaller labels, quiet surface, placed after the
                voice choice so they never outrank it. */}
            <div className="grid gap-3 border-t border-border/60 pt-3 sm:grid-cols-2">
              <div>
                <Label className="text-[11px] font-normal uppercase tracking-wide text-muted-foreground">
                  TTS model
                </Label>
                <select
                  className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs text-foreground"
                  value={value.tts_model || "eleven_flash_v2_5"}
                  onChange={(e) => onChange({ ...value, tts_model: e.target.value })}
                >
                  <option value="eleven_flash_v2_5">Flash v2.5</option>
                  <option value="eleven_v3">Eleven v3</option>
                  <option value="eleven_multilingual_v2">Multilingual v2</option>
                </select>
              </div>
              <div>
                <Label className="text-[11px] font-normal uppercase tracking-wide text-muted-foreground">
                  Turn-taking
                </Label>
                <select
                  className="mt-1 h-8 w-full rounded-md border border-border/70 bg-background px-2 text-xs text-foreground"
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
          // Custom Voice Design keeps its shipped order: describe → generate →
          // listen → save. The steps are numbered so the order is legible.
          <div className="space-y-4">
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-[11px] font-medium tabular-nums text-muted-foreground">01</span>
                <Label className="text-xs font-medium">Describe the voice</Label>
              </div>
              <Textarea
                className="mt-1.5 text-sm"
                rows={3}
                placeholder="A calm American woman in her 30s, clear and direct…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="flex items-baseline gap-2">
              <span className="text-[11px] font-medium tabular-nums text-muted-foreground">02</span>
              <Button type="button" size="sm" className="h-8" disabled={designBusy} onClick={runDesign}>
                {designBusy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
                Generate previews
              </Button>
            </div>

            {previews.length > 0 ? (
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-[11px] font-medium tabular-nums text-muted-foreground">03</span>
                  <Label className="text-xs font-medium">Listen, then save one</Label>
                </div>
                <div className="mt-1.5 grid gap-2">
                  {previews.map((p, i) => {
                    const listened = heard.includes(p.generated_voice_id)
                    return (
                      <div
                        key={p.generated_voice_id}
                        className="flex items-center gap-3 rounded-lg border border-border/60 bg-muted/20 p-2.5"
                      >
                        {/* Take N, not the raw generated_voice_id. */}
                        <span className="shrink-0 text-xs font-medium text-muted-foreground">
                          Take {i + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                          {listened ? "Previewed" : "Not previewed yet"}
                        </span>
                        <div className="flex shrink-0 items-center gap-1">
                          {p.audio_base_64 ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-8 gap-1.5 px-2"
                              onClick={() => {
                                const src = `data:${p.media_type || "audio/mpeg"};base64,${p.audio_base_64}`
                                void new Audio(src).play()
                                setHeard((prev) =>
                                  prev.includes(p.generated_voice_id)
                                    ? prev
                                    : [...prev, p.generated_voice_id],
                                )
                              }}
                            >
                              <Play className="h-3.5 w-3.5" />
                              Listen
                            </Button>
                          ) : null}
                          <Button
                            type="button"
                            size="sm"
                            variant={listened ? "default" : "outline"}
                            className="h-8"
                            onClick={() => saveCustom(p.generated_voice_id)}
                          >
                            Save
                          </Button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Footer: human identity + source, plus the calm preview requirement. */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border/70 bg-muted/20 px-4 py-2.5">
        {value.voice_id ? (
          <>
            {selectedHeard ? (
              <Check className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
            ) : null}
            <span className="text-xs font-medium text-foreground">{selectedName}</span>
            <Trait>{isCustom ? "Custom" : "Preset"}</Trait>
            {selectedHeard ? (
              <span className="text-xs text-muted-foreground">Previewed</span>
            ) : (
              <>
                <span className="text-xs text-muted-foreground">Preview before confirming</span>
                <button
                  type="button"
                  className="text-xs font-medium text-foreground underline underline-offset-2"
                  onClick={() => previewVoice(value.voice_id!)}
                >
                  Play
                </button>
              </>
            )}
          </>
        ) : (
          <span className="text-xs text-muted-foreground">
            No voice selected yet — pick one above and listen before confirming.
          </span>
        )}
      </div>
    </div>
  )
}
