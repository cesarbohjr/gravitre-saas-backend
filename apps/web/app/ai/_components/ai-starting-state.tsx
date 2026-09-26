"use client"

import type { RefObject } from "react"
import useSWR from "swr"
import { ArrowUpRight, ShieldCheck } from "lucide-react"
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
    <div className="mx-auto flex w-full max-w-[720px] flex-col px-2 pb-6 pt-[8vh]" data-gravitre-ai-start="">
      <p className="mb-5 flex items-center gap-2 text-[13px] font-medium text-[color:var(--g-text-primary)]">
        <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
        Gravitre AI
      </p>
      <h2 className="text-balance text-[28px] font-semibold leading-[1.08] tracking-[-0.03em] text-[color:var(--g-text-primary)] sm:text-[36px]">
        What do you want to get done?
      </h2>
      <p className="mt-3 max-w-[560px] text-[15px] leading-relaxed text-[color:var(--g-text-secondary)]">
        Ask, delegate or search. Actions that change your systems wait for your approval.
      </p>

      {selected || origin || pending > 0 ? (
        <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px]" aria-label="Context">
          {origin ? <span className="text-[color:var(--g-text-muted)]">From {origin}</span> : null}
          {selected ? (
            <span className="border-l-2 border-[color:var(--g-intelligence)] pl-2 font-medium text-[color:var(--g-text-primary)]">
              {selected.label}
            </span>
          ) : null}
          {pending > 0 ? (
            <span className="inline-flex items-center gap-1.5 font-medium text-[color:var(--g-text-primary)]">
              <ShieldCheck className="size-3.5 text-[color:var(--g-signal)]" aria-hidden />
              <span className="tabular-nums">{pending}</span> waiting for approval
            </span>
          ) : null}
        </div>
      ) : null}

      <ul
        className="mt-8 divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-default)]"
        aria-label="Suggested requests"
      >
        {starters.map((starter) => (
          <li key={starter.text}>
            <button
              type="button"
              onClick={() => stage(starter.text)}
              className="group flex w-full items-center gap-4 px-1 py-3 text-left transition-colors hover:bg-[color:var(--g-background-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
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
    </div>
  )
}
