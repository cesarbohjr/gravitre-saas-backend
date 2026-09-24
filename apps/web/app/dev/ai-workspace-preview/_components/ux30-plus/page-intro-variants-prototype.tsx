"use client"

/**
 * Page-intro structural choice package — realistic content + family map + compare.
 * Harness only · Cesar selects · not one global header.
 */

import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type IntroVariant = "operating" | "expert" | "empty" | "immersive" | "compare"

const FAMILIES: Record<Exclude<IntroVariant, "compare">, string[]> = {
  operating: ["Dashboard", "Activity", "Assignments", "Approvals", "Notifications", "Goals (list)"],
  expert: ["Workflow Builder", "Model Studio", "Connectors admin", "Settings dense", "Agent configuration"],
  empty: ["First-run any family", "Insufficient Intelligence data", "No connectors", "Empty Marketplace search"],
  immersive: ["Intelligence Field", "Relationship Graph", "Knowledge Graph", "Fullscreen AI work"],
}

const TRADEOFFS: Record<Exclude<IntroVariant, "compare">, { pros: string; cons: string }> = {
  operating: {
    pros: "Answer what matters now; clear primary action; suits interrupted operators.",
    cons: "Weak for dense expert canvas; strips can become KPI card parking.",
  },
  expert: {
    pros: "Metadata + tools first; maximizes workspace; power users orient fast.",
    cons: "Cold for first-run; can feel like admin software.",
  },
  empty: {
    pros: "Honest insufficient data; one next action; avoids fake density.",
    cons: "Must not be the default when data exists.",
  },
  immersive: {
    pros: "Field/canvas is the product; chrome recedes; matches §21 Field primacy.",
    cons: "Harder discoverability of secondary actions; needs strong empty handling.",
  },
}

function OperatingFrame({ mobile }: { mobile?: boolean }) {
  // SaaSFrame Mintlify: greeting + secondary actions + stepper + hero status card + activity — not equal KPI cards.
  return (
    <HarnessSurface className={cn("space-y-4 p-5", mobile && "max-w-[390px]")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={TYPE.eyebrow}>Operating · SaaSFrame Mintlify structure</p>
          <h3 className={cn(TYPE.pageTitle, "mt-1")}>Intelligence</h3>
          <p className={cn(TYPE.pageLead, "mt-1")}>
            3 accounts need attention · 1 workflow waiting on approval.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm">Review approvals</Button>
          <Button size="sm" variant="secondary">
            What changed?
          </Button>
          <Button size="sm" variant="ghost">
            Ask Gravitre
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        {[
          { n: 1, label: "Sources connected", done: true },
          { n: 2, label: "First Field insight", done: true },
          { n: 3, label: "Clear approvals", done: false },
        ].map((s) => (
          <span
            key={s.n}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
              s.done
                ? "border-[color:var(--g-brand)]/30 bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]"
                : "border-[color:var(--g-border-subtle)] text-[color:var(--g-text-muted)]",
            )}
          >
            <span className="font-mono text-[10px]">{s.done ? "✓" : s.n}</span>
            {s.label}
          </span>
        ))}
      </div>

      <div className="rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className={TYPE.meta}>Primary work · fixture</p>
            <p className="mt-1 text-sm font-medium">Acme renewal risk · Field insight ready</p>
            <p className={TYPE.meta}>Last update · fixture · not live evidence</p>
          </div>
          <span className="rounded-md bg-[color:var(--g-brand-soft)] px-2 py-0.5 text-[11px] font-medium text-[color:var(--g-brand)]">
            Live lens
          </span>
        </div>
        <div className="mt-3 h-28 rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3">
          <p className={TYPE.meta}>Field preview (secondary under operating strip)</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-[color:var(--g-border-subtle)]">
        <div className="border-b border-[color:var(--g-border-subtle)] px-3 py-2">
          <p className={TYPE.eyebrow}>Recent activity · fixture</p>
        </div>
        <ul className="divide-y divide-[color:var(--g-border-subtle)] text-sm">
          <li className="flex justify-between gap-2 px-3 py-2">
            <span>Prospect enrich · failed step 3</span>
            <span className="text-[color:var(--g-danger)]">failed</span>
          </li>
          <li className="flex justify-between gap-2 px-3 py-2">
            <span>HubSpot write · awaiting approval</span>
            <span className="text-[color:var(--g-warning)]">waiting</span>
          </li>
        </ul>
      </div>
    </HarnessSurface>
  )
}

function ExpertFrame({ mobile }: { mobile?: boolean }) {
  return (
    <HarnessSurface className={cn("p-5", mobile && "max-w-[390px]")}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className={TYPE.eyebrow}>Expert</p>
          <h3 className={cn(TYPE.pageTitle, "mt-1")}>Intelligence</h3>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-mono text-[11px] text-[color:var(--g-text-muted)]">128 entities · 412 rel · lens knows</p>
          <Button size="sm" variant="secondary">
            Filters
          </Button>
          <Button size="sm">Inspect</Button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-1 border-b border-[color:var(--g-border-subtle)] pb-2 text-xs">
        {["Field", "Matrix", "Relationships", "Predictive"].map((t) => (
          <span
            key={t}
            className={cn(
              "rounded-md px-2 py-1",
              t === "Field" ? "bg-[color:var(--g-intelligence-soft)]" : "text-[color:var(--g-text-muted)]",
            )}
          >
            {t}
          </span>
        ))}
      </div>
      <div className="mt-4 h-56 rounded-lg border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]" />
    </HarnessSurface>
  )
}

