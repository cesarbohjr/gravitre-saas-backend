"use client"

import type { RefObject } from "react"
import useSWR from "swr"
import { ArrowUpRight, ShieldCheck, Sparkles } from "lucide-react"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useOptionalGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { routeContextLabel } from "@/components/gravitre/ai-helper"

type Starter = { text: string; hint: string }

const BASE_STARTERS: Starter[] = [
  { text: "What changed in my workspace since yesterday?", hint: "Briefing" },
  { text: "Find failed workflow runs from the last 24 hours", hint: "Runs" },
  { text: "Summarize our pipeline health and flag stale deals", hint: "Pipeline" },
  { text: "Which agents are busiest this week?", hint: "Workforce" },
]

/**
 * First view of an empty conversation: identity, the context Gravitre will use,
 * and starter prompts staged into the composer (never auto-sent).
 */
export function AiStartingState({
  onInputChange,
  inputRef,
}: {
  onInputChange: (value: string) => void
  inputRef?: RefObject<HTMLTextAreaElement | null>
}) {
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
  ].slice(0, 4)

  const stage = (text: string) => {
    onInputChange(text)
    requestAnimationFrame(() => inputRef?.current?.focus())
  }

  return (
    <div className="mx-auto flex w-full max-w-[680px] flex-col px-2 pb-6 pt-[8vh]" data-gravitre-ai-start="">
      <span className="mb-4 flex size-10 items-center justify-center rounded-[12px] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
        <Sparkles className="size-5" aria-hidden />
      </span>
      <h2 className="text-balance text-2xl font-semibold tracking-[-0.02em] text-[color:var(--g-text-primary)] sm:text-[28px]">
        What do you want to get done?
      </h2>
      <p className="mt-2 text-sm text-[color:var(--g-text-muted)]">
        Ask, delegate or search. Actions that change your systems wait for your approval.
      </p>

      {selected || origin || pending > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[12px]" aria-label="Context">
          {origin ? (
            <span className="rounded-full border border-[color:var(--g-border-default)] px-2.5 py-1 text-[color:var(--g-text-muted)]">
              From {origin}
            </span>
          ) : null}
          {selected ? (
            <span className="rounded-full bg-[color:var(--g-intelligence-soft)] px-2.5 py-1 font-medium text-[color:var(--g-intelligence)]">
              {selected.label}
            </span>
          ) : null}
          {pending > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-[color:var(--g-signal-soft)] px-2.5 py-1 font-medium text-[color:var(--g-signal)]">
              <ShieldCheck className="size-3.5" aria-hidden />
              {pending} waiting for approval
            </span>
          ) : null}
        </div>
      ) : null}

      <ul className="mt-6 grid gap-2 sm:grid-cols-2" aria-label="Suggested requests">
        {starters.map((starter) => (
          <li key={starter.text}>
            <button
              type="button"
              onClick={() => stage(starter.text)}
              className="group flex h-full w-full flex-col items-start gap-1.5 rounded-[12px] border border-[color:var(--g-border-default)] bg-background p-3 text-left transition-[border-color,box-shadow] hover:border-[color:var(--g-border-strong)] hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="flex w-full items-center justify-between text-[11px] font-medium text-[color:var(--g-text-muted)]">
                {starter.hint}
                <ArrowUpRight className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
              </span>
              <span className="text-[13px] leading-snug text-[color:var(--g-text-primary)]">{starter.text}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
