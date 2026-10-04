"use client"

/**
 * Voice assignment for the CONFIGURE seat: preset library + Custom Voice Design v3.
 *
 * Library, preview and persistence paths are retained. Errors, pending state and
 * audio lifecycle are handled locally. Every request path (/api/voice/library,
 * /api/voice/preview, /api/voice/design, /api/voice/design/save), the
 * AgentVoiceProfile payload shape, and the value/onChange contract are unchanged.
 *
 * Seat gating is intentionally absent: the host (/agents/new) decides via
 * canConfigureVoice and renders short locked copy instead of this component, so
 * a Lite seat never sees a non-functional picker.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/fetcher"
import type { AgentVoiceProfile } from "@/types/api"
import { toast } from "sonner"
import { GravitreWave } from "@/components/gravitre/assistant/voice-presentation"
import { Check, ChevronRight, Loader2, Play, Sparkles } from "lucide-react"

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
    <span className="rounded-[4px] bg-[color:var(--g-surface-2)] px-1.5 py-px text-[11px] text-muted-foreground">
      {children}
    </span>
  )
}

export function AgentVoiceAssignment({
  value,
  onChange,
  department,
  className,
}: Props) {
  const mounted = useRef(true)
  const controlId = useId()
  const [libraryAttempt, setLibraryAttempt] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [libraryError, setLibraryError] = useState<string | null>(null)
  const [savingCustom, setSavingCustom] = useState<string | null>(null)
  const savingLock = useRef(false)
  const designLock = useRef(false)
  const playbackLock = useRef(false)
  const previewRequest = useRef<AbortController | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrl = useRef<string | null>(null)
  const [generatedDescription, setGeneratedDescription] = useState("")
  const [tab, setTab] = useState<"preset" | "custom">("preset")
  const [voices, setVoices] = useState<LibraryVoice[]>([])
  const [loading, setLoading] = useState(false)
  const [previewing, setPreviewing] = useState<string | null>(null)
  const [description, setDescription] = useState("")
  const [designBusy, setDesignBusy] = useState(false)
  const [previews, setPreviews] = useState<
    Array<{
      generated_voice_id: string
      audio_base_64?: string
      media_type?: string
    }>
  >([])
  // Which voices the operator has actually heard. Local presentation state only:
  // it drives the "preview first" affordance and is never sent anywhere.
  const [heard, setHeard] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setLibraryError(null)
      try {
        const res = await apiFetch("/api/voice/library", { timeoutMs: 20_000 })
        if (!res.ok) throw new Error("Could not load voice library")
        const data = (await res.json()) as { voices?: LibraryVoice[] }
        if (!cancelled) setVoices(data.voices || [])
      } catch (err) {
        if (!cancelled)
          setLibraryError(
            err instanceof Error ? err.message : "Could not load voice library",
          )
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [libraryAttempt])

  const stopAudio = useCallback(() => {
    previewRequest.current?.abort()
    previewRequest.current = null
    if (audioRef.current) {
      audioRef.current.onended = null
      audioRef.current.onerror = null
      audioRef.current.pause()
      audioRef.current = null
    }
    if (audioUrl.current) {
      URL.revokeObjectURL(audioUrl.current)
      audioUrl.current = null
    }
    playbackLock.current = false
  }, [])
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      stopAudio()
    }
  }, [stopAudio])
  const playAudio = useCallback(
    async (src: string, key: string, objectUrl = false) => {
      if (!mounted.current) {
        if (objectUrl) URL.revokeObjectURL(src)
        return
      }
      stopAudio()
      playbackLock.current = true
      setPreviewing(key)
      if (objectUrl) audioUrl.current = src
      const audio = new Audio(src)
      audioRef.current = audio
      audio.onended = () => {
        stopAudio()
        setPreviewing(null)
      }
      audio.onerror = () => {
        stopAudio()
        setPreviewing(null)
        setError("Could not play this preview")
      }
      try {
        await audio.play()
      } catch (err) {
        if (audioRef.current !== audio) return
        throw err
      }
      if (audioRef.current !== audio) return
      setHeard((prev) => (prev.includes(key) ? prev : [...prev, key]))
    },
    [stopAudio],
  )
  const previewVoice = useCallback(
    async (voiceId: string, model?: string) => {
      if (playbackLock.current) return
      playbackLock.current = true
      setPreviewing(voiceId)
      setError(null)
      const controller = new AbortController()
      previewRequest.current = controller
      try {
        const res = await apiFetch("/api/voice/preview", {
          method: "POST",
          headers: { "content-type": "application/json", accept: "audio/mpeg" },
          body: JSON.stringify({
            voice: voiceId,
            model: model || value.tts_model || "eleven_flash_v2_5",
          }),
          timeoutMs: 45_000,
          signal: controller.signal,
        })
        if (!res.ok)
          throw new Error(
            "Voice preview failed. Check voice access and credits, then retry.",
          )
        const blob = await res.blob()
        if (!mounted.current || controller.signal.aborted) return
        previewRequest.current = null
        await playAudio(URL.createObjectURL(blob), voiceId, true)
      } catch (err) {
        if (controller.signal.aborted) return
        stopAudio()
        setPreviewing(null)
        setError(err instanceof Error ? err.message : "Voice preview failed")
      }
    },
    [value.tts_model, playAudio, stopAudio],
  )

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
    if (designLock.current || savingLock.current) return
    if (!description.trim()) {
      toast.error("Describe the voice in plain English")
      return
    }
    designLock.current = true
    setError(null)
    const requestedDescription = description.trim()
    setDesignBusy(true)
    try {
      const res = await apiFetch("/api/voice/design", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          voice_description: requestedDescription,
          model_id: "eleven_ttv_v3",
          should_enhance: true,
        }),
        timeoutMs: 120_000,
      })
      if (!res.ok) {
        throw new Error(
          "Voice design failed. Check voice access and credits, then retry.",
        )
      }
      const data = (await res.json()) as { previews?: typeof previews }
      setPreviews(data.previews || [])
      setGeneratedDescription(requestedDescription)
      if (!data.previews?.length)
        setError(
          "No voice previews were returned. Try refining the description.",
        )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice design failed")
    } finally {
      designLock.current = false
      setDesignBusy(false)
    }
  }

  const saveCustom = async (generatedVoiceId: string) => {
    if (savingLock.current || designLock.current) return
    savingLock.current = true
    setSavingCustom(generatedVoiceId)
    setError(null)
    try {
      const res = await apiFetch("/api/voice/design/save", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          generated_voice_id: generatedVoiceId,
          name: `Custom ${department || "agent"} voice`,
          description: generatedDescription,
        }),
        timeoutMs: 60_000,
      })
      if (!res.ok) throw new Error("Could not save custom voice")
      const data = (await res.json()) as { voice_id?: string }
      if (!data.voice_id) throw new Error("Save returned no voice ID")
      onChange({
        ...value,
        voice_source: "custom_voice_v3",
        voice_id: data.voice_id,
        voice_key: data.voice_id,
        tts_model: "eleven_flash_v2_5",
        turn_sensitivity: value.turn_sensitivity || "normal",
      })
      toast.success(
        "Voice saved to the library. Save personality to assign it to this agent.",
      )
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not save custom voice",
      )
    } finally {
      savingLock.current = false
      setSavingCustom(null)
    }
  }

  const isCustom = value.voice_source === "custom_voice_v3"
  // Human-readable identity for the footer. The raw voice_id stays out of the UI
  // — it is an ElevenLabs handle, not information an operator can act on.
  const selectedName = useMemo(() => {
    if (!value.voice_id) return null
    if (isCustom) return `Custom ${department || "agent"} voice`
    return (
      voices.find((v) => v.voice_id === value.voice_id)?.name ??
      "Selected voice"
    )
  }, [value.voice_id, isCustom, department, voices])
  const selectedHeard = value.voice_id ? heard.includes(value.voice_id) : false

  return (
    <div className={cn("space-y-4", className)}>
      {/* Equal-weight paths: one segmented control, two same-width halves, so
          Custom never reads as a buried advanced toggle. */}
      <div className="inline-grid w-full grid-cols-2 gap-0.5 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] p-0.5 sm:w-auto">
        {(["preset", "custom"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            aria-pressed={tab === t}
            className={cn(
              "flex min-h-11 items-center justify-center gap-1.5 rounded-[6px] px-3 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              tab === t
                ? "bg-background text-foreground shadow-[0_0_0_1px_var(--g-border-default)]"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t === "custom" ? <Sparkles className="size-3.5" /> : null}
            {t === "preset" ? "Voice library" : "Design a voice"}
          </button>
        ))}
      </div>

      {previewing ? (
        <Button
          className="min-h-11"
          variant="outline"
          onClick={() => {
            stopAudio()
            setPreviewing(null)
          }}
        >
          Stop preview
        </Button>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      <div>
        {tab === "preset" ? (
          <div className="space-y-4">
            {loading ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" />{" "}
                Loading library…
              </div>
            ) : (
              <div className="space-y-3">
                {libraryError ? (
                  <div>
                    <p role="alert" className="text-sm text-destructive">
                      {libraryError}
                    </p>
                    <Button
                      className="min-h-11 mt-2"
                      variant="outline"
                      onClick={() => setLibraryAttempt(libraryAttempt + 1)}
                    >
                      Retry voice library
                    </Button>
                  </div>
                ) : null}
                {!libraryError && !voices.length ? (
                  <p className="text-sm text-muted-foreground">
                    No library voices returned.
                  </p>
                ) : null}
                <div className="grid max-h-80 gap-2 overflow-y-auto pr-0.5 sm:grid-cols-2">
                  {voices.map((v) => {
                    const selected = value.voice_id === v.voice_id
                    const isPreviewing = previewing === v.voice_id
                    return (
                      <div
                        key={v.voice_id}
                        className={cn(
                          "flex items-start gap-2 rounded-[var(--np-radius-md)] border p-3 transition-colors",
                          selected
                            ? "border-foreground bg-[color:var(--g-surface-1)]"
                            : "border-[color:var(--g-border-default)] hover:border-[color:var(--g-border-strong)] hover:bg-[color:var(--g-surface-1)]",
                        )}
                      >
                        <button
                          type="button"
                          className="min-h-11 min-w-0 flex-1 rounded-[4px] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={() => selectPreset(v)}
                          aria-pressed={selected}
                        >
                          <span className="flex items-center gap-1.5">
                            {selected ? (
                              <Check
                                className="size-3.5 shrink-0 text-foreground"
                                aria-hidden
                              />
                            ) : null}
                            <span className="truncate text-[13px] font-medium text-foreground">
                              {v.name}
                            </span>
                          </span>
                          <span className="mt-0.5 block line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                            {v.personality?.descriptor ||
                              "Shared library voice"}
                          </span>
                          {v.personality?.tone || v.personality?.energy ? (
                            <span className="mt-1.5 flex flex-wrap gap-1">
                              {v.personality?.tone ? (
                                <Trait>{v.personality.tone}</Trait>
                              ) : null}
                              {v.personality?.energy ? (
                                <Trait>{v.personality.energy}</Trait>
                              ) : null}
                            </span>
                          ) : null}
                        </button>
                        <Button
                          type="button"
                          size="icon-sm"
                          variant="outline"
                          className={cn(
                            "min-h-11 min-w-11 shrink-0 rounded-full",
                            isPreviewing && "border-foreground",
                          )}
                          disabled={Boolean(previewing)}
                          onClick={() => previewVoice(v.voice_id)}
                          aria-label={`Preview ${v.name}`}
                        >
                          {isPreviewing ? (
                            // Decorative: the same waveform motif as the chat
                            // presence, standing in for a spinner while audio plays.
                            <GravitreWave speaker="agent" compact />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Secondary controls: smaller labels, quiet surface, placed after the
                voice choice so they never outrank it. */}
            <details className="group">
              <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1 rounded-[4px] text-[13px] font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
                <ChevronRight
                  className="size-3.5 transition-transform group-open:rotate-90"
                  aria-hidden
                />
                Advanced
              </summary>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <Label
                    htmlFor={`${controlId}-model`}
                    className="text-xs font-medium text-muted-foreground"
                  >
                    Speech model
                  </Label>
                  <select
                    className="mt-1 min-h-11 w-full rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-background px-2 text-[13px] text-foreground hover:border-[color:var(--g-border-strong)]"
                    id={`${controlId}-model`}
                    value={value.tts_model || "eleven_flash_v2_5"}
                    onChange={(e) =>
                      onChange({ ...value, tts_model: e.target.value })
                    }
                  >
                    <option value="eleven_flash_v2_5">Flash v2.5</option>
                    <option value="eleven_v3">Eleven v3</option>
                    <option value="eleven_multilingual_v2">
                      Multilingual v2
                    </option>
                  </select>
                </div>
                <div>
                  <Label
                    htmlFor={`${controlId}-turn`}
                    className="text-xs font-medium text-muted-foreground"
                  >
                    Turn-taking
                  </Label>
                  <select
                    className="mt-1 min-h-11 w-full rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-background px-2 text-[13px] text-foreground hover:border-[color:var(--g-border-strong)]"
                    id={`${controlId}-turn`}
                    value={value.turn_sensitivity || "normal"}
                    onChange={(e) =>
                      onChange({
                        ...value,
                        turn_sensitivity: e.target
                          .value as AgentVoiceProfile["turn_sensitivity"],
                      })
                    }
                  >
                    <option value="eager">Eager</option>
                    <option value="normal">Normal (default)</option>
                    <option value="patient">Patient</option>
                  </select>
                </div>
              </div>
            </details>
          </div>
        ) : (
          // Custom Voice Design keeps its shipped order: describe → generate →
          // listen → save. The steps are numbered so the order is legible.
          <div className="space-y-4">
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-[11px] font-medium tabular-nums text-muted-foreground">
                  01
                </span>
                <Label
                  htmlFor={`${controlId}-description`}
                  className="text-xs font-medium"
                >
                  Describe the voice
                </Label>
              </div>
              <Textarea
                id={`${controlId}-description`}
                disabled={designBusy || Boolean(savingCustom)}
                className="mt-1.5 text-sm"
                rows={3}
                placeholder="A calm American woman in her 30s, clear and direct…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="flex items-baseline gap-2">
              <span className="text-[11px] font-medium tabular-nums text-muted-foreground">
                02
              </span>
              <Button
                type="button"
                size="sm"
                className="min-h-11"
                disabled={
                  designBusy || Boolean(savingCustom) || !description.trim()
                }
                onClick={runDesign}
              >
                {designBusy ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
                ) : null}
                Generate previews
              </Button>
            </div>

            {previews.length > 0 ? (
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-[11px] font-medium tabular-nums text-muted-foreground">
                    03
                  </span>
                  <Label className="text-xs font-medium">
                    Listen, then save one
                  </Label>
                </div>
                <div className="mt-1.5 grid gap-2">
                  {previews.map((p, i) => {
                    const listened = heard.includes(p.generated_voice_id)
                    return (
                      <div
                        key={p.generated_voice_id}
                        className="flex flex-wrap items-center gap-3 rounded-lg border border-border/60 bg-muted/20 p-2.5"
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
                              className="min-h-11 gap-1.5 px-2"
                              disabled={Boolean(previewing)}
                              onClick={() => {
                                if (playbackLock.current) return
                                void playAudio(
                                  `data:${p.media_type || "audio/mpeg"};base64,${p.audio_base_64}`,
                                  p.generated_voice_id,
                                ).catch(() => {
                                  stopAudio()
                                  setPreviewing(null)
                                  setError("Could not play this preview")
                                })
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
                            className="min-h-11"
                            disabled={Boolean(savingCustom) || designBusy}
                            onClick={() =>
                              void saveCustom(p.generated_voice_id)
                            }
                          >
                            {savingCustom === p.generated_voice_id
                              ? "Saving…"
                              : "Save to library"}
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
      <div
        aria-live="polite"
        className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-1)] px-3 py-2.5"
      >
        {value.voice_id ? (
          <>
            {selectedHeard ? (
              <Check
                className="size-3.5 shrink-0 text-foreground"
                aria-hidden
              />
            ) : null}
            <span className="text-xs text-muted-foreground">Selected</span>
            <span className="text-[13px] font-medium text-foreground">
              {selectedName}
            </span>
            <Trait>{isCustom ? "Custom" : "Preset"}</Trait>
            {selectedHeard ? (
              <span className="text-xs text-muted-foreground">Previewed</span>
            ) : (
              <>
                <span className="text-xs text-muted-foreground">
                  Preview before confirming
                </span>
                <button
                  type="button"
                  disabled={Boolean(previewing)}
                  className="inline-flex min-h-11 items-center text-xs font-medium text-foreground underline underline-offset-2"
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
