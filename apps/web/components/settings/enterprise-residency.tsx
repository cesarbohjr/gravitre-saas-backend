"use client"

/**
 * Enterprise > Data residency (design p18). Region cards come from
 * GET /api/enterprise/insights/residency: the org's region, and which region
 * this deployment actually stores data in. Data is not copied between regions
 * by the app, so a region this deployment does not run in shows Not available
 * and the copy says a change is arranged with Gravitre support. The existing
 * PUT /api/enterprise/data-region stays for setting the org to the region it
 * really runs in.
 */
import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Check, Copy, Globe } from "lucide-react"
import { enterpriseApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { RESIDENCY_KEY, type ResidencyOverview, type ResidencyRegion } from "@/lib/settings-api/enterprise"
import type { EnterpriseRegion } from "@/types/api"
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
import { SetError, SetNote, SetPill, SetSkeleton } from "./settings-kit"

export function EnterpriseResidency({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<ResidencyOverview>(RESIDENCY_KEY, fetcher, { revalidateOnFocus: false })
  const [pending, setPending] = useState<ResidencyRegion | null>(null)
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  const copyPrefix = async () => {
    if (!data?.storagePrefix) return
    try {
      await navigator.clipboard.writeText(data.storagePrefix)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error("Could not copy")
    }
  }

  const confirmChange = async () => {
    if (!pending) return
    setSaving(true)
    try {
      await enterpriseApi.updateDataRegion({ region: pending.id as EnterpriseRegion })
      await mutate()
      toast.success(`Data region set to ${pending.label}`)
      setPending(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update the region")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <section className="gs-card ent-card" style={{ padding: 20 }}>
        <div className="ent-title">
          <Globe size={17} aria-hidden />
          <h3 style={{ fontSize: 16 }}>Where your data lives</h3>
        </div>
        <p className="ent-card-sub" style={{ marginBottom: 14 }}>
          {data?.migrationSupported
            ? "Pick a primary region. Moving regions copies data first, then switches."
            : "Run artifacts, memory and connector tokens are stored in your current region. A region change is arranged with Gravitre support."}
        </p>
        {error && !data ? (
          <SetError message="Data residency did not load." onRetry={() => void mutate()} />
        ) : isLoading || !data ? (
          <SetSkeleton rows={2} label="Loading data residency" />
        ) : (
          <>
            <div className="ent-regions">
              {data.regions.map((region) => {
                const selectable = isAdmin && region.available && !region.current
                return (
                  <button
                    key={region.id}
                    type="button"
                    className="gs-wcard ent-region"
                    aria-pressed={region.current}
                    disabled={!selectable}
                    onClick={() => (selectable ? setPending(region) : undefined)}
                  >
                    <span style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
                      <b>{region.label}</b>
                      {region.current ? (
                        <SetPill tone="green">Current</SetPill>
                      ) : !region.available ? (
                        <SetPill>Not available</SetPill>
                      ) : null}
                    </span>
                    <span>
                      {region.current
                        ? region.available
                          ? "Your data is stored here."
                          : "Set for your workspace, but this deployment runs elsewhere. Contact Gravitre support."
                        : region.available
                          ? "This deployment's region."
                          : "Arranged with Gravitre support."}
                    </span>
                  </button>
                )
              })}
            </div>
            <div className="gs-field" style={{ marginTop: 16 }}>
              Storage prefix
              <div className="ent-hex">
                <code className="gs-mono" style={{ flex: 1, minWidth: 0, overflowWrap: "anywhere", background: "var(--gs-tile)", borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
                  {data.storagePrefix}
                </code>
                <button type="button" className="gs-iconbtn" onClick={() => void copyPrefix()} aria-label="Copy storage prefix">
                  {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
                </button>
              </div>
            </div>
          </>
        )}
      </section>
      {!isAdmin ? <SetNote>Only workspace admins can change data residency.</SetNote> : null}

      <AlertDialog open={pending !== null} onOpenChange={(open) => (open ? undefined : setPending(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Set data region to {pending?.label}?</AlertDialogTitle>
            <AlertDialogDescription>
              New data is stored in this region. Existing data is not copied automatically, and connector tokens may need
              to be authorized again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={saving}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={saving}
              onClick={(event) => {
                event.preventDefault()
                void confirmChange()
              }}
            >
              {saving ? "Saving…" : "Set region"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
