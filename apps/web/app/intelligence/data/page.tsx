"use client"

import { Suspense } from "react"
import { PAGE_FRAME, TYPE } from "@/lib/design-system"
import { AppShell } from "@/components/gravitre/app-shell"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { ExternalDatasetsSection } from "@/components/intelligence/external-datasets-section"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { TrainingWorkbench } from "@/components/training/training-workbench"
import { useAuth } from "@/lib/auth-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cn } from "@/lib/utils"

/**
 * Intelligence › Data: every dataset Gravitre can learn from, in one place.
 * Public datasets (Hugging Face, Kaggle) and your own datasets used to live in
 * Model Studio's Train step and on Agents › Training respectively.
 */
export default function IntelligenceDataPage() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.intelligenceData

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to manage datasets." />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME} data-composition="create">
        <GravitrePageHeader
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <AskGravitreSummonButton
              label="Find the right data"
              prompt="Help me choose datasets for what I want my agents or models to learn. Separate my own data from public datasets and say what each would be used for."
            />
          }
        />
        <IntelligenceShell activeTab="data" loadState="READY">
          <div className="space-y-10 pt-6">
            <section aria-labelledby="data-public-heading" className="space-y-3">
              <div>
                <h2 id="data-public-heading" className={TYPE.sectionTitle}>
                  Public datasets
                </h2>
                <p className={cn(TYPE.meta, "mt-0.5")}>{copy.publicDescription}</p>
              </div>
              <ExternalDatasetsSection enabled={Boolean(user)} source="intelligence_data" showHeading={false} />
            </section>

            <section id="yours" aria-labelledby="data-yours-heading" className="scroll-mt-24 space-y-3">
              <div>
                <h2 id="data-yours-heading" className={TYPE.sectionTitle}>
                  Your datasets
                </h2>
                <p className={cn(TYPE.meta, "mt-0.5")}>{copy.yoursDescription}</p>
              </div>
              <Suspense fallback={<p className={TYPE.bodyMuted}>Loading datasets…</p>}>
                <TrainingWorkbench embedded section="datasets" />
              </Suspense>
            </section>
          </div>
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
