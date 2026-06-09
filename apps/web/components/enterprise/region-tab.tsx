"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Globe, Copy, Check, AlertTriangle, ShieldCheck, Lock } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseDataRegion, EnterpriseRegion } from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

const REGIONS: { id: EnterpriseRegion; label: string; sub: string; flag: string }[] = [
  { id: "us", label: "United States", sub: "us-east-1 · N. Virginia", flag: "US" },
  { id: "eu", label: "European Union", sub: "eu-central-1 · Frankfurt", flag: "EU" },
]

export function RegionTab({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, mutate } = useSWR<EnterpriseDataRegion>(
    "enterprise-data-region",
    () => enterpriseApi.getDataRegion(),
    { revalidateOnFocus: false },
  )

  const [selected, setSelected] = useState<EnterpriseRegion | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingRegion, setPendingRegion] = useState<EnterpriseRegion | null>(null)
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  if (isLoading) return <TabSkeleton rows={2} />

  const currentRegion = data?.region
  const storagePrefix = data?.storagePrefix ?? ""
  const activeRegion = selected ?? currentRegion ?? null

  const handleSelect = (region: EnterpriseRegion) => {
    if (!isAdmin || region === currentRegion) return
    setPendingRegion(region)
    setConfirmOpen(true)
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(storagePrefix)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const confirmChange = async () => {
    if (!pendingRegion) return
    setSaving(true)
    try {
      const updated = await enterpriseApi.updateDataRegion({ region: pendingRegion })
      await mutate(updated, { revalidate: false })
      setSelected(pendingRegion)
      toast.success(`Data region updated to ${pendingRegion.toUpperCase()}`)
      setConfirmOpen(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update region")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Globe className="h-4 w-4 text-primary" />
            <CardTitle className="text-base">Data residency</CardTitle>
          </div>
          <CardDescription>
            Choose where your organization&apos;s data is stored at rest. All run artifacts, memory, and
            connector tokens are pinned to this region.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {REGIONS.map((region) => {
              const active = activeRegion === region.id
              return (
                <button
                  key={region.id}
                  type="button"
                  onClick={() => handleSelect(region.id)}
                  disabled={!isAdmin}
                  aria-pressed={active}
                  className={cn(
                    "flex items-center gap-3 rounded-lg border p-4 text-left transition-all duration-150",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                      : "border-border hover:border-primary/40 hover:bg-secondary/40",
                    !isAdmin && "cursor-not-allowed opacity-70",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-xs font-semibold",
                      active ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground",
                    )}
                  >
                    {region.flag}
                  </span>
                  <span className="flex-1">
                    <span className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{region.label}</span>
                      {currentRegion === region.id && (
                        <Badge variant="secondary" className="h-5 gap-1 px-1.5 text-[10px]">
                          <ShieldCheck className="h-3 w-3" /> Active
                        </Badge>
                      )}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">{region.sub}</span>
                  </span>
                </button>
              )
            })}
          </div>

          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Storage prefix
            </span>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded-md border border-border bg-secondary/50 px-3 py-2 font-mono text-xs text-foreground">
                {storagePrefix || "—"}
              </code>
              <Button
                variant="outline"
                size="icon"
                onClick={handleCopy}
                disabled={!storagePrefix}
                aria-label="Copy storage prefix"
              >
                {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          {!isAdmin && (
            <Alert>
              <Lock className="h-4 w-4" />
              <AlertTitle>Read-only</AlertTitle>
              <AlertDescription>
                Only organization admins can change the data region. Contact your administrator to
                request a change.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              Change data region?
            </DialogTitle>
            <DialogDescription className="space-y-2 pt-1">
              <span className="block">
                Moving to{" "}
                <strong className="text-foreground">{pendingRegion?.toUpperCase()}</strong> changes
                where new data is stored.
              </span>
              <span className="block">
                Connector tokens are pinned per-region and may need to be re-authorized. Existing data
                is not migrated automatically.
              </span>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={confirmChange} disabled={saving}>
              {saving ? "Updating…" : "Confirm change"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
