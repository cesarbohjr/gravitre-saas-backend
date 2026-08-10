"use client"

/**
 * Editable capabilities / connectors / approval gates for create + profile.
 */

import { useMemo, useState } from "react"
import Link from "next/link"
import { Check, Plus } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  AGENT_CAPABILITY_OPTIONS,
  AGENT_GUARDRAIL_OPTIONS,
  AGENT_SYSTEM_OPTIONS,
  capabilityNamesFromIds,
  customCapabilityNames,
  guardrailNamesFromIds,
  systemNamesFromIds,
} from "@/lib/agent-config-catalog"

type AgentCapabilitiesEditorProps = {
  capabilityIds: string[]
  customCapabilities: string[]
  systemIds: string[]
  guardrailIds: string[]
  onCapabilityIdsChange: (ids: string[]) => void
  onCustomCapabilitiesChange: (names: string[]) => void
  onSystemIdsChange: (ids: string[]) => void
  onGuardrailIdsChange: (ids: string[]) => void
  knowledgeHref?: string
  className?: string
}

function toggleId(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]
}

export function AgentCapabilitiesEditor({
  capabilityIds,
  customCapabilities,
  systemIds,
  guardrailIds,
  onCapabilityIdsChange,
  onCustomCapabilitiesChange,
  onSystemIdsChange,
  onGuardrailIdsChange,
  knowledgeHref,
  className,
}: AgentCapabilitiesEditorProps) {
  const [draftCapability, setDraftCapability] = useState("")

  const resolvedCapabilityNames = useMemo(
    () => capabilityNamesFromIds(capabilityIds, customCapabilities),
    [capabilityIds, customCapabilities],
  )

  const addCustomCapability = () => {
    const next = draftCapability.trim()
    if (!next) return
    const exists =
      resolvedCapabilityNames.some((name) => name.toLowerCase() === next.toLowerCase()) ||
      AGENT_CAPABILITY_OPTIONS.some((option) => option.name.toLowerCase() === next.toLowerCase())
    if (exists) {
      setDraftCapability("")
      return
    }
    onCustomCapabilitiesChange([...customCapabilities, next])
    setDraftCapability("")
  }

  return (
    <div className={cn("space-y-8", className)}>
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Capabilities</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            What this agent can do. Add catalog skills or your own capability labels.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {AGENT_CAPABILITY_OPTIONS.map((cap) => {
            const selected = capabilityIds.includes(cap.id)
            const Icon = cap.icon
            return (
              <button
                key={cap.id}
                type="button"
                onClick={() => onCapabilityIdsChange(toggleId(capabilityIds, cap.id))}
                className={cn(
                  "flex items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors",
                  selected
                    ? "border-foreground/40 bg-card"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">{cap.name}</span>
                    {selected ? <Check className="h-3.5 w-3.5 text-foreground" /> : null}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">
                    {cap.description}
                  </span>
                </span>
              </button>
            )
          })}
        </div>

        {customCapabilities.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {customCapabilities.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() =>
                  onCustomCapabilitiesChange(customCapabilities.filter((item) => item !== name))
                }
                className="rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground"
                title="Remove custom capability"
              >
                {name} ×
              </button>
            ))}
          </div>
        ) : null}

        <div className="flex gap-2">
          <input
            type="text"
            value={draftCapability}
            onChange={(event) => setDraftCapability(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault()
                addCustomCapability()
              }
            }}
            placeholder="Add a custom capability…"
            className="h-9 flex-1 rounded-md border border-border bg-secondary px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <Button type="button" variant="outline" size="sm" className="h-9 gap-1" onClick={addCustomCapability}>
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </div>

        {knowledgeHref ? (
          <p className="text-xs text-muted-foreground">
            Knowledge sources (folders, docs, instructions) are managed on{" "}
            <Link href={knowledgeHref} className="underline underline-offset-2 hover:text-foreground">
              the Knowledge page
            </Link>
            . Enable “Use knowledge” above so the agent is expected to ground in them.
          </p>
        ) : null}
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Connectors / apps</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Systems this agent is allowed to use. Live connector setup still happens under Integrations.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {AGENT_SYSTEM_OPTIONS.map((system) => {
            const selected = systemIds.includes(system.id)
            return (
              <button
                key={system.id}
                type="button"
                onClick={() => onSystemIdsChange(toggleId(systemIds, system.id))}
                className={cn(
                  "flex items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-colors",
                  selected
                    ? "border-foreground/40 bg-card"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <span>
                  <span className="block text-sm font-medium text-foreground">{system.name}</span>
                  <span className="text-[11px] text-muted-foreground">{system.type}</span>
                </span>
                {selected ? <Check className="h-3.5 w-3.5 text-foreground" /> : null}
              </button>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Actions / approval gates</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Safety limits for writes, deletes, and rate of action.
          </p>
        </div>
        <div className="space-y-2">
          {AGENT_GUARDRAIL_OPTIONS.map((guard) => {
            const selected = guardrailIds.includes(guard.id)
            return (
              <button
                key={guard.id}
                type="button"
                onClick={() => onGuardrailIdsChange(toggleId(guardrailIds, guard.id))}
                className={cn(
                  "flex w-full items-start justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                  selected
                    ? "border-foreground/40 bg-card"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <span>
                  <span className="block text-sm font-medium text-foreground">
                    {guard.name}
                    {guard.recommended ? (
                      <span className="ml-2 text-[10px] font-normal uppercase tracking-wide text-muted-foreground">
                        Recommended
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">
                    {guard.description}
                  </span>
                </span>
                {selected ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-foreground" /> : null}
              </button>
            )
          })}
        </div>
        <p className="text-[11px] text-muted-foreground">
          Selected apps: {systemNamesFromIds(systemIds).join(", ") || "none"} · Gates:{" "}
          {guardrailNamesFromIds(guardrailIds).join(", ") || "none"}
        </p>
      </section>
    </div>
  )
}

export { customCapabilityNames }
