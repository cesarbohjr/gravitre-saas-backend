"use client"

import { useState } from "react"
import { toast } from "sonner"
import { enterpriseApi } from "@/lib/api"
import type { ResidencyOverview, ResidencyRegion } from "@/lib/settings-api/enterprise"
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
import { Icon, Pill, TONE } from "./ts-ui"

type ResidencyData = { data?: ResidencyOverview; error?: unknown; mutate: () => Promise<unknown> }

/**
 * Data residency from /api/enterprise/insights/residency. Only the region this
 * deployment runs in stores data; another region is arranged with Gravitre
 * support, so it shows Not available.
 */
export function TrustSafetyResidency({ residency }: { residency: ResidencyData }) {
  const { data, error, mutate } = residency
  const [copied, setCopied] = useState(false)
  const [pending, setPending] = useState<ResidencyRegion | null>(null)
  const [saving, setSaving] = useState(false)

  const copyPrefix = async () => {
    if (!data?.storagePrefix) return
    try {
      await navigator.clipboard.writeText(data.storagePrefix)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Could not copy the storage prefix")
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
      <div className="ts-sechead" style={{ marginTop: 8 }}>
        <span className="ts-eyebrow">Data residency</span>
        <span style={{ fontSize: 13, color: "#6A6B64" }}>Where run artifacts, memory and connector tokens are stored</span>
      </div>
      <section className="ts-card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
          <span className="ts-ico blue"><Icon name="globe" /></span>
          <div style={{ flex: "1 1 300px", minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 16 }}>Where your data lives</div>
            <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2, lineHeight: 1.5 }}>
              Everything this workspace stores stays in its current region. A region change is arranged with Gravitre support.
            </div>
          </div>
          <a className="ts-btn text sm" href="mailto:support@gravitre.app?subject=Data%20region%20change">Contact support</a>
        </div>
        {error && !data ? (
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", fontSize: 13, color: "#8A2530" }}>
            Data residency did not load.
            <button type="button" className="ts-btn line sm" onClick={() => void mutate()}>Try again</button>
          </div>
        ) : !data ? (
          <div style={{ fontSize: 13, color: "#6A6B64" }} role="status">Loading data residency</div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
              {data.regions.map((region) => {
                const selectable = region.available && !region.current
                const body = (
                  <>
                    <span
                      className="ts-mono"
                      style={{ width: 44, height: 44, borderRadius: 12, background: region.current ? "#EAF7F0" : "#EFEFEA", color: region.current ? "#0A6B47" : "#55564F", display: "grid", placeItems: "center", fontSize: 13, fontWeight: 500, flex: "0 0 auto" }}
                    >
                      {region.id.toUpperCase()}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                        <span style={{ fontWeight: 600 }}>{region.label}</span>
                        {region.current ? (
                          <Pill bg={TONE.ok.bg} fg={TONE.ok.fg} dot="#19C37D" live>Current</Pill>
                        ) : !region.available ? (
                          <Pill bg={TONE.mute.bg} fg={TONE.mute.fg}>Not available</Pill>
                        ) : null}
                      </div>
                      <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 4 }}>
                        {region.current
                          ? region.available
                            ? "Your data is stored here"
                            : "Set for this workspace, but this deployment runs elsewhere. Contact Gravitre support."
                          : region.available
                            ? "This deployment's region"
                            : "Arranged with Gravitre support"}
                      </div>
                    </div>
                  </>
                )
                const style = {
                  border: `1px solid ${region.current ? "#19C37D" : "#E4E4DF"}`,
                  boxShadow: region.current ? "0 0 0 3px rgba(25,195,125,.14)" : undefined,
                  borderRadius: 14,
                  padding: 16,
                  display: "flex",
                  gap: 14,
                  alignItems: "center",
                  background: region.current ? "#FFFFFF" : "#FBFBF9",
                  textAlign: "left" as const,
                  font: "inherit",
                  color: "inherit",
                }
                return selectable ? (
                  <button key={region.id} type="button" style={{ ...style, cursor: "pointer" }} onClick={() => setPending(region)}>
                    {body}
                  </button>
                ) : (
                  <div key={region.id} style={style} aria-current={region.current ? "true" : undefined}>
                    {body}
                  </div>
                )
              })}
            </div>
            <div>
              <div style={{ fontSize: 13, color: "#55564F", marginBottom: 6 }}>Storage prefix</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div
                  className="ts-mono"
                  style={{ flex: 1, minWidth: 0, background: "#F7F7F4", border: "1px solid #EFEFEA", borderRadius: 10, padding: "11px 12px", fontSize: 13, color: "#3E3F3A", overflowWrap: "anywhere" }}
                >
                  {data.storagePrefix}
                </div>
                <button type="button" className="ts-btn line sm" aria-label="Copy storage prefix" onClick={() => void copyPrefix()}>
                  <Icon name="copy" size={15} />
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <AlertDialog open={pending !== null} onOpenChange={(open) => (open ? undefined : setPending(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Set data region to {pending?.label}?</AlertDialogTitle>
            <AlertDialogDescription>
              New data is stored in this region. Existing data is not copied automatically, and connector tokens may need to be
              authorized again.
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
