"use client"

import { useEffect, useState } from "react"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { ReportsStage } from "@/components/intelligence/pages/reports-stage"
import type { ReportPeriodDays } from "@/components/intelligence/reports/report-model"
import { SCHEDULE_UNAVAILABLE_REASON } from "@/components/intelligence/reports/scheduled-reports-panel"
import { useAuth } from "@/lib/auth-context"
import { PAGE_FRAME } from "@/lib/design-system"
import { ApiError } from "@/lib/fetcher"
import {
  REPORT_TEMPLATES,
  deleteSavedIntelligenceView,
  readSavedIntelligenceViews,
  saveIntelligenceView,
  type ReportTemplateId,
  type SavedIntelligenceView,
} from "@/lib/intelligence/saved-intelligence-views"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

const copy = SURFACE_COPY.pages.reports

export default function IntelligenceReportsPage() {
  const { user } = useAuth()
  const [orgId, setOrgId] = useState<string | null>(null)
  const [template, setTemplate] = useState<ReportTemplateId>("business")
  const [periodDays, setPeriodDays] = useState<ReportPeriodDays>(30)
  const [savedViews, setSavedViews] = useState<SavedIntelligenceView[]>([])

  // Org and saved views live in browser storage; read them after mount to keep hydration stable.
  useEffect(() => {
    const id = getSelectedOrgFromStorage()?.id ?? null
    setOrgId(id)
    setSavedViews(readSavedIntelligenceViews(id))
  }, [])

  const {
    data: pageContext,
    error,
    loadState,
    generatedAt,
    isValidating,
    mutate,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user),
    activeLens: "improves",
    // The snapshot API caps its window at 7 days; the stage says so when the period is longer.
    windowHours: periodDays * 24,
    swrKeySuffix: "reports",
  })

  /** The org can resolve after mount, so read it again when the user acts. */
  function resolveOrgId(): string | null {
    const id = orgId ?? getSelectedOrgFromStorage()?.id ?? null
    if (id && id !== orgId) setOrgId(id)
    return id
  }

  function saveView() {
    const id = resolveOrgId()
    if (!id) {
      toast.error("Pick an organization first. Views are saved per organization.")
      return
    }
    const label = `${REPORT_TEMPLATES.find((t) => t.id === template)?.label ?? "Report"} · ${periodDays} days`
    try {
      setSavedViews(saveIntelligenceView(id, { label, templateId: template, periodDays }))
      toast.success(`Saved ${label}`)
    } catch {
      toast.error("Could not save this view in this browser.")
    }
  }

  function loadView(view: SavedIntelligenceView) {
    setTemplate(view.templateId)
    setPeriodDays(view.periodDays)
  }

  function removeView(viewId: string) {
    const id = resolveOrgId()
    if (!id) return
    try {
      setSavedViews(deleteSavedIntelligenceView(id, viewId))
    } catch {
      toast.error("Could not remove this view.")
    }
  }

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view reports." />
      </AppShell>
    )
  }

  if (error && !pageContext) {
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load reports"
          description={error instanceof ApiError ? error.message : "Please try again."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME}>
        <GravitrePageHeader
          eyebrow={copy.eyebrow}
          titleScale="display"
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <>
              <Button variant="outline" size="sm" disabled title={SCHEDULE_UNAVAILABLE_REASON}>
                Schedule
              </Button>
              <Button
                size="sm"
                onClick={saveView}
              >
                Save this view
              </Button>
            </>
          }
        />
        <IntelligenceShell
          activeTab="reports"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
        >
          <ReportsStage
            pageContext={pageContext}
            loadState={loadState}
            generatedAt={generatedAt}
            isValidating={isValidating}
            onRefresh={() => mutate()}
            enabled={Boolean(user)}
            template={template}
            onTemplateChange={setTemplate}
            periodDays={periodDays}
            onPeriodChange={setPeriodDays}
            savedViews={savedViews}
            canSave={Boolean(user)}
            onSaveView={saveView}
            onLoadView={loadView}
            onRemoveView={removeView}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
