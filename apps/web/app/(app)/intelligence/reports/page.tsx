"use client"

import { Suspense, useEffect, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"
import useSWR from "swr"
import { toast } from "@/components/intelligence/overlays/toast"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { ReportsStage } from "@/components/intelligence/pages/reports-stage"
import { REPORT_PERIODS, type ReportPeriodDays } from "@/components/intelligence/reports/report-model"
import { intelligenceReportsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { INTELLIGENCE_PAGE_FRAME } from "@/lib/design-system"
import { ApiError } from "@/lib/fetcher"
import {
  REPORT_TEMPLATES,
  clearLocalSavedIntelligenceViews,
  readSavedIntelligenceViews,
  type ReportTemplateId,
  type SavedIntelligenceView,
} from "@/lib/intelligence/saved-intelligence-views"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

const copy = SURFACE_COPY.pages.reports

const VIEWS_KEY = "intelligence/reports/views"

function templateFromParam(value: string | null): ReportTemplateId | null {
  return REPORT_TEMPLATES.find((t) => t.id === value)?.id ?? null
}

function periodFromParam(value: string | null): ReportPeriodDays | null {
  const days = Number(value)
  return REPORT_PERIODS.find((p) => p.days === days)?.days ?? null
}

function IntelligenceReportsInner() {
  const { user } = useAuth()
  const searchParams = useSearchParams()
  // A scheduled report email links to /intelligence/reports?template=…&period=…
  const [template, setTemplate] = useState<ReportTemplateId>(() => templateFromParam(searchParams.get("template")) ?? "business")
  const [periodDays, setPeriodDays] = useState<ReportPeriodDays>(() => periodFromParam(searchParams.get("period")) ?? 30)
  const [saving, setSaving] = useState(false)
  const scheduleRef = useRef<HTMLElement>(null)

  // Saved views are shared with everyone in the organization.
  const viewsQuery = useSWR(user ? VIEWS_KEY : null, () => intelligenceReportsApi.listViews(), {
    revalidateOnFocus: false,
  })
  const savedViews: SavedIntelligenceView[] = viewsQuery.data?.views ?? []

  // Views an older version kept in this browser move to the server once.
  const migrated = useRef(false)
  useEffect(() => {
    if (migrated.current || !viewsQuery.data) return
    migrated.current = true
    const orgId = getSelectedOrgFromStorage()?.id ?? null
    const local = readSavedIntelligenceViews(orgId)
    if (!orgId || local.length === 0) return
    void Promise.allSettled(
      local.map((view) =>
        intelligenceReportsApi.saveView({ templateId: view.templateId, periodDays: view.periodDays, label: view.label }),
      ),
    ).then((results) => {
      if (results.every((r) => r.status === "fulfilled")) clearLocalSavedIntelligenceViews(orgId)
      void viewsQuery.mutate()
    })
  }, [viewsQuery])

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

  async function saveView() {
    if (saving) return
    const label = `${REPORT_TEMPLATES.find((t) => t.id === template)?.label ?? "Report"} · ${periodDays} days`
    setSaving(true)
    try {
      await intelligenceReportsApi.saveView({ templateId: template, periodDays, label })
      await viewsQuery.mutate()
      toast.success(`Saved ${label}`, { description: "Everyone in your organization can open it from Saved views." })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save this view.")
    } finally {
      setSaving(false)
    }
  }

  function loadView(view: SavedIntelligenceView) {
    setTemplate(view.templateId)
    setPeriodDays(view.periodDays)
  }

  async function removeView(viewId: string) {
    try {
      await intelligenceReportsApi.deleteView(viewId)
      await viewsQuery.mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove this view.")
    }
  }

  function openSchedule() {
    const section = scheduleRef.current
    if (!section) return
    section.scrollIntoView({ behavior: "smooth", block: "center" })
    section.querySelector<HTMLElement>("select, button")?.focus({ preventScroll: true })
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
      <div className={INTELLIGENCE_PAGE_FRAME}>
        <GravitrePageHeader
          eyebrow={copy.eyebrow}
          titleScale="display"
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <>
              <Button variant="outline" size="sm" onClick={openSchedule}>
                Schedule
              </Button>
              <Button size="sm" onClick={() => void saveView()} disabled={saving}>
                {saving ? "Saving…" : "Save this view"}
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
            savedViewsLoading={viewsQuery.isLoading}
            savedViewsError={viewsQuery.error ? "Saved views couldn't be loaded. Try again in a moment." : null}
            canSave={Boolean(user) && !saving}
            onSaveView={() => void saveView()}
            onLoadView={loadView}
            onRemoveView={(id) => void removeView(id)}
            scheduleRef={scheduleRef}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}

export default function IntelligenceReportsPage() {
  return (
    <Suspense fallback={null}>
      <IntelligenceReportsInner />
    </Suspense>
  )
}
