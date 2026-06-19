"use client"

import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { marketplaceApi } from "@/lib/api"
import { History, Loader2 } from "lucide-react"
import { toast } from "sonner"

export function AssetVersionHistory({
  slug,
  disabled,
  onRolledBack,
}: {
  slug: string
  disabled?: boolean
  onRolledBack?: () => Promise<void>
}) {
  const { data, error, isLoading, mutate } = useSWR(
    slug ? `marketplace-asset-versions:${slug}` : null,
    () => marketplaceApi.listAssetVersions(slug),
  )

  const versions = data?.versions ?? []
  const currentVersion = data?.currentVersion

  const handleRollback = async (versionNumber: number) => {
    if (
      !window.confirm(
        `Restore version ${versionNumber}? The live asset config will match that snapshot.`,
      )
    ) {
      return
    }
    try {
      await marketplaceApi.rollbackAssetVersion(slug, versionNumber)
      toast.success(`Restored version ${versionNumber}`)
      await mutate()
      await onRolledBack?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rollback failed")
    }
  }

  if (isLoading && !data) {
    return <div className="h-16 animate-pulse rounded-lg border bg-muted/30" />
  }
  if (error) {
    return <p className="text-xs text-destructive">Could not load version history.</p>
  }
  if (versions.length <= 1) {
    return (
      <p className="text-xs text-muted-foreground">
        Version {currentVersion ?? 1} — publish again to create additional snapshots.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <History className="h-3.5 w-3.5" aria-hidden />
        Version history
      </p>
      <ul className="space-y-2">
        {versions.map((version) => (
          <li
            key={version.versionNumber}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/80 px-3 py-2 text-sm"
          >
            <div className="min-w-0">
              <span className="font-medium">v{version.versionNumber}</span>
              {version.isCurrent ? <Badge className="ml-2">current</Badge> : null}
              {version.changeSummary ? (
                <p className="truncate text-xs text-muted-foreground">{version.changeSummary}</p>
              ) : null}
            </div>
            {!version.isCurrent ? (
              <Button
                size="sm"
                variant="outline"
                disabled={disabled}
                onClick={() => handleRollback(version.versionNumber)}
              >
                {disabled ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : "Restore"}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
