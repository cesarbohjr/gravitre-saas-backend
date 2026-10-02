"use client"

import type { ReactNode } from "react"
import useSWR from "swr"
import { Check, Eye, Hand, ShieldCheck, Zap } from "lucide-react"
import { agentIdentityApi } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { formatVendorLabel } from "@/lib/connectors"
import { cn } from "@/lib/utils"
import {
  deriveAutonomyLabel,
  type CapabilitySnapshot,
} from "@/lib/capabilities"

/**
 * Customer-facing autonomy labels derive from agent identity plus the
 * canonical WRITE-governance snapshot. Missing policy always fails closed to
 * ACT WITH APPROVAL.
 */
export const AUTONOMY_LEVELS = [
  {
    id: "read_only",
    label: "READ ONLY",
    icon: Eye,
    summary: "Can inspect and analyze only.",
  },
  {
    id: "write_with_approval",
    label: "ACT WITH APPROVAL",
    icon: Hand,
    summary: "Write actions are prepared and require human approval.",
  },
  {
    id: "autonomous",
    label: "ACT WITHIN POLICY",
    icon: Zap,
    summary: "Only explicitly policy-authorized actions may run unattended.",
  },
] as const

export type AutonomyLevelId = (typeof AUTONOMY_LEVELS)[number]["id"]

type CapabilityProfile = {
  allowedConnectors?: string[]
  availableReadActions?: string[]
  availableWriteActions?: string[]
  approvalRequiredActions?: string[]
}

const OVERRIDE_LABEL: Record<string, string> = {
  always_approve: "Always needs approval",
  always_deny: "Always denied",
  auto_run: "Runs without approval",
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-[color:var(--g-border-subtle)] py-2.5 last:border-b-0 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-[12px] font-medium text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-[13px] text-foreground">{children}</dd>
    </div>
  )
}

function Chips({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <span className="text-muted-foreground">{empty}</span>
  return (
    <span className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="rounded border border-[color:var(--g-border-default)] px-1.5 py-0.5 text-[12px] text-foreground dark:border-[color:var(--graphite-700)]"
        >
          {item}
        </span>
      ))}
    </span>
  )
}

