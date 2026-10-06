"use client"

import type { ReactNode, RefObject } from "react"
import useSWR from "swr"
import { ArrowUpRight, ShieldCheck } from "lucide-react"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useOptionalGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { routeContextLabel } from "@/components/gravitre/ai-helper"
import { MISSION_STAGE_ORDER } from "./ai-mission-spine"

type Starter = { text: string; hint: string }

const BASE_STARTERS: Starter[] = [
  { text: "What changed in my workspace since yesterday?", hint: "Briefing" },
  { text: "Find failed workflow runs from the last 24 hours", hint: "Runs" },
  { text: "Summarize our pipeline health and flag stale deals", hint: "Pipeline" },
  { text: "Which agents are busiest this week?", hint: "Workforce" },
]

/**
 * One source for what Gravitre knows before the first message, shared by every
 * presentation so a compact window and fullscreen never suggest different things.
 */
export function useAiStarters(
  limit: number,
  onInputChange: (value: string) => void,
  inputRef?: RefObject<HTMLTextAreaElement | null>,
) {
  const workspace = useOptionalGravitreAIWorkspace()
  const selected = workspace?.pageContext.selected ?? null
  const originPath = workspace?.pageContext.pathname
  const origin = originPath && !originPath.startsWith("/ai") ? routeContextLabel(originPath) : null
  const { data: approvals } = useSWR<{ approvals?: Array<{ status?: string }> }>("/api/approvals", apiFetcher, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
  const pending = approvals?.approvals?.filter((a) => a.status === "pending").length ?? 0

  const starters: Starter[] = [
    ...(selected ? [{ text: `Tell me what matters about ${selected.label}`, hint: "In context" }] : []),
    ...(pending > 0 ? [{ text: "What should I approve first, and why?", hint: "Approvals" }] : []),
    ...BASE_STARTERS,
  ].slice(0, limit)

  const stage = (text: string) => {
    onInputChange(text)
    requestAnimationFrame(() => inputRef?.current?.focus())
  }

  return { starters, selected, origin, pending, stage }
}

/**
 * Empty state for the windowed presentations (compact, floating, docked).
 * Sits directly above the composer so context, scope and suggestions read as
 * one unit with the input instead of a hero the eye has to travel down from.
 */
export function AiCompactStart({
  onInputChange,
  inputRef,
}: {
  onInputChange: (value: string) => void
  inputRef?: RefObject<HTMLTextAreaElement | null>
}) {
  const { starters, selected, origin, pending, stage } = useAiStarters(3, onInputChange, inputRef)
  const where = selected?.label ?? origin

  return (
    <div className="flex min-h-full flex-col justify-end gap-4 px-1 pb-1 pt-4" data-gravitre-ai-compact-start="">
      <div className="flex flex-col gap-1.5">
        <p className="flex min-w-0 items-center gap-1.5 text-xs font-medium text-[color:var(--g-text-muted)]">
          <span className="size-1.5 shrink-0 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
          <span className="truncate">{where ? `Working with ${where}` : "Across your workspace"}</span>
        </p>
        <h2 className="text-pretty text-base font-semibold leading-snug tracking-[-0.01em] text-[color:var(--g-text-primary)]">
          {where ? "Ask about this, or hand off the next step." : "What do you want to get done?"}
        </h2>
        <p className="flex items-center gap-1.5 text-xs leading-relaxed text-[color:var(--g-text-muted)]">
          <ShieldCheck className="size-3.5 shrink-0 text-[color:var(--g-signal)]" aria-hidden />
          {pending > 0
            ? `${pending} waiting for your approval. Nothing changes without it.`
            : "Reads what you can see. Asks before changing anything."}
        </p>
      </div>
      <ul className="flex flex-col gap-1" aria-label="Suggested requests">
        {starters.map((starter) => (
          <li key={starter.text}>
            <button
              type="button"
              onClick={() => stage(starter.text)}
              className="group flex w-full items-center gap-3 rounded-[var(--np-radius-sm)] border border-[color:var(--g-border-subtle)] px-3 py-2 text-left transition-colors hover:border-[color:var(--g-border-default)] hover:bg-[color:var(--g-background-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[11px] font-medium text-[color:var(--g-text-muted)]">{starter.hint}</span>
                <span className="block text-sm leading-snug text-[color:var(--g-text-primary)]">{starter.text}</span>
              </span>
              <ArrowUpRight
                className="size-4 shrink-0 text-[color:var(--g-text-muted)] transition-colors group-hover:text-[color:var(--g-text-primary)]"
                aria-hidden
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * First view of an empty conversation: identity, the context Gravitre will use,
 * and starter prompts staged into the composer (never auto-sent).
 */
export function AiStartingState({
  onInputChange,
  inputRef,
  composer,
}: {
  onInputChange: (value: string) => void
  inputRef?: RefObject<HTMLTextAreaElement | null>
  /** The live composer, placed under the objective prompt while the conversation is empty. */
  composer?: ReactNode
}) {
  const { starters, selected, origin, pending, stage } = useAiStarters(4, onInputChange, inputRef)
  const where = selected?.label ?? origin

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col px-2 pb-6 pt-[6vh]" data-gravitre-ai-start="">
      <div className="min-w-0">
        <p className="mb-4 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-[13px] font-medium text-[color:var(--g-text-muted)]">
          <span className="inline-flex min-w-0 items-center gap-2 text-[color:var(--g-text-primary)]">
            <span className="size-1.5 shrink-0 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
            <span className="truncate">{where ? `Working with ${where}` : "Across your workspace"}</span>
          </span>
          {pending > 0 ? (
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="size-3.5 text-[color:var(--g-signal)]" aria-hidden />
              <span>
                <span className="tabular-nums">{pending}</span> waiting for your approval
              </span>
            </span>
          ) : null}
        </p>
        <h2 className="text-balance text-[26px] font-semibold leading-[1.1] tracking-[-0.03em] text-[color:var(--g-text-primary)] sm:text-[32px]">
          What do you want to get done?
        </h2>
        <p className="mt-2 max-w-[560px] text-[14px] leading-relaxed text-[color:var(--g-text-secondary)]">
          State the outcome. Gravitre plans it, works through your connected systems, and waits for your approval before changing anything.
        </p>

        {composer ? <div className="mt-6">{composer}</div> : null}

        <ul
          className="mt-6 divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-default)]"
          aria-label="Suggested requests"
        >
          {starters.map((starter) => (
            <li key={starter.text}>
              <button
                type="button"
                onClick={() => stage(starter.text)}
                className="group flex w-full items-center gap-4 px-1 py-2.5 text-left transition-colors hover:bg-[color:var(--g-background-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <span className="w-[84px] shrink-0 text-xs font-medium text-[color:var(--g-text-muted)]">{starter.hint}</span>
                <span className="min-w-0 flex-1 text-sm font-medium leading-snug text-[color:var(--g-text-primary)]">
                  {starter.text}
                </span>
                <ArrowUpRight
                  className="size-4 shrink-0 text-[color:var(--g-text-muted)] transition-colors group-hover:text-[color:var(--g-text-primary)]"
                  aria-hidden
                />
              </button>
            </li>
          ))}
        </ul>

        <ol
          aria-label="How a request runs"
          className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-[color:var(--g-text-muted)]"
        >
          {MISSION_STAGE_ORDER.map((stage, index) => (
            <li key={stage.id} className="inline-flex items-center gap-2" title={stage.explain}>
              {index > 0 ? (
                <span aria-hidden className="h-px w-3 bg-[color:var(--g-border-strong)]" />
              ) : null}
              <span className={stage.id === "approval" ? "font-medium text-[color:var(--g-text-primary)]" : undefined}>
                {stage.label}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}
