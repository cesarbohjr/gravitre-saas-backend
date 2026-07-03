"use client"

import { Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

export type AdvisorAction = {
  id?: string
  action?: string
  title?: string
  reason?: string
  summary?: string
  impact?: string
  estimated_impact?: string
  confidence?: number
}

export type AdvisorBrief = {
  mode?: string
  department?: string
  what_changed?: string[]
  why?: string
  recommended_actions?: AdvisorAction[]
  risks?: Array<{ title?: string; summary?: string }>
  opportunities?: Array<{ title?: string; summary?: string }>
  impact_summary?: string
  confidence?: number
  evidence?: Array<{ source?: string; title?: string; department?: string }>
  advisory_only?: boolean
}

export function AdvisorBriefPanel({ brief }: { brief: AdvisorBrief | null | undefined }) {
  if (!brief) return null

  const actions = brief.recommended_actions ?? []

  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
      <div className="mb-2 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-300">
          Advisor brief{brief.department ? ` · ${brief.department}` : ""}
        </p>
        {brief.confidence != null ? (
          <span className="ml-auto text-[10px] text-muted-foreground">
            {Math.round(brief.confidence * 100)}% confidence
          </span>
        ) : null}
      </div>

      {brief.what_changed?.length ? (
        <div className="mb-2">
          <p className="text-[11px] font-medium text-foreground">What changed</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {brief.what_changed.slice(0, 4).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {brief.why ? <p className="mb-2 text-xs text-muted-foreground">{brief.why}</p> : null}

      {actions.length ? (
        <div className="space-y-2">
          <p className="text-[11px] font-medium text-foreground">What to do</p>
          {actions.slice(0, 3).map((action) => (
            <div
              key={action.id ?? action.action ?? action.title}
              className="rounded-lg border border-border/60 bg-background/70 px-3 py-2"
            >
              <p className="text-sm font-medium text-foreground">{action.action ?? action.title}</p>
              {action.reason ?? action.summary ? (
                <p className="mt-0.5 text-xs text-muted-foreground">{action.reason ?? action.summary}</p>
              ) : null}
              <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                {action.impact ?? action.estimated_impact ? (
                  <span>Impact: {action.impact ?? action.estimated_impact}</span>
                ) : null}
                {action.confidence != null ? (
                  <span>{Math.round(action.confidence * 100)}% relevance</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {brief.impact_summary ? (
        <p className={cn("mt-2 text-[11px] text-muted-foreground")}>{brief.impact_summary}</p>
      ) : null}
      <p className="mt-2 text-[10px] text-muted-foreground">Advisory only — review before acting.</p>
    </div>
  )
}
