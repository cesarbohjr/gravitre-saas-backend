"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { RelationshipsWorkspace } from "@/components/intelligence/relationships/relationships-workspace"
import { PerformanceWaterfall } from "@/app/admin/intelligence/_components/performance-waterfall"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { ShotAuthProvider } from "../shot-auth"

/** PART 72 — high-fidelity prototype gallery (fixture data only, not production). */
const PROTOTYPES: { id: string; title: string; blurb: string }[] = [
  { id: "1", title: "Relationships — default", blurb: "Graph-first workspace with seeded + learned data." },
  { id: "2", title: "Grouped tracked-by cluster", blurb: "Aggregated customer → agent edges." },
  { id: "8", title: "Add first entity", blurb: "Onboarding sheet with type picker." },
  { id: "9", title: "Duplicate match review", blurb: "Possible match panel on create." },
  { id: "14", title: "Performance stage bars", blurb: "Classical + unified stage breakdown." },
  { id: "15", title: "Performance waterfall", blurb: "TTFT waterfall slices." },
  { id: "17", title: "Performance uninstrumented", blurb: "Empty / instrumentation-required states." },
]

const SHOT_SNAPSHOT = {
  queryVolume: { totalLogged: 42, distinctNormalized: 38, failedSearchCount: 2 },
  recentFailedSearches: [] as Array<Record<string, unknown>>,
  clusters: [] as Array<Record<string, unknown>>,
  glossary: [
    { id: "term_northwind", term: "Northwind Logistics" },
    { id: "term_revops", term: "RevOps playbook" },
  ],
  knowledgeGaps: [] as Array<Record<string, unknown>>,
  entityRelationships: [] as Array<Record<string, unknown>>,
}

const FIXTURE_WATERFALL = {
  unifiedTurn: [
    { stage: "unified_registry_tools", label: "Registry tools", avgMs: 42, p50Ms: 38, p95Ms: 71, count: 12 },
    { stage: "unified_context_prompt", label: "Context assembly", avgMs: 186, p50Ms: 160, p95Ms: 240, count: 12 },
    { stage: "unified_model_ttft", label: "Model TTFT", avgMs: 920, p50Ms: 880, p95Ms: 1100, count: 12 },
  ],
  classical: [
    { stage: "retrieval", label: "Retrieval", avgMs: 184, p50Ms: 160, p95Ms: 220, count: 48 },
    { stage: "rerank", label: "Rerank", avgMs: 143, p50Ms: 120, p95Ms: 190, count: 48 },
    { stage: "generation", label: "Generation", avgMs: 1888, p50Ms: 1700, p95Ms: 2400, count: 48 },
  ],
}

function Learning4PrototypeBody() {
  const params = useSearchParams()
  const p = params.get("p") ?? "index"

  if (p === "index") {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">Learning 4.0 — PART 72 prototypes</h1>
          <p className="text-sm text-muted-foreground">
            High-fidelity fixture captures for Relationships + Performance. Not linked from production nav.
          </p>
        </div>
        <ul className="divide-y divide-border rounded-xl border border-border/70">
          {PROTOTYPES.map((item) => (
            <li key={item.id}>
              <Link
                href={`/e2e/shots/learning-4?p=${item.id}`}
                className="flex flex-col gap-0.5 px-4 py-3 transition-colors hover:bg-muted/40"
              >
                <span className="text-sm font-medium">{item.title}</span>
                <span className="text-xs text-muted-foreground">{item.blurb}</span>
              </Link>
            </li>
          ))}
          <li>
            <Link
              href="/e2e/shots/relationships"
              className="flex flex-col gap-0.5 px-4 py-3 transition-colors hover:bg-muted/40"
            >
              <span className="text-sm font-medium">Full Relationships harness</span>
              <span className="text-xs text-muted-foreground">Playwright visual baseline route</span>
            </Link>
          </li>
        </ul>
      </div>
    )
  }

  if (p === "14" || p === "15") {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
        <p className="text-xs text-amber-600 dark:text-amber-400">
          PLACEHOLDER — fixture timings for visual capture only, not live telemetry.
        </p>
        <PerformanceWaterfall
          title="Unified turn TTFT waterfall"
          subtitle="Fixture prototype (PART 72 #15)"
          stages={FIXTURE_WATERFALL.unifiedTurn}
          emptyLabel="Instrumentation required"
          tone="violet"
        />
        <PerformanceWaterfall
          title="Classical pipeline waterfall"
          subtitle="Fixture prototype (PART 72 #14)"
          stages={FIXTURE_WATERFALL.classical}
          emptyLabel="No data yet"
          tone="cyan"
        />
      </div>
    )
  }

  if (p === "17") {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
        <PerformanceWaterfall
          title="Unified turn TTFT waterfall"
          subtitle="Uninstrumented state (PART 72 #17)"
          stages={[]}
          emptyLabel="Instrumentation required — unified-turn stages appear after live chat turns."
          tone="violet"
        />
        <PerformanceWaterfall
          title="Classical pipeline waterfall"
          subtitle="Empty period state (PART 72 #17)"
          stages={[]}
          emptyLabel="No pipeline samples in this period."
          tone="cyan"
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
      <p className="text-xs text-muted-foreground">
        Prototype {p} — Relationships workspace (fixture intercept). Open add-entity sheet for #8/#9.
      </p>
      <RelationshipsWorkspace data={SHOT_SNAPSHOT} isLoading={false} enabled />
    </div>
  )
}

export default function Learning4ShotPage() {
  const copy = SURFACE_COPY.learning
  return (
    <ShotAuthProvider>
      <AppShell title={`${copy.title} — Prototypes`}>
        <Suspense fallback={<p className="p-6 text-sm text-muted-foreground">Loading prototype…</p>}>
          <Learning4PrototypeBody />
        </Suspense>
      </AppShell>
    </ShotAuthProvider>
  )
}