function EmptyFrame() {
  return (
    <HarnessSurface className="flex min-h-[280px] flex-col items-start justify-center p-8">
      <p className={TYPE.eyebrow}>Empty / first-run</p>
      <h3 className={cn(TYPE.pageTitle, "mt-2")}>No knowledge fabric yet</h3>
      <p className={cn(TYPE.pageLead, "mt-2 max-w-md")}>
        Connect a source or run a workflow that writes entities. Do not invent demo graph density.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm">Connect source</Button>
        <Button size="sm" variant="secondary">
          Open Marketplace packs
        </Button>
      </div>
    </HarnessSurface>
  )
}

function ImmersiveFrame() {
  return (
    <div className="overflow-hidden rounded-xl border border-[color:var(--g-border-default)]">
      <div className="relative h-[380px] bg-[color:var(--g-canvas)]">
        <svg className="absolute inset-0 h-full w-full" aria-hidden>
          <line x1="20%" y1="40%" x2="48%" y2="52%" stroke="var(--g-border-subtle)" />
          <line x1="48%" y1="52%" x2="72%" y2="30%" stroke="var(--g-border-subtle)" />
          <circle cx="20%" cy="40%" r="6" fill="var(--g-intelligence)" />
          <circle cx="48%" cy="52%" r="8" fill="var(--g-brand)" />
          <circle cx="72%" cy="30%" r="6" fill="var(--g-signal)" />
        </svg>
        <div className="absolute left-4 top-4 max-w-sm rounded-lg border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/95 p-3">
          <p className={TYPE.eyebrow}>Immersive</p>
          <h3 className={cn(TYPE.cardTitle, "mt-1")}>Field is the page</h3>
          <p className={TYPE.meta}>Acme · relationship strengthened · Ask or inspect</p>
          <div className="mt-2 flex gap-2">
            <Button size="sm">Inspect</Button>
            <Button size="sm" variant="ghost">
              Matrix
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function PageIntroVariantsPrototype({ scene }: { scene: string }) {
  const variant = (["operating", "expert", "empty", "immersive", "compare"].find((v) => scene.includes(v)) ??
    "operating") as IntroVariant
  const mobile = scene.includes("mobile")

  return (
    <div data-review-surface="page-intro" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>Selection A · Page introduction · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Structural hierarchy options</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Realistic Gravitre content. Different structures — not cosmetic skins. Final pick reserved for Cesar.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {(["operating", "expert", "empty", "immersive", "compare"] as const).map((v) => (
          <Button key={v} size="sm" variant={variant === v ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=page-intro&scene=${v}`}>{v}</a>
          </Button>
        ))}
        <Button size="sm" variant={mobile ? "secondary" : "ghost"} asChild>
          <a href={`/dev/ai-workspace-preview?s=page-intro&scene=${variant === "compare" ? "operating" : variant}-mobile`}>
            mobile
          </a>
        </Button>
      </div>

      {variant === "operating" && <OperatingFrame mobile={mobile} />}
      {variant === "expert" && <ExpertFrame mobile={mobile} />}
      {variant === "empty" && <EmptyFrame />}
      {variant === "immersive" && <ImmersiveFrame />}

      {variant === "compare" && (
        <div className="space-y-6">
          <OperatingFrame />
          <ExpertFrame />
          <EmptyFrame />
          <ImmersiveFrame />
        </div>
      )}

      {variant !== "compare" && (
        <HarnessSurface className="p-4">
          <p className={TYPE.eyebrow}>Intended page families</p>
          <p className="mt-2 text-sm">{FAMILIES[variant].join(" · ")}</p>
          <p className={cn(TYPE.meta, "mt-3")}>Advantages</p>
          <p className="text-sm">{TRADEOFFS[variant].pros}</p>
          <p className={cn(TYPE.meta, "mt-3")}>Tradeoffs</p>
          <p className="text-sm">{TRADEOFFS[variant].cons}</p>
        </HarnessSurface>
      )}

      {variant === "compare" && (
        <HarnessSurface className="p-4">
          <p className={TYPE.eyebrow}>Family → pattern map (proposal, not decision)</p>
          <ul className="mt-2 space-y-2 text-sm">
            {(Object.keys(FAMILIES) as Exclude<IntroVariant, "compare">[]).map((k) => (
              <li key={k}>
                <span className="font-medium capitalize">{k}:</span> {FAMILIES[k].join(", ")}
              </li>
            ))}
          </ul>
        </HarnessSurface>
      )}
    </div>
  )
}
