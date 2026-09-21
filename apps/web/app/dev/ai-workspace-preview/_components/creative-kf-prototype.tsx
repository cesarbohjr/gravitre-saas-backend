"use client"

/**
 * Harness-only side-by-side: shipped Pilot 3 storyboard vs KF-A workbench.
 * Production /features/technology is untouched.
 */

import { EntityConvergenceField } from "@/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-field"
import { EntityConvergenceWorkbench } from "@/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench"
import { TYPE } from "@/lib/design-system"

export function CreativeKfPrototype({ scene }: { scene: string }) {
  const mode = scene === "pilot3" ? "pilot3" : scene === "workbench" ? "workbench" : "compare"

  return (
    <div className="space-y-6" data-testid="creative-kf-prototype">
      <div>
        <p className={TYPE.eyebrow}>CES 2.0 · Knowledge Fabric · harness only</p>
        <h2 className={TYPE.sectionTitle}>Entity convergence — Pilot 3 vs KF-A</h2>
        <p className="mt-2 max-w-3xl text-sm text-[color:var(--g-text-secondary)]">
          Production Pilot 3 remains the AUTOPLAY storyboard. KF-A is the interactive workbench prototype for Cesar
          review — not promoted to marketing routes.
        </p>
      </div>

      {mode === "pilot3" || mode === "compare" ? (
        <section className="space-y-2" aria-label="Current Pilot 3">
          <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">Current Pilot 3 (shipped)</h3>
          <p className="text-[12px] text-[color:var(--g-text-muted)]">
            AUTOPLAY phase machine · pre-baked normalized keys · no visitor select / step / replay
          </p>
          <EntityConvergenceField />
        </section>
      ) : null}

      {mode === "workbench" || mode === "compare" ? (
        <section className="space-y-2" aria-label="KF-A interactive prototype">
          <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">
            KF-A interactive prototype
          </h3>
          <p className="text-[12px] text-[color:var(--g-text-muted)]">
            STEPPED SceneController · select mentions · inspect normalize/match/reject · evidence on resolved identity ·
            compare lens
          </p>
          <EntityConvergenceWorkbench />
        </section>
      ) : null}

      {mode === "compare" ? (
        <section
          className="rounded-xl border border-[color:var(--color-line,#eaedf1)] bg-white p-4 text-sm text-[color:var(--g-text-secondary)]"
          data-testid="kf-a-vs-pilot3-notes"
        >
          <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">What KF-A teaches that Pilot 3 does not</h3>
          <ul className="mt-2 list-disc space-y-1.5 pl-5">
            <li>Single structured field — mentions are field nodes, not a chip list beside a diagram.</li>
            <li>Select causes the field to respond (soft ring + ghost twin edge) without restarting the beat.</li>
            <li>Normalize / match / resolve / evidence / reject are lenses on the same objects.</li>
            <li>Compare toggles Fragmented ↔ Resolved in-field — not a second layout.</li>
            <li>Evidence grows on the resolved identity; Sarah path stays spatially separate.</li>
          </ul>
        </section>
      ) : null}
    </div>
  )
}
