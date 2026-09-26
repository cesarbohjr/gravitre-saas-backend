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
    <div
      className="mx-auto grid w-full max-w-[1080px] gap-8 px-2 pb-6 pt-[6vh] lg:grid-cols-[minmax(0,1fr)_280px] lg:gap-12"
      data-gravitre-ai-start=""
    >
      <div className="min-w-0">
        <p className="mb-4 flex items-center gap-2 text-[13px] font-medium text-[color:var(--g-text-primary)]">
          <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--g-brand)]" aria-hidden />
          Gravitre AI · Objective
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
      </div>

      <aside className="min-w-0 space-y-6 lg:border-l lg:border-[color:var(--g-border-subtle)] lg:pl-8" aria-label="How requests run">
        {selected || origin || pending > 0 ? (
          <section aria-label="Context" className="space-y-2 text-[13px]">
            <h3 className="text-[12px] font-semibold text-[color:var(--g-text-primary)]">Context</h3>
            {origin ? <p className="text-[color:var(--g-text-muted)]">From {origin}</p> : null}
            {selected ? (
              <p className="border-l-2 border-[color:var(--g-intelligence)] pl-2 font-medium text-[color:var(--g-text-primary)]">
                {selected.label}
              </p>
            ) : null}
            {pending > 0 ? (
              <p className="inline-flex items-center gap-1.5 font-medium text-[color:var(--g-text-primary)]">
                <ShieldCheck className="size-3.5 text-[color:var(--g-signal)]" aria-hidden />
                <span className="tabular-nums">{pending}</span> waiting for approval
              </p>
            ) : null}
          </section>
        ) : null}
        <section className="space-y-3">
          <h3 className="text-[12px] font-semibold text-[color:var(--g-text-primary)]">How a request runs</h3>
          <ol className="relative space-y-3">
            {MISSION_STAGE_ORDER.map((stage, index) => (
              <li key={stage.id} className="relative flex gap-3">
                {index < MISSION_STAGE_ORDER.length - 1 ? (
                  <span aria-hidden className="absolute left-[4.5px] top-3 h-[calc(100%+2px)] w-px bg-[color:var(--g-border-default)]" />
                ) : null}
                <span aria-hidden className="relative z-10 mt-1 size-2.5 shrink-0 rounded-full border border-[color:var(--g-border-strong)] bg-background" />
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-semibold text-[color:var(--g-text-primary)]">{stage.label}</span>
                  <span className="block text-[12px] leading-snug text-[color:var(--g-text-muted)]">{stage.explain}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>
      </aside>
    </div>
  )
}
