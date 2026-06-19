"use client"

import { useSyncExternalStore } from "react"
import Link from "next/link"
import { ArrowLeft, Building2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  getPlatformOrgViewState,
  getSelectedOrgFromStorage,
  navigateFromPlatformOrgView,
} from "@/lib/org-context"

function subscribePlatformOrgView(onStoreChange: () => void) {
  if (typeof window === "undefined") return () => {}
  const handler = () => onStoreChange()
  window.addEventListener("storage", handler)
  return () => window.removeEventListener("storage", handler)
}

function getPlatformViewSnapshot() {
  if (typeof window === "undefined") return null
  const view = getPlatformOrgViewState()
  if (!view?.active) return null
  const org = getSelectedOrgFromStorage()
  if (!org?.id) return null
  return { org, returnPath: view.returnPath ?? "/platform/cs-workspace" }
}

export function PlatformOrgViewBanner() {
  const snapshot = useSyncExternalStore(
    subscribePlatformOrgView,
    getPlatformViewSnapshot,
    () => null,
  )

  if (!snapshot) return null

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-violet-500/30 bg-violet-500/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3 min-w-0">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-violet-500/10">
          <Building2 className="h-4 w-4 text-violet-600" />
        </div>
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-foreground">
            Viewing tenant: {snapshot.org.name}
          </p>
          <p className="text-xs text-muted-foreground text-pretty">
            Platform operator view — actions apply to this organization via{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">x-org-id</code>.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 shrink-0">
        <Button variant="outline" size="sm" asChild>
          <Link href={snapshot.returnPath}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            CS workspace
          </Link>
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigateFromPlatformOrgView(snapshot.returnPath)}
        >
          Exit tenant view
        </Button>
      </div>
    </div>
  )
}
