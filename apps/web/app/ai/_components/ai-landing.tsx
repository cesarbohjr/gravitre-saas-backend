"use client"

import { useMemo, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import {
  ArrowUp,
  Lightning,
  Sparkle as Sparkles,
} from "@phosphor-icons/react"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import { AI_EXAMPLE_PROMPTS, AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"

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
}

export function AiLanding({
  mode,
  onModeChange,
  input,
  onInputChange,
  routing,
  routedTo,
  onSubmit,
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
    <div className="relative z-10 mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 py-10 md:px-6 md:py-16">
      <div className="text-center">
        <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Lightning className="h-3.5 w-3.5 text-primary" weight="fill" aria-hidden />
          One surface, three modes
        </div>
        <h1 className="text-balance text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
          What do you want to get done?
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-pretty text-sm leading-relaxed text-muted-foreground md:text-base">
          Ask a question, delegate a task, or search your workspace. In Auto mode, Gravitre routes
          your intent to the right engine automatically.
        </p>
      </div>

      <div className="mt-8">
        <div
          className={cn(
            "rounded-2xl border border-border bg-card p-2 shadow-sm transition-all",
            "focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20",
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
                    : "Describe what you need — Gravitre will route it to the right engine…"
            }
            className="w-full resize-none bg-transparent px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 disabled:opacity-60"
          />
          <div className="flex items-center justify-between gap-3 px-2 pb-1">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ModeIconBadge modeId={activeMode.id} className="h-3.5 w-3.5" />
              <span className="truncate">{activeMode.blurb}</span>
            </p>
            <button
              type="button"
              onClick={onSubmit}
              disabled={!input.trim() || routing}
              className={cn(
                "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-primary-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-40",
                "bg-primary hover:bg-primary/90",
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
              <Sparkles className="h-4 w-4 animate-pulse text-primary" weight="fill" aria-hidden />
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

      <div className="mt-4 flex flex-wrap justify-center gap-2">
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
                  ? cn("ring-1", m.ring, "text-foreground")
                  : "border-border bg-card/50 text-muted-foreground hover:border-foreground/20 hover:text-foreground",
              )}
            >
              <ModeIconBadge modeId={m.id} />
              {m.label}
            </button>
          )
        })}
      </div>

      {!routing ? (
        <div className="mt-6">
          <p className="mb-2 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Try
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {AI_EXAMPLE_PROMPTS.map((example) => (
              <button
                key={example.text}
                type="button"
                onClick={() => {
                  onInputChange(example.text)
                  inputRef.current?.focus()
                }}
                className="group inline-flex items-center gap-2 rounded-lg border border-border bg-card/50 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
              >
                <ModeIconBadge modeId={example.hint} className="h-3.5 w-3.5" />
                <span className="max-w-[15rem] truncate">{example.text}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
