"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { LearningStage } from "@/components/intelligence/pages/learning-stage"
import { MemoryAuditSheet } from "@/components/intelligence/knowledge/memory-audit-sheet"
import {
  knowledgeViewSearch,
  resolveKnowledgeView,
  type KnowledgeView,
} from "@/components/intelligence/knowledge/knowledge-view"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { ApiError } from "@/lib/fetcher"
import { PAGE_FRAME } from "@/lib/design-system"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

/** `?view=` drives the view; `#memory` (and /intelligence/memory) selects Memory. */
function useKnowledgeView(): [KnowledgeView, (view: KnowledgeView) => void] {
  const router = useRouter()
  const pathname = usePathname() ?? "/intelligence/learning"
  const searchParams = useSearchParams()
  const viewParam = searchParams.get("view")
  const [hash, setHash] = useState("")

  useEffect(() => {
    const read = () => setHash(window.location.hash)
    read()
    window.addEventListener("hashchange", read)
    return () => window.removeEventListener("hashchange", read)
  }, [])

  const view = resolveKnowledgeView(viewParam, hash)
  const setView = useCallback(
    (next: KnowledgeView) => {
      setHash("")
      router.replace(`${pathname}${knowledgeViewSearch(searchParams.toString(), next)}`, { scroll: false })
    },
    [router, pathname, searchParams],
  )
  return [view, setView]
}

function IntelligenceLearningInner() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.learning
  const { summonWorkspace } = useGravitreAIWorkspace()
  const [view, setView] = useKnowledgeView()
  const [auditOpen, setAuditOpen] = useState(false)
  const viewCopy = copy.views[view]

  const {
    data: pageContext,
    error,
    loadState,
    generatedAt,
    isValidating,
    mutate,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user),
    activeLens: "learns",
    swrKeySuffix: "learning",
  })

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view business learning insights." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load learning insights."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load learning" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div
        className={cn(PAGE_FRAME, "bg-[color:var(--g-canvas)] px-[var(--np-page-pad-sm)] sm:px-[var(--np-page-pad)]")}
        data-composition="understand"
      >
        <GravitrePageHeader
          eyebrow={copy.eyebrow}
          titleScale="display"
          title={viewCopy.title}
          description={viewCopy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" className="min-h-10" onClick={() => setAuditOpen(true)}>
                Audit trail
              </Button>
              <Button
                className="min-h-10"
                title="Opens Ask Gravitre so you can say what to remember."
                onClick={() =>
                  summonWorkspace({
                    presentation: "compact",
                    composerText: copy.addMemoryPrompt,
                    submit: false,
                  })
                }
              >
                Add a memory
              </Button>
            </div>
          }
        />

        <IntelligenceShell
          activeTab="learning"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
        >
          <LearningStage
            pageContext={pageContext}
            loadState={loadState}
            enabled={Boolean(user)}
            view={view}
            onViewChange={setView}
          />
        </IntelligenceShell>

        <MemoryAuditSheet open={auditOpen} onOpenChange={setAuditOpen} enabled={Boolean(user)} />
      </div>
    </AppShell>
  )
}

export default function IntelligenceLearningPage() {
  return (
    <Suspense fallback={null}>
      <IntelligenceLearningInner />
    </Suspense>
  )
}
