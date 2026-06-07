"use client"

import { useState } from "react"
import { Check, Copy, Globe, Loader2, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"

interface DataRegionTabProps {
  isAdmin: boolean
  region: string
  storagePrefix?: string
  isLoading: boolean
  onRegionChange: (region: string) => void
  onSaved: () => Promise<void>
}

const regions = [
  { id: "us", label: "United States", code: "US", description: "US data residency" },
  { id: "eu", label: "European Union", code: "EU", description: "EU data residency" },
] as const

export function DataRegionTab({
  isAdmin,
  region,
  storagePrefix,
  isLoading,
  onRegionChange,
  onSaved,
}: DataRegionTabProps) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingRegion, setPendingRegion] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const saveRegion = async (nextRegion: string) => {
    setSaving(true)
    try {
      await enterpriseApi.updateDataRegion(nextRegion as "us" | "eu")
      toast.success("Data region updated")
      await onSaved()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      toast.error("Failed to update data region")
    } finally {
      setSaving(false)
      setConfirmOpen(false)
      setPendingRegion(null)
    }
  }

  const handleSaveClick = () => {
    if (!isAdmin) return
    setPendingRegion(region)
    setConfirmOpen(true)
  }

  const copyPrefix = async () => {
    if (!storagePrefix) return
    try {
      await navigator.clipboard.writeText(storagePrefix)
      setCopied(true)
      toast.success("Storage prefix copied")
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Could not copy")
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-10 w-40" />
      </div>
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Globe className="h-4 w-4" />
            Data residency
          </CardTitle>
          <CardDescription>
            Pin org storage and workflow execution to US or EU. Connector tokens are stamped to this region on connect.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {regions.map((r) => (
              <button
                key={r.id}
                type="button"
                disabled={!isAdmin}
                onClick={() => onRegionChange(r.id)}
                className={cn(
                  "rounded-xl border p-4 text-left transition-colors",
                  region === r.id
                    ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                    : "border-border bg-secondary/20 hover:bg-secondary/40",
                  !isAdmin && "cursor-not-allowed opacity-70"
                )}
              >
                <div className="flex items-center justify-between">
                  <Badge variant={region === r.id ? "default" : "secondary"}>{r.code}</Badge>
                  {region === r.id && <Check className="h-4 w-4 text-primary" />}
                </div>
                <p className="mt-2 font-medium text-foreground">{r.label}</p>
                <p className="text-xs text-muted-foreground">{r.description}</p>
              </button>
            ))}
          </div>

          {storagePrefix && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">Storage prefix</span>
              <code className="rounded-md bg-background px-2 py-1 font-mono text-xs">{storagePrefix}</code>
              <Button type="button" size="icon" variant="ghost" className="h-7 w-7" onClick={copyPrefix}>
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
            </div>
          )}

          <Alert>
            <AlertTitle>Region change impact</AlertTitle>
            <AlertDescription>
              Changing region affects where new connector credentials are stored. Existing tokens remain in their original region until reconnected.
            </AlertDescription>
          </Alert>

          <Button size="sm" className="gap-2" disabled={!isAdmin || saving} onClick={handleSaveClick}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
            Save region
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Change data region?</AlertDialogTitle>
            <AlertDialogDescription>
              This will set your organization to{" "}
              <strong>{pendingRegion === "eu" ? "European Union (EU)" : "United States (US)"}</strong>. New connector
              tokens will be pinned to this region.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => pendingRegion && saveRegion(pendingRegion)}>Confirm</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