export function AgentAutonomyPanel({ agentId, className }: { agentId: string; className?: string }) {
  const { data: status, error, isLoading } = useSWR(agentId ? `agent-identity-${agentId}` : null, () =>
    agentIdentityApi.get(agentId),
  )
  const { data: profile } = useSWR<CapabilityProfile>(agentId ? `/api/agents/${agentId}/capabilities` : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const { data: capabilitySnapshot } = useSWR<CapabilitySnapshot>(
    agentId ? "/api/capabilities" : null,
    apiFetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  )

  const record = status?.identity ?? null
  const storedTrustLevel = status?.effective?.trustLevel ?? record?.trustLevel ?? null
  const canonicalLabel = deriveAutonomyLabel(
    storedTrustLevel,
    record?.approvalRuleOverrides,
    capabilitySnapshot?.governance,
  )
  const effectiveLevel: AutonomyLevelId =
    canonicalLabel === "READ ONLY"
      ? "read_only"
      : canonicalLabel === "ACT WITHIN POLICY"
        ? "autonomous"
        : "write_with_approval"
  const level = AUTONOMY_LEVELS.find((l) => l.id === effectiveLevel) ?? null
  const kinds = status?.effective?.allowedActionKinds?.length
    ? status.effective.allowedActionKinds
    : record?.allowedActionKinds ?? []
  const patterns = status?.effective?.allowedToolPatterns?.length
    ? status.effective.allowedToolPatterns
    : record?.allowedToolPatterns ?? []
  const overrides = Object.entries(record?.approvalRuleOverrides ?? {})
  const connectors = profile?.allowedConnectors ?? []
  const canWrite = level ? level.id !== "read_only" && kinds.some((k) => k === "write" || k === "delete") : false

  return (
    <section
      aria-labelledby="agent-autonomy-heading"
      data-review-surface="agent-autonomy"
      className={cn("border-y border-[color:var(--g-border-default)] py-1", className)}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 py-3">
        <div>
          <h3 id="agent-autonomy-heading" className="text-[13px] font-semibold text-foreground">
            Autonomy and access
          </h3>
          <p className="mt-0.5 text-[12px] text-muted-foreground">What policy lets this agent read, execute and change.</p>
        </div>
        {record?.updatedAt ? (
          <span className="text-[11.5px] text-muted-foreground">Policy updated {new Date(record.updatedAt).toLocaleDateString()}</span>
        ) : null}
      </header>

      <div role="img" aria-label={level ? `Autonomy: ${level.label}` : "Autonomy: governed by organization policy"} className="relative grid grid-cols-3 gap-px overflow-hidden rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-border-subtle)] dark:border-[color:var(--graphite-700)]">
        {AUTONOMY_LEVELS.map((option) => {
          const active = option.id === level?.id
          const Icon = option.icon
          return (
            <div
              key={option.id}
              data-autonomy-level={option.id}
              data-active={active ? "" : undefined}
              className={cn(
                "relative px-3 py-2.5",
                active
                  ? "bg-[color:var(--g-emerald-pale)] before:absolute before:inset-x-0 before:top-0 before:h-[2px] before:bg-[color:var(--g-emerald)] dark:bg-[color:var(--graphite-800)]"
                  : "bg-[color:var(--g-canvas)]",
              )}
            >
              <span className={cn("flex items-center gap-1.5 text-[12.5px] font-semibold", active ? "text-foreground" : "text-muted-foreground")}>
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {option.label}
                {active ? <Check className="ml-auto h-3.5 w-3.5 text-[color:var(--g-emerald-deep)]" aria-hidden /> : null}
              </span>
              <span className={cn("mt-1 hidden text-[11.5px] leading-snug sm:block", active ? "text-foreground/80" : "text-muted-foreground")}>
                {option.summary}
              </span>
            </div>
          )
        })}
      </div>
      {!isLoading && !level ? (
        <p className="mt-2 text-[12px] text-muted-foreground">
          {error ? "Identity policy could not be loaded." : "No agent identity policy set. Organization approval policy governs every action."}
        </p>
      ) : null}

      <dl className="mt-2">
        <Row label="Can read">
          <Chips items={profile?.availableReadActions ?? []} empty={kinds.includes("read") ? "Read allowed; no connector scopes granted" : "—"} />
        </Row>
        <Row label="Can execute">
          {level?.id === "read_only" ? (
            <span className="text-muted-foreground">Nothing — read-only policy</span>
          ) : (
            <Chips items={profile?.availableWriteActions ?? []} empty={canWrite ? "Writes allowed; no connector write scopes granted" : "—"} />
          )}
        </Row>
        <Row label="Requires approval">
          {level?.id === "write_with_approval" ? (
            <span>Every write action</span>
          ) : level?.id === "autonomous" ? (
            <span className="text-muted-foreground">Only explicitly policy-authorized actions can run unattended; high-risk actions still require approval.</span>
          ) : level?.id === "read_only" ? (
            <span className="text-muted-foreground">Not applicable</span>
          ) : (
            <span className="text-muted-foreground">Set by organization policy</span>
          )}
          {overrides.length ? (
            <ul className="mt-1.5 space-y-1">
              {overrides.map(([kind, rule]) => (
                <li key={kind} className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                  <ShieldCheck className="h-3 w-3" aria-hidden />
                  <span className="font-mono text-[11.5px] text-foreground">{kind}</span>: {OVERRIDE_LABEL[rule] ?? rule}
                </li>
              ))}
            </ul>
          ) : null}
        </Row>
        <Row label="Where it can act">
          {connectors.length ? (
            <span className="flex flex-wrap gap-2">
              {connectors.map((c) => (
                <span key={c} className="inline-flex items-center gap-1.5 text-[12.5px]">
                  <ProviderLogo provider={c} size="sm" decorative />
                  {formatVendorLabel(c)}
                </span>
              ))}
            </span>
          ) : (
            <span className="text-muted-foreground">No connector permissions granted</span>
          )}
          {patterns.length ? (
            <span className="mt-1 block text-[12px] text-muted-foreground">Tools limited to: <span className="font-mono text-[11.5px]">{patterns.join(", ")}</span></span>
          ) : null}
        </Row>
        <Row label="Daily limits">
          {record && (record.maxActionsPerDay != null || record.maxSpendUsdPerDay != null) ? (
            <span className="tabular-nums">
              {[
                record.maxActionsPerDay != null ? `${record.maxActionsPerDay} actions` : null,
                record.maxSpendUsdPerDay != null ? `$${record.maxSpendUsdPerDay} spend` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
              {status?.usageToday ? (
                <span className="text-muted-foreground">
                  {" "}
                  · used today {status.usageToday.actions} actions
                </span>
              ) : null}
            </span>
          ) : (
            <span className="text-muted-foreground">No limits set</span>
          )}
        </Row>
      </dl>
    </section>
  )
}

/**
 * Strength radar slot. The backend has no measured per-dimension strength
 * scores, so this states that plainly instead of drawing a shape.
 */
export function AgentStrengthProfile({ className }: { className?: string }) {
  return (
    <section
      aria-labelledby="agent-strength-heading"
      data-review-surface="agent-strength"
      className={cn("border-y border-[color:var(--g-border-default)] py-3", className)}
    >
      <h3 id="agent-strength-heading" className="text-[13px] font-semibold text-foreground">
        Strength profile
      </h3>
      <p className="mt-1 text-[12px] text-muted-foreground">
        Not measured. Gravitre does not yet score agents per dimension (reasoning, research, execution, reliability), so
        no radar is drawn. Success rate is the only measured performance signal.
      </p>
    </section>
  )
}
