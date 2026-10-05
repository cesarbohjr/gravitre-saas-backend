"use client"

import { useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { marketplaceApi } from "@/lib/api"
import { History } from "lucide-react"
import { toast } from "sonner"

export function AssetVersionHistory({
  slug,
  disabled,
  onRolledBack,
  onRestore,
}: {
  slug: string
  disabled?: boolean
  onRolledBack?: () => Promise<void>
  onRestore?: (version: number) => Promise<void>
}) {
  const { data, error, isLoading, mutate } = useSWR(
    slug ? `marketplace-asset-versions:${slug}` : null,
    () => marketplaceApi.listAssetVersions(slug),
  )
  const [target, setTarget] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  const lock = useRef(false)
  const versions = data?.versions ?? []
  async function restore() {
    if (target === null || disabled || lock.current) return
    lock.current = true
    setBusy(true)
    setFailure(null)
    try {
      if (onRestore) await onRestore(target)
      else await marketplaceApi.rollbackAssetVersion(slug, target)
      toast.success(`Restored version ${target}`)
      setTarget(null)
      await Promise.allSettled([mutate(), onRolledBack?.()])
    } catch (err) {
      setFailure(
        err instanceof Error
          ? err.message
          : "Restore failed. The selected snapshot is retained for retry.",
      )
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  return (
    <details className="border-t border-[color:var(--g-border-subtle)] py-2 [&_[data-slot=button]]:min-h-11">
      <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">
        <History className="mr-2 inline size-4" aria-hidden />
        Version history ·{" "}
        {data?.currentVersion == null
          ? "Not reported"
          : `v${data.currentVersion}`}
      </summary>
      {isLoading && !data ? (
        <p role="status" className="py-3 text-sm">
          Loading snapshots…
        </p>
      ) : null}
      {error ? (
        <div role="alert" className="space-y-2 py-3 text-sm">
          <p>
            Could not refresh version history. Loaded snapshots remain
            available.
          </p>
          <Button variant="outline" onClick={() => void mutate()}>
            Retry history
          </Button>
        </div>
      ) : null}
      {data && !versions.length ? (
        <p className="py-3 text-sm text-muted-foreground">
          No snapshots returned.
        </p>
      ) : null}
      <ul className="divide-y divide-border">
        {versions.map((version) => (
          <li
            key={version.versionNumber}
            className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
          >
            <div className="min-w-0">
              <span className="font-medium">v{version.versionNumber}</span>
              {version.isCurrent ? (
                <Badge className="ml-2">current</Badge>
              ) : null}
              {version.changeSummary ? (
                <p className="break-words text-xs text-muted-foreground">
                  {version.changeSummary}
                </p>
              ) : null}
            </div>
            {!version.isCurrent ? (
              <Button
                variant="outline"
                disabled={disabled || busy}
                onClick={() => {
                  setTarget(version.versionNumber)
                  setFailure(null)
                }}
              >
                Restore
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {target !== null ? (
        <section
          aria-label="Confirm version restore"
          className="space-y-3 border-l-2 border-[color:var(--g-warmth)] pl-4 py-3"
        >
          <h4 className="text-sm font-medium">Restore version {target}?</h4>
          <p className="text-sm text-muted-foreground">
            The live asset configuration will match this snapshot. Review the
            version before replacing the current configuration.
          </p>
          {failure ? (
            <p role="alert" className="text-sm text-destructive">
              {failure}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button disabled={disabled || busy} onClick={() => void restore()}>
              {busy ? "Restoring…" : `Confirm restore v${target}`}
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setTarget(null)
                setFailure(null)
              }}
            >
              Keep current version
            </Button>
          </div>
        </section>
      ) : null}
    </details>
  )
}
