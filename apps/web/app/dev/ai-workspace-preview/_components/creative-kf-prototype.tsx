"use client"

/**
 * Harness-only: Pilot 3 storyboard vs stable KF-A vs refined KF-A preview.
 * Production /features/technology stays on the stable workbench until Cesar confirms promote.
 */

import { EntityConvergenceField } from "@/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-field"
import { EntityConvergenceWorkbench } from "@/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench"
import { EntityConvergenceWorkbenchRefined } from "@/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench-refined"
import { TYPE } from "@/lib/design-system"

export function CreativeKfPrototype({ scene }: { scene: string }) {
  const mode =
    scene === "pilot3"
      ? "pilot3"
      : scene === "workbench"
        ? "workbench"
        : scene === "refined"
          ? "refined"
          : "compare"

  return (
    <div className="space-y-6" data-testid="creative-kf-prototype">
      <div>
        <p className={TYPE.eyebrow}>CES 2.0 · Knowledge Fabric · harness only</p>
        <h2 className={TYPE.sectionTitle}>Entity convergence — Pilot 3 vs KF-A</h2>
        <p className="mt-2 max-w-3xl text-sm text-[color:var(--g-text-secondary)]">
          Stable KF-A remains what Technology mounts today. The refined edition is harness preview only — quiet
          pipeline around a living field; converge + reject together; knowledge persists. Do not treat this route as a
          Technology promote.
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
        <section className="space-y-2" aria-label="KF-A stable workbench">
          <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">
            KF-A stable (Technology today)
          </h3>
          <p className="text-[12px] text-[color:var(--g-text-muted)]">
            STEPPED SceneController · seven beats including late Reject · compare lens
          </p>
          <EntityConvergenceWorkbench />
        </section>
      ) : null}

      {mode === "refined" || mode === "compare" ? (
        <section className="space-y-2" aria-label="KF-A refined preview">
          <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">
            KF-A refined preview (awaiting promote)
          </h3>
          <p className="text-[12px] text-[color:var(--g-text-muted)]">
            Arrive → Normalize → Match → Resolve (converge + reject concurrent) → Evidence → Knowledge persists
          </p>
          <EntityConvergenceWorkbenchRefined />
        </section>
      ) : null}

      {mode === "compare" ? (
        <section
          className="rounded-xl border border-[color:var(--color-line,#eaedf1)] bg-white p-4 text-sm text-[color:var(--g-text-secondary)]"
          data-testid="kf-a-vs-pilot3-notes"
        >
          <h3 className="text-sm font-semibold text-[color:var(--g-text-primary)]">What refined KF-A changes</h3>
          <ul className="mt-2 list-disc space-y-1.5 pl-5">
            <li>Pipeline rail names the knowledge story — not only ← / → chip chrome.</li>
            <li>Rejected person mentions stay separate from Match onward, beside Acme convergence.</li>
            <li>Evidence attaches into the resolved identity card.</li>
            <li>Terminal Knowledge beat keeps structure visible; Fragmented is an optional peek.</li>
            <li>Technology page is unchanged until an explicit promote confirmation.</li>
          </ul>
        </section>
      ) : null}
    </div>
  )
}
