"use client"

import { Suspense, useRef, useState } from "react"
import Link from "next/link"
import { PAGE_FRAME, TYPE } from "@/lib/design-system"
import { AppShell } from "@/components/gravitre/app-shell"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { FindDataSection } from "@/components/intelligence/data/find-data-section"
import { TrainingDatasetsTable } from "@/components/intelligence/data/training-datasets-table"
import { UploadDatasetDialog } from "@/components/intelligence/data/upload-dataset-dialog"
import { useDataSources, useRefreshDatasets } from "@/components/intelligence/data/use-data-sources"
import { YourDatasetsSection } from "@/components/intelligence/data/your-datasets-section"
import { TrainingWorkbench } from "@/components/training/training-workbench"
import { APP_ROUTES } from "@/lib/app-routes"
import { useAuth } from "@/lib/auth-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cn } from "@/lib/utils"

/**
 * Intelligence › Data: everything Gravitre can learn from. One search across
 * the org's own datasets and public catalogs (Hugging Face, Kaggle), the ways
 * to add your own material, and what each model learned from.
 */
export default function IntelligenceDataPage() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.intelligenceData
  const sources = useDataSources(Boolean(user))
  const refresh = useRefreshDatasets()
  const [uploadOpen, setUploadOpen] = useState(false)
  const [manageOpen, setManageOpen] = useState(false)
  const [focusDataset, setFocusDataset] = useState<{ id: string; nonce: number } | null>(null)
  const manageRef = useRef<HTMLDetailsElement>(null)

  function manageDataset(id: string) {
    setManageOpen(true)
    setFocusDataset((current) => ({ id, nonce: (current?.nonce ?? 0) + 1 }))
    requestAnimationFrame(() => manageRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }))
  }

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to manage datasets." />
      </AppShell>
    )
  }

  const datasets = sources.datasets.data?.datasets ?? []

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME} data-composition="create">
        <GravitrePageHeader
          eyebrow={copy.eyebrow}
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" className="min-h-11" onClick={() => setUploadOpen(true)}>
                Upload a file
              </Button>
              <Button asChild className="min-h-11">
                <Link href={APP_ROUTES.connectors}>Connect a source</Link>
              </Button>
            </div>
          }
        />
        <IntelligenceShell activeTab="data" loadState="READY">
          <div className="space-y-10 pt-6">
            <FindDataSection enabled={Boolean(user)} sources={sources} onManageDataset={manageDataset} />

            <div className="space-y-4">
              <YourDatasetsSection
                datasets={datasets}
                datasetsReady={!sources.datasets.isLoading}
                onUpload={() => setUploadOpen(true)}
                onChanged={() => void refresh()}
              />
              <TrainingDatasetsTable sources={sources} onManageDataset={manageDataset} />
            </div>

            <details
              id="manage-datasets"
              ref={manageRef}
              open={manageOpen}
              onToggle={(event) => setManageOpen((event.currentTarget as HTMLDetailsElement).open)}
              className="group scroll-mt-24 rounded-[var(--g-radius-card)] border border-[color:var(--g-border-subtle)] bg-card"
            >
              <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]">
                <span>
                  <span className={cn(TYPE.cardTitle, "block")}>{copy.manageTitle}</span>
                  <span className={cn(TYPE.meta, "mt-0.5 block")}>{copy.manageDescription}</span>
                </span>
                <span aria-hidden className="text-xs text-[color:var(--g-text-muted)] group-open:rotate-180">▾</span>
              </summary>
              <div className="border-t border-[color:var(--g-border-subtle)] px-5 py-5">
                {manageOpen ? (
                  <Suspense fallback={<p className={TYPE.bodyMuted}>Loading datasets…</p>}>
                    <TrainingWorkbench embedded section="datasets" focusDataset={focusDataset} />
                  </Suspense>
                ) : null}
              </div>
            </details>
          </div>
        </IntelligenceShell>
        <UploadDatasetDialog
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          datasets={datasets}
          onUploaded={() => void refresh()}
        />
      </div>
    </AppShell>
  )
}
