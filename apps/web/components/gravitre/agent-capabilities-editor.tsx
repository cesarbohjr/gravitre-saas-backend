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
  capabilityNamesFromIds,
  customCapabilityNames,
  DEFAULT_MAX_ACTIONS_PER_HOUR,
  guardrailNamesFromIds,
} from "@/lib/agent-config-catalog"
import { MaxActionsPerHourInput } from "@/components/gravitre/max-actions-per-hour-input"
import { useConnectedAgentApps } from "@/lib/agent-connected-apps"

type AgentCapabilitiesEditorProps = {
  capabilityIds: string[]
  customCapabilities: string[]
  systemIds: string[]
  guardrailIds: string[]
  onCapabilityIdsChange: (ids: string[]) => void
  onCustomCapabilitiesChange: (names: string[]) => void
  onSystemIdsChange: (ids: string[]) => void
  onGuardrailIdsChange: (ids: string[]) => void
  maxActionsPerHour?: number
  onMaxActionsPerHourChange?: (value: number) => void
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
  maxActionsPerHour = DEFAULT_MAX_ACTIONS_PER_HOUR,
  onMaxActionsPerHourChange,
  knowledgeHref,
  className,
}: AgentCapabilitiesEditorProps) {
  const [draftCapability, setDraftCapability] = useState("")
  const { apps, error: appsError, isLoading: appsLoading } = useConnectedAgentApps()
  // Connected apps, plus any saved selection whose connector was since removed so it can be cleared.
  const appChoices = useMemo(() => {
    const connected = apps.map((app) => ({ ...app, connected: true }))
    const missing = systemIds
      .filter((id) => !apps.some((app) => app.id === id))
      .map((id) => ({ id, name: id.replace(/_/g, " "), type: "", connected: false }))
    return [...connected, ...missing]
  }, [apps, systemIds])
  const appName = (id: string) => appChoices.find((app) => app.id === id)?.name ?? id

  const resolvedCapabilityNames = useMemo(
    () => capabilityNamesFromIds(capabilityIds, customCapabilities),
    [capabilityIds, customCapabilities],
  )

  const addCustomCapability = () => {
    const next = draftCapability.trim()
    if (!next) return
    const exists =
      resolvedCapabilityNames.some(
        (name) => name.toLowerCase() === next.toLowerCase(),
      ) ||
      AGENT_CAPABILITY_OPTIONS.some(
        (option) => option.name.toLowerCase() === next.toLowerCase(),
      )
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
          <h3 className="text-sm font-semibold text-foreground">
            Capabilities
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Describe this agent’s intended skills. Labels do not grant runtime
            access.
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
                aria-pressed={selected}
                onClick={() =>
                  onCapabilityIdsChange(toggleId(capabilityIds, cap.id))
                }
                className={cn(
                  "flex min-h-11 items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors",
                  selected
                    ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">
                      {cap.name}
                    </span>
                    {selected ? (
                      <Check className="h-3.5 w-3.5 text-foreground" />
                    ) : null}
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
                  onCustomCapabilitiesChange(
                    customCapabilities.filter((item) => item !== name),
                  )
                }
                aria-label={`Remove ${name}`}
                className="min-h-11 break-words rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground"
                title="Remove custom capability"
              >
                {name} ×
              </button>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <input
            aria-label="Custom capability"
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
            className="min-h-11 min-w-0 flex-1 rounded-md border border-border bg-secondary px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!draftCapability.trim()}
            className="min-h-11 gap-1"
            onClick={addCustomCapability}
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </div>

        {knowledgeHref ? (
          <p className="text-xs text-muted-foreground">
            Knowledge sources (folders, docs, instructions) are managed on{" "}
            <Link
              href={knowledgeHref}
              className="underline underline-offset-2 hover:text-foreground"
            >
              the Knowledge page
            </Link>
            . Enable “Use knowledge” above so the agent is expected to ground in
            them.
          </p>
        ) : null}
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Connected apps
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {systemIds.length === 0
              ? "No apps selected: this agent can use every app your workspace has connected."
              : "This agent can only use the apps you select, plus Gravitre’s own reporting and workflow tools."}
          </p>
        </div>
        {appsLoading ? (
          <p className="text-xs text-muted-foreground">Loading connected apps…</p>
        ) : appsError ? (
          <p role="alert" className="text-xs text-destructive">
            Could not load connected apps. Saved selections are kept.
          </p>
        ) : appChoices.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No apps are connected yet.{" "}
            <Link href="/connectors" className="underline underline-offset-2 hover:text-foreground">
              Connect one
            </Link>{" "}
            to give this agent tools.
          </p>
        ) : null}
        <div className="grid gap-2 sm:grid-cols-2">
          {appChoices.map((system) => {
            const selected = systemIds.includes(system.id)
            return (
              <button
                key={system.id}
                type="button"
                aria-pressed={selected}
                onClick={() =>
                  onSystemIdsChange(toggleId(systemIds, system.id))
                }
                className={cn(
                  "flex min-h-11 items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-colors",
                  selected
                    ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <span>
                  <span className="block text-sm font-medium text-foreground">
                    {system.name}
                  </span>
                  <span
                    className={cn(
                      "text-[11px]",
                      system.connected ? "text-muted-foreground" : "text-warning",
                    )}
                  >
                    {system.connected ? system.type : "Not connected, so it has no tools"}
                  </span>
                </span>
                {selected ? (
                  <Check className="h-3.5 w-3.5 text-foreground" />
                ) : null}
              </button>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Safety rules
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Slow down and Workspace limits are enforced on every action this
            agent takes. Spending caps live under Governance.
          </p>
        </div>
        <div className="space-y-2">
          {AGENT_GUARDRAIL_OPTIONS.map((guard) => {
            const selected = guardrailIds.includes(guard.id)
            return (
              <button
                key={guard.id}
                type="button"
                aria-pressed={selected}
                onClick={() =>
                  onGuardrailIdsChange(toggleId(guardrailIds, guard.id))
                }
                className={cn(
                  "flex min-h-11 w-full items-start justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                  selected
                    ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]"
                    : "border-border bg-secondary/40 hover:border-foreground/20",
                )}
              >
                <span>
                  <span className="block text-sm font-medium text-foreground">
                    {guard.name}
                    {guard.recommended ? (
                      <span className="ml-2 text-xs font-normal text-muted-foreground font-medium">
                        Recommended
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-0.5 block text-[11px] text-muted-foreground">
                    {guard.description}
                  </span>
                </span>
                {selected ? (
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-foreground" />
                ) : null}
              </button>
            )
          })}
        </div>
        {guardrailIds.includes("rate-limit") && onMaxActionsPerHourChange ? (
          <MaxActionsPerHourInput value={maxActionsPerHour} onChange={onMaxActionsPerHourChange} />
        ) : null}
        <p className="text-[11px] text-muted-foreground">
          Selected apps: {systemIds.map(appName).join(", ") || "every connected app"} ·
          Gates: {guardrailNamesFromIds(guardrailIds).join(", ") || "none"}
        </p>
      </section>
    </div>
  )
}

export { customCapabilityNames }
