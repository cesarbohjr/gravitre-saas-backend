"use client"

import { useMemo, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import {
  ArrowUp,
  Lightning,
  Sparkle as Sparkles,
} from "@phosphor-icons/react"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import { AI_EXAMPLE_PROMPTS, AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"
import { VoiceInputButton } from "@/components/gravitre/assistant/voice-input-button"
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
      {/* Calm operator surface: neutral card, single restrained emerald accent.
          No blurred gradient orbs — they read as decoration and the composer is
          the only thing that should pull focus here. */}
      {/* Shape of AI — Initial CTA / Open input over the patterned chat surface */}
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
          <div
            className={cn(
              "rounded-[10px] border border-[color:var(--chat-surface-border,#dcd9d4)] bg-white p-2 shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors dark:bg-[#262626]",
              "focus-within:border-[#16a374]/50 focus-within:ring-2 focus-within:ring-[#16a374]/15",
            )}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={onKeyDown}
              rows={3}
              disabled={routing}
              placeholder={
                activeMode.id === "find"
                  ? "Find a run, workflow, agent, connector, or document…"
                  : activeMode.id === "execute"
                    ? "Describe the work to delegate — Gravitre will plan and run it…"
                    : activeMode.id === "chat"
                      ? "Ask a question or start a conversation…"
                      : "Ask, delegate, or search — results appear here…"
              }
              className="w-full min-h-[88px] resize-none bg-transparent px-3 py-3 text-left text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/70"
            />
            <div className="flex items-center justify-end gap-3 px-2 pb-1">
              <VoiceInputButton
                value={input}
                onChange={onInputChange}
                disabled={routing}
                onError={(message) => {
                  if (message) toast.error(message)
                }}
              />
              <button
                type="button"
                onClick={onSubmit}
                disabled={!input.trim() || routing}
                className={cn(
                  "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white shadow-sm transition-opacity disabled:cursor-not-allowed disabled:opacity-40",
                  "bg-[#16a374] hover:opacity-90",
                )}
                aria-label="Submit"
              >
                {routing ? (
                  <Sparkles className="h-4 w-4 animate-pulse" weight="fill" aria-hidden />
                ) : (
                  <ArrowUp className="h-4 w-4" weight="bold" aria-hidden />
                )}
              </button>
            </div>
          </div>

          <AnimatePresence>
            {routing ? (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-3 flex items-center justify-center gap-2 text-sm text-muted-foreground"
              >
                <Sparkles className="h-4 w-4 animate-pulse text-emerald-600 dark:text-emerald-400" weight="fill" aria-hidden />
                {routedMode ? (
                  <span>
                    Routing to <span className={cn("font-medium", routedMode.accent)}>{routedMode.badge}</span>…
                  </span>
                ) : (
                  <span>Reading your intent…</span>
                )}
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <div className="relative mt-5 flex flex-wrap justify-center gap-2">
          {AI_MODES.map((m) => {
            const isActive = m.id === mode
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => onModeChange(m.id)}
                aria-pressed={isActive}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-medium transition-all",
                  isActive
                    ? cn("ring-1", m.ring, "text-emerald-800 dark:text-emerald-200")
                    : "border-border/70 bg-background/60 text-muted-foreground hover:border-emerald-500/25 hover:text-foreground",
                )}
              >
                <ModeIconBadge modeId={m.id} />
                {m.label}
              </button>
            )
          })}
        </div>
      </section>

      {!routing ? (
        <div className="mt-6">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-wider text-[#16a374]">
            Try
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {AI_EXAMPLE_PROMPTS.map((example) => (
              <button
                key={example.text}
                type="button"
                onClick={() => {
                  if (onExampleSelect) {
                    onExampleSelect(example.text)
                    return
                  }
                  onInputChange(example.text)
                  inputRef.current?.focus()
                }}
                className="group inline-flex items-center gap-2 rounded-[10px] border border-[color:var(--chat-surface-border,#dcd9d4)] bg-white/85 px-3 py-2 text-left text-xs text-[color:var(--chat-surface-muted,#57534e)] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all hover:border-[#16a374]/40 hover:text-[#1c1917] dark:bg-[#262626]"
              >
                <ModeIconBadge modeId={example.hint} className="h-3.5 w-3.5 transition-colors group-hover:text-emerald-600 dark:group-hover:text-emerald-400" />
                <span className="max-w-[15rem] truncate">{example.text}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </motion.div>
  )
}
