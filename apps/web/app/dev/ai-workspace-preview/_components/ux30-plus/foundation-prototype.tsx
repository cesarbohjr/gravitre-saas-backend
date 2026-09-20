"use client"

import { motion } from "framer-motion"
import { EvidenceChip } from "@/components/gravitre/creative-grammar"
import { TYPE, SEMANTIC, MOTION } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { TopologyEdge, TopologyNode, HarnessSurface } from "./topology-primitives"
import { HARNESS_FIXTURE_LABEL } from "./fixtures"

export function FoundationPrototype({ scene }: { scene: string }) {
  const reduced = scene.includes("reduced")

  return (
    <div data-review-surface="foundation" data-review-scene={scene} className="mx-auto max-w-5xl space-y-8">
      <header>
        <p className={TYPE.eyebrow}>3.0 Plus · Shared visual foundation</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>One grammar for Intelligence + Activity</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>{HARNESS_FIXTURE_LABEL}</p>
      </header>

      <section className="grid gap-6 lg:grid-cols-2">
        <HarnessSurface className="p-5">
          <p className={TYPE.eyebrow}>Canvas & depth</p>
          <div className="mt-4 rounded-lg bg-[color:var(--g-canvas)] p-4">
            <div className="rounded-xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 shadow-sm">
              <p className={TYPE.cardTitle}>Work surface</p>
              <p className={cn(TYPE.meta, "mt-1")}>Elevated · hairline · no card-in-card</p>
            </div>
          </div>
        </HarnessSurface>

        <HarnessSurface className="p-5">
          <p className={TYPE.eyebrow}>Semantic color (scarce)</p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            {[
              ["Emerald / verified", SEMANTIC.emerald],
              ["Intelligence", SEMANTIC.intelligence],
              ["Signal", SEMANTIC.signal],
              ["Waiting", SEMANTIC.approval],
              ["Failure", SEMANTIC.danger],
            ].map(([label, color]) => (
              <div key={label} className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ background: color }} />
                <span className="text-[color:var(--g-text-muted)]">{label}</span>
              </div>
            ))}
          </div>
        </HarnessSurface>
      </section>

      <HarnessSurface className="p-5">
        <p className={TYPE.eyebrow}>Typography roles</p>
        <div className="mt-4 space-y-3">
          <p className={TYPE.pageTitle}>Page title — Intelligence</p>
          <p className="font-sans text-sm font-semibold text-[color:var(--g-text-primary)]">Object title — HubSpot contact</p>
          <p className={TYPE.body}>Operational body — execution summary for the selected outcome.</p>
          <p className={TYPE.meta}>Metadata · 6m ago · run_01hq8s4m2k</p>
          <p className="font-mono text-[11px] text-[color:var(--g-text-muted)]">TRACE · hubspot.contact.create</p>
        </div>
      </HarnessSurface>

      <HarnessSurface className="p-5">
        <p className={TYPE.eyebrow}>Node · edge · evidence</p>
        <svg viewBox="0 0 480 160" className="mt-4 h-auto w-full">
          <TopologyEdge x1={80} y1={80} x2={200} y2={80} label="delegates" active progress={0.85} reducedMotion={reduced} />
          <TopologyEdge x1={200} y1={80} x2={320} y2={80} label="verified" learned progress={1} reducedMotion={reduced} />
          <TopologyNode x={80} y={80} label="Agent" state="active" reducedMotion={reduced} />
          <TopologyNode x={200} y={80} label="Tool" kind="hub" state="learned" selected reducedMotion={reduced} />
          <TopologyNode x={320} y={80} label="Outcome" state="learned" reducedMotion={reduced} />
        </svg>
        <div className="mt-4 flex flex-wrap gap-2">
          <EvidenceChip label="run outcome" tone="evidence" />
          <EvidenceChip label="policy" tone="waiting" />
          <EvidenceChip label="scope error" tone="error" />
        </div>
      </HarnessSurface>

      <HarnessSurface className="p-5">
        <p className={TYPE.eyebrow}>Motion sample</p>
        <motion.div
          className="mt-4 h-2 w-full overflow-hidden rounded-full bg-[color:var(--g-border-subtle)]"
          aria-hidden
        >
          <motion.div
            className="h-full rounded-full bg-[color:var(--g-signal)]"
            initial={{ width: "0%" }}
            animate={{ width: reduced ? "65%" : ["0%", "65%", "65%"] }}
            transition={
              reduced
                ? { duration: 0 }
                : { duration: MOTION.ui, repeat: Infinity, repeatDelay: 1.2, repeatType: "reverse" }
            }
          />
        </motion.div>
        <p className={cn(TYPE.meta, "mt-2")}>
          {reduced ? "Reduced motion — static progress" : "Event-driven progress — not decorative loop on calm pages"}
        </p>
      </HarnessSurface>
    </div>
  )
}
