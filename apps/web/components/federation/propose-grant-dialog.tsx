"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Loader2,
  Plug,
  ShieldCheck,
} from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { connectorsApi, federationApi } from "@/lib/api"
import { readActions } from "@/lib/connector-actions"
import type { FederationPartnership } from "@/types/api"

const CONSENT_TERMS = [
  "The partner organization must accept this grant before any connector actions run in their org.",
  "Only read-only connector actions are permitted for federated grants.",
  "The partner can decline or you can revoke an active grant at any time.",
]

export function ProposeGrantDialog({
  open,
  onOpenChange,
  onCreated,
  disabled,
  activePartnerships,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
  disabled?: boolean
  activePartnerships: FederationPartnership[]
}) {
  const [step, setStep] = useState(0)
  const [granteeOrgId, setGranteeOrgId] = useState("")
  const [connectorId, setConnectorId] = useState("")
  const [selectedActions, setSelectedActions] = useState<string[]>([])
  const [label, setLabel] = useState("")
  const [expiresInHours, setExpiresInHours] = useState("24")
  const [acknowledged, setAcknowledged] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const { data: connectorsData, isLoading: loadingConnectors } = useSWR(
    open ? "federation/propose-grant/connectors" : null,
    () => connectorsApi.list(),
  )

  const connectors = useMemo(() => connectorsData?.connectors ?? [], [connectorsData])
  const selectedConnector = useMemo(
    () => connectors.find((c) => c.id === connectorId),
    [connectors, connectorId],
  )

  const { data: catalogData, isLoading: loadingCatalog } = useSWR(
    open && selectedConnector?.vendor
      ? ["federation/propose-grant/catalog", selectedConnector.vendor]
      : null,
    () => connectorsApi.actionCatalogForVendor(selectedConnector!.vendor),
  )

  const readOnlyActions = useMemo(() => {
    if (!catalogData) return []
    return readActions(catalogData).map((action) => action.tool)
  }, [catalogData])

  function reset() {
    setStep(0)
    setGranteeOrgId("")
    setConnectorId("")
    setSelectedActions([])
    setLabel("")
    setExpiresInHours("24")
    setAcknowledged(false)
    setSubmitting(false)
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset()
    onOpenChange(next)
  }

  function toggleAction(action: string) {
    setSelectedActions((prev) =>
      prev.includes(action) ? prev.filter((item) => item !== action) : [...prev, action],
    )
  }

  const expiresHours = Number.parseInt(expiresInHours, 10)
  const validExpiry = Number.isFinite(expiresHours) && expiresHours >= 1 && expiresHours <= 168
  const canContinue =
    Boolean(granteeOrgId) &&
    Boolean(connectorId) &&
    selectedActions.length > 0 &&
    validExpiry

  async function submit() {
    if (!acknowledged || disabled || !canContinue) return
    setSubmitting(true)
    try {
      await federationApi.proposeConnectorGrant({
        granteeOrgId,
        connectorId,
        allowedActions: selectedActions,
        label: label.trim() || undefined,
        expiresInHours: expiresHours,
      })
      toast.success("Connector grant proposed", {
        description: "Your partner must accept before read-only actions are available.",
      })
      onCreated()
      handleOpenChange(false)
    } catch (err) {
      toast.error("Could not propose grant", {
        description: err instanceof Error ? err.message : "Verify the partnership and connector.",
      })
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plug className="h-5 w-5 text-primary" />
            Propose connector grant
          </DialogTitle>
          <DialogDescription>
            Share read-only access to one of your connectors with an active partner organization.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          {[0, 1].map((s) => (
            <div key={s} className="flex flex-1 items-center gap-2">
              <div
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium transition-colors",
                  step >= s
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {step > s ? <Check className="h-3.5 w-3.5" /> : s + 1}
              </div>
              <div
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors",
                  step > s ? "bg-primary" : "bg-muted",
                )}
              />
            </div>
          ))}
        </div>

        {step === 0 && (
          <div className="space-y-4 py-2">
            {activePartnerships.length === 0 ? (
              <p className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                You need at least one active partnership before proposing a connector grant.
              </p>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="grant-partner">Partner organization</Label>
                  <Select value={granteeOrgId} onValueChange={setGranteeOrgId}>
                    <SelectTrigger id="grant-partner" className="w-full">
                      <SelectValue placeholder="Select an active partner" />
                    </SelectTrigger>
                    <SelectContent>
                      {activePartnerships.map((partnership) => (
                        <SelectItem key={partnership.id} value={partnership.partnerOrgId}>
                          <span className="flex items-center gap-2">
                            <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="font-mono text-xs">{partnership.partnerOrgId}</span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="grant-connector">Connector</Label>
                  <Select
                    value={connectorId}
                    onValueChange={(value) => {
                      setConnectorId(value)
                      setSelectedActions([])
                    }}
                    disabled={loadingConnectors}
                  >
                    <SelectTrigger id="grant-connector" className="w-full">
                      <SelectValue placeholder={loadingConnectors ? "Loading connectors…" : "Select connector"} />
                    </SelectTrigger>
                    <SelectContent>
                      {connectors.map((connector) => (
                        <SelectItem key={connector.id} value={connector.id}>
                          {connector.name} · {connector.vendor}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {connectorId ? (
                  <div className="space-y-2">
                    <Label>Read-only actions</Label>
                    {loadingCatalog ? (
                      <p className="text-xs text-muted-foreground">Loading action catalog…</p>
                    ) : readOnlyActions.length === 0 ? (
                      <p className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                        No read-only actions found for this connector vendor.
                      </p>
                    ) : (
                      <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                        {readOnlyActions.map((action) => (
                          <label
                            key={action}
                            className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50"
                          >
                            <input
                              type="checkbox"
                              checked={selectedActions.includes(action)}
                              onChange={() => toggleAction(action)}
                              className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
                            />
                            <span className="font-mono text-[11px] leading-relaxed">{action}</span>
                          </label>
                        ))}
                      </div>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Select at least one read-only action the partner may invoke.
                    </p>
                  </div>
                ) : null}

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="grant-label">Label (optional)</Label>
                    <Input
                      id="grant-label"
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      placeholder="e.g. HubSpot read for renewal desk"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="grant-expiry">Expires in (hours)</Label>
                    <Input
                      id="grant-expiry"
                      type="number"
                      min={1}
                      max={168}
                      value={expiresInHours}
                      onChange={(e) => setExpiresInHours(e.target.value)}
                    />
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3 py-2">
            <p className="text-sm font-medium">Consent before exchange</p>
            <ul className="space-y-2">
              {CONSENT_TERMS.map((term) => (
                <li key={term} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-chart-1" />
                  <span className="leading-relaxed">{term}</span>
                </li>
              ))}
            </ul>
            <label className="mt-2 flex cursor-pointer items-start gap-2 rounded-lg border border-border bg-muted/30 p-3">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => setAcknowledged(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
              />
              <span className="text-sm">
                I authorize proposing read-only connector access to partner org{" "}
                <span className="font-mono text-foreground">{granteeOrgId}</span>.
              </span>
            </label>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          {step === 0 ? (
            <Button
              className="gap-1.5"
              disabled={!canContinue || disabled || activePartnerships.length === 0}
              onClick={() => setStep(1)}
            >
              Continue
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            <>
              <Button variant="outline" className="gap-1.5" onClick={() => setStep(0)}>
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <Button
                className="gap-1.5"
                disabled={!acknowledged || submitting || disabled}
                onClick={submit}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="h-4 w-4" />
                )}
                {submitting ? "Proposing…" : "Propose grant"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
