"use client"

import { useMemo, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { Lightning, Sparkle as Sparkles } from "@phosphor-icons/react"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import { AI_EXAMPLE_PROMPTS, AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"
import { SharedChatComposerControls } from "@/components/gravitre/assistant/shared-chat-composer-controls"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"
import { toast } from "sonner"

function ModeIconBadge({
  modeId,
  className,
}: {
  modeId: ModeId
  className?: string
}) {
  const mode = getModeMeta(modeId)
  const Icon = mode.icon
  return <Icon className={cn("h-4 w-4", mode.accent, className)} weight="duotone" aria-hidden />
}

type AiLandingProps = {
  mode: ModeId
  onModeChange: (mode: ModeId) => void
  input: string
  onInputChange: (value: string) => void
  routing: boolean
  routedTo: AiEngine | null
  onSubmit: () => void
  /** Submit a TRY prompt immediately (do not only fill the composer). */
  onExampleSelect?: (text: string) => void
  modality: ChatModality
  onModalityChange: (next: ChatModality) => void
  voiceEntitled: boolean
  voiceUnavailableReason?: string
}

export function AiLanding({
  mode,
  onModeChange,
  input,
  onInputChange,
  routing,
  routedTo,
  onSubmit,
  onExampleSelect,
  modality,
  onModalityChange,
  voiceEntitled,
  voiceUnavailableReason,
}: AiLandingProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeMode = useMemo(() => getModeMeta(mode), [mode])
  const routedMode = routedTo ? getModeMeta(routedTo) : null

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    onSubmit()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="relative z-10 mx-auto flex w-full max-w-[920px] flex-col px-2 py-6 md:px-4"
    >
      <section className="relative p-4 sm:p-6">
        <div className="text-center">
          <div className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-[#16a374]/30 bg-white/70 px-3 py-1 text-xs font-medium uppercase tracking-wider text-[#16a374] dark:bg-[#262626]/80">
            <Lightning className="h-3.5 w-3.5" weight="fill" aria-hidden />
            One surface, three modes
          </div>
          <h1 className="text-balance text-3xl font-semibold tracking-tight text-[#1c1917] md:text-4xl dark:text-[#f2f2f0]">
            What do you want to get done?
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-pretty text-sm leading-relaxed text-[color:var(--chat-surface-muted,#57534e)] md:text-base">
            Ask a question, delegate a task, or search your workspace. In Auto mode, Gravitre routes
            your intent to the right engine automatically.
          </p>
        </div>

        <div className="relative mt-8">
          <SharedChatComposerControls
            modality={modality}
            onModalityChange={onModalityChange}
            voiceEntitled={voiceEntitled}
            unavailableReason={voiceUnavailableReason}
            input={input}
            onInputChange={onInputChange}
            inputRef={inputRef}
            onKeyDown={onKeyDown}
            disabled={routing}
            canSubmit={Boolean(input.trim()) && !routing}
            showSubmit
            onSubmit={onSubmit}
            textareaRows={3}
            placeholder={
              modality === "voice"
                ? "Speak or type — replies play aloud…"
                : activeMode.id === "find"
                  ? "Find a run, workflow, agent, connector, or document…"
                  : activeMode.id === "execute"
                    ? "Describe the work to delegate — Gravitre will plan and run it…"
                    : activeMode.id === "chat"
                      ? "Ask a question or start a conversation…"
                      : "Ask, delegate, or search — results appear here…"
            }
            textareaClassName="min-h-[88px] text-sm leading-relaxed"
            onVoiceInputError={(message) => {
              if (message) toast.error(message)
            }}
          />

          <AnimatePresence>
            {routing && routedMode ? (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-3 flex items-center justify-center gap-2 text-xs text-muted-foreground"
              >
                <Sparkles className="h-3.5 w-3.5 animate-pulse text-[#16a374]" weight="fill" />
                Routing to {routedMode.label}…
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {AI_MODES.map((item) => {
            const active = item.id === mode
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onModeChange(item.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? "border-[#16a374]/40 bg-[#16a374]/10 text-[#16a374]"
                    : "border-[color:var(--chat-surface-border)] bg-white/70 text-muted-foreground hover:text-foreground dark:bg-[#262626]/70",
                )}
              >
                <ModeIconBadge modeId={item.id} />
                {item.label}
              </button>
            )
          })}
        </div>

        <div className="mt-8 grid gap-2 sm:grid-cols-2">
          {AI_EXAMPLE_PROMPTS.map((prompt) => (
            <button
              key={prompt.text}
              type="button"
              onClick={() =>
                onExampleSelect ? onExampleSelect(prompt.text) : onInputChange(prompt.text)
              }
              className="rounded-xl border border-[color:var(--chat-surface-border)] bg-white/80 px-3 py-2.5 text-left text-xs text-muted-foreground transition-colors hover:border-[#16a374]/35 hover:text-foreground dark:bg-[#262626]/80"
            >
              {prompt.text}
            </button>
          ))}
        </div>
      </section>
    </motion.div>
  )
}
