"use client"

import { useState } from "react"
import useSWR from "swr"
import { ChevronDown, ChevronUp, HelpCircle, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { assistantApi } from "@/lib/api"

const DISMISS_KEY = "gravitre:assistantOrgContextDismissed"

export function OrgContextPill({ enabled }: { enabled: boolean }) {
  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false
    return localStorage.getItem(DISMISS_KEY) === "1"
  })

  const { data } = useSWR(enabled && !dismissed ? "assistant-org-context" : null, () =>
    assistantApi.orgContext(),
  )

  if (!enabled || dismissed || !data) return null

  const { counts, agents = [], workflows = [], connectors = [] } = data

  return (
    <div className="mx-4 mt-3 rounded-xl border border-zinc-200 bg-zinc-50/80 px-3 py-2 text-sm text-zinc-600">
      <div className="flex items-start gap-2">
        <p className="flex-1 text-xs leading-relaxed">
          I know about your{" "}
          <span className="font-medium text-zinc-800">{counts.agents} agents</span>,{" "}
          <span className="font-medium text-zinc-800">{counts.workflows} workflows</span>, and{" "}
          <span className="font-medium text-zinc-800">{counts.connectors} connected tools</span>.
        </p>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setExpanded((v) => !v)}
            aria-label="Show org context details"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <HelpCircle className="h-3.5 w-3.5" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => {
              setDismissed(true)
              localStorage.setItem(DISMISS_KEY, "1")
            }}
            aria-label="Dismiss org context"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      {expanded ? (
        <div className={cn("mt-2 grid gap-2 border-t border-zinc-200 pt-2 text-[11px] md:grid-cols-3")}>
          <div>
            <p className="mb-1 font-medium text-zinc-700">Agents</p>
            <ul className="space-y-0.5 text-zinc-500">
              {agents.slice(0, 5).map((a) => (
                <li key={a.id}>{a.name}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-1 font-medium text-zinc-700">Workflows</p>
            <ul className="space-y-0.5 text-zinc-500">
              {workflows.slice(0, 5).map((w) => (
                <li key={w.id}>{w.name}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-1 font-medium text-zinc-700">Connectors</p>
            <ul className="space-y-0.5 text-zinc-500">
              {connectors.slice(0, 5).map((c) => (
                <li key={c.id}>{c.type || c.name}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
  )
}
