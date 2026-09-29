"use client"

/**
 * Dashboard §40 — SaaSFrame-informed (Wise + Mintlify) · Nodus/Gravitre visual.
 * Harness only · fixture data · not live production evidence.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type Concept = "attention-first" | "ops-board" | "outcome-rail"

const CONCEPTS: { id: Concept; title: string; pros: string; cons: string }[] = [
  {
    id: "attention-first",
    title: "Attention-first",
    pros: "Wise-style hero status + accent CTA; Mintlify activity truth; matches §16 / §35.",
    cons: "Weaker for scanning many healthy systems; risk of alert fatigue.",
  },
  {
    id: "ops-board",
    title: "Ops board",
    pros: "Mintlify activity-table language across Running / Failed / Approvals columns.",
    cons: "Can look like generic kanban; business outcomes secondary.",
  },
  {
    id: "outcome-rail",
    title: "Outcome rail",
    pros: "Business outcomes lead; AI work nested under goals.",
    cons: "Harder when goals empty; more progressive-disclosure work.",
  },
]

const ACTIVITY = [
  { label: "Approve HubSpot write · Acme", status: "waiting" as const, when: "2m ago", duration: "—" },
  { label: "Prospect enrich · step 3", status: "failed" as const, when: "14m ago", duration: "41s" },
  { label: "Qualify lead · HubSpot", status: "ok" as const, when: "1h ago", duration: "2m 04s" },
  { label: "Apollo connector · auth check", status: "warn" as const, when: "3h ago", duration: "—" },
]

export function DashboardConceptsPrototype({ scene }: { scene: string }) {
  const concept = (CONCEPTS.find((c) => scene.includes(c.id))?.id ?? "attention-first") as Concept
  const meta = CONCEPTS.find((c) => c.id === concept)!

  return (
    <div data-review-surface="dashboard" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>§40 · Dashboard · SaaSFrame Wise + Mintlify · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Operational overview (research-applied)</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          REF Wise/Mintlify → hero attention + action row + activity table. Nodus tokens. Fixture ≠ production.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {CONCEPTS.map((c) => (
          <Button key={c.id} size="sm" variant={concept === c.id ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=dashboard&scene=${c.id}`}>{c.title}</a>
          </Button>
        ))}
      </div>

      {concept === "attention-first" && (
        <div className="space-y-4">
          <HarnessSurface className="space-y-4 p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className={TYPE.eyebrow}>Needs you · fixture</p>
                <h3 className={cn(TYPE.pageTitle, "mt-1 text-[1.5rem]")}>3 items require action</h3>
                <p className={TYPE.meta}>2 approvals · 1 failed run · 1 connector degraded</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm">Resolve next</Button>
                <Button size="sm" variant="secondary">
                  Ask Gravitre
                </Button>
                <Button size="sm" variant="ghost">
                  What changed?
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { t: "Waiting approval", v: "HubSpot write · Acme", tone: "border-[color:var(--g-warning)]/40" },
                { t: "Failed", v: "Prospect enrich · step 3", tone: "border-[color:var(--g-danger)]/40" },
                { t: "Degraded", v: "Apollo · auth expiring", tone: "border-[color:var(--g-border-subtle)]" },
              ].map((c) => (
                <div key={c.t} className={cn("rounded-lg border p-3", c.tone)}>
                  <p className={TYPE.meta}>{c.t}</p>
                  <p className="mt-1 text-sm font-medium">{c.v}</p>
                </div>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] p-3">
                <p className={TYPE.meta}>Running now</p>
                <p className="mt-1 text-sm font-medium">Qualify lead · 2/4 steps</p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[color:var(--g-border-subtle)]">
                  <div className="h-full w-1/2 rounded-full bg-[color:var(--g-brand)]" />
                </div>
              </div>
              <div className="rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] p-3">
                <p className={TYPE.meta}>Changed</p>
                <p className="mt-1 text-sm font-medium">3 Intelligence updates</p>
                <Button size="sm" variant="ghost" className="mt-1 h-7 px-0" asChild>
                  <a href="/dev/ai-workspace-preview?s=intelligence-journey&scene=field-primary">Open Field →</a>
                </Button>
              </div>
            </div>
          </HarnessSurface>

          <HarnessSurface className="overflow-hidden p-0">
            <div className="flex items-center justify-between border-b border-[color:var(--g-border-subtle)] px-4 py-3">
              <p className={TYPE.eyebrow}>Activity · fixture</p>
              <button type="button" className="text-xs text-[color:var(--g-brand)]">
                See all
              </button>
            </div>
            <table className="w-full text-left text-sm">
              <thead className="bg-[color:var(--g-surface-2)] text-[11px] uppercase tracking-wide text-[color:var(--g-text-muted)]">
                <tr>
                  <th className="px-4 py-2 font-medium">Activity</th>
                  <th className="px-4 py-2 font-medium">Updated</th>
                  <th className="px-4 py-2 font-medium">Duration</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {ACTIVITY.map((row) => (
                  <tr key={row.label} className="border-t border-[color:var(--g-border-subtle)]">
                    <td className="px-4 py-2.5">{row.label}</td>
                    <td className="px-4 py-2.5 text-[color:var(--g-text-muted)]">{row.when}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-[color:var(--g-text-muted)]">
                      {row.duration}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusPill status={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </HarnessSurface>
        </div>
      )}

      {concept === "ops-board" && (
        <div className="grid gap-3 md:grid-cols-3">
          {(
            [
              ["Running", ["Qualify lead · 2/4", "Enrich contacts · 1/5"]],
              ["Failed", ["Prospect enrich · step 3"]],
              ["Approvals", ["HubSpot write · Acme", "Outreach draft · Contoso"]],
            ] as const
          ).map(([col, items]) => (
            <HarnessSurface key={col} className="p-4">
              <p className={TYPE.eyebrow}>{col}</p>
              <ul className="mt-3 space-y-2 text-sm">
                {items.map((i) => (
                  <li key={i} className="rounded-md border border-[color:var(--g-border-subtle)] px-2 py-2">
                    {i}
                  </li>
                ))}
              </ul>
            </HarnessSurface>
          ))}
        </div>
      )}

      {concept === "outcome-rail" && (
        <HarnessSurface className="space-y-3 p-5">
          <p className={TYPE.eyebrow}>Outcomes · fixture</p>
          {[
            ["Renewal risk ↓", "Acme · Intelligence Field"],
            ["Pipeline coverage", "3 workflows · 1 waiting approval"],
          ].map(([t, s]) => (
            <div key={t} className="rounded-lg border border-[color:var(--g-border-subtle)] p-3">
              <p className="text-sm font-medium">{t}</p>
              <p className={TYPE.meta}>{s}</p>
            </div>
          ))}
        </HarnessSurface>
      )}

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>{meta.title} · tradeoffs</p>
        <p className="mt-2 text-sm text-[color:var(--g-text-secondary)]">Pros: {meta.pros}</p>
        <p className="mt-1 text-sm text-[color:var(--g-text-secondary)]">Cons: {meta.cons}</p>
      </HarnessSurface>
    </div>
  )
}

function StatusPill({ status }: { status: "ok" | "failed" | "waiting" | "warn" }) {
  const label =
    status === "ok" ? "ok" : status === "failed" ? "failed" : status === "waiting" ? "waiting" : "warn"
  const cls =
    status === "ok"
      ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]"
      : status === "failed"
        ? "bg-[color:var(--g-danger)]/10 text-[color:var(--g-danger)]"
        : status === "waiting"
          ? "bg-[color:var(--g-warning)]/15 text-[color:var(--g-warning)]"
          : "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)]"
  return <span className={cn("rounded-md px-2 py-0.5 text-[11px] font-medium", cls)}>{label}</span>
}
