"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { mspDelegationsApi, type MspGrantResult } from "@/lib/msp-delegations"

/** Explicitly opt-in customer-owner controls. No inferred MSP access or org switching. */
export function MspDelegationPanel({ customerOrgId }: { customerOrgId: string }) {
  const [providerId, setProviderId] = useState("")
  const [granteeId, setGranteeId] = useState("")
  const [grant, setGrant] = useState<MspGrantResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [revoked, setRevoked] = useState(false)

  async function createGrant() {
    if (!providerId.trim() || !granteeId.trim()) {
      toast.error("Provider organization and provider member are required")
      return
    }
    if (!window.confirm("Approve account health access for this specific provider member for one hour?")) return
    setBusy(true)
    try {
      const result = await mspDelegationsApi.create({
        provider_org_id: providerId.trim(),
        customer_org_id: customerOrgId,
        grantee_user_id: granteeId.trim(),
        tier: 1,
        actions: ["account.health.read"],
        expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      })
      setGrant(result)
      setRevoked(false)
      toast.success("Delegation stored; access is not activated")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not store delegation")
    } finally {
      setBusy(false)
    }
  }

  async function revokeGrant() {
    if (!grant || !window.confirm("Revoke this delegation immediately?")) return
    setBusy(true)
    try {
      await mspDelegationsApi.revoke(grant.id, customerOrgId)
      setRevoked(true)
      toast.success("Delegation revoked")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Revocation failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="msp-delegation-heading" className="mt-5 space-y-3 border-t border-divide pt-4">
      <h3 id="msp-delegation-heading" className="text-sm font-semibold text-foreground">Managed service provider access</h3>
      <p className="text-xs text-muted-foreground">
        Customer-owner approval only. This limited grant allows account-health visibility,
        not conversations, documents, billing details, or organization switching.
      </p>
      <div className="space-y-2">
        <Label htmlFor="msp-provider-org">Provider organization ID</Label>
        <Input id="msp-provider-org" value={providerId} onChange={(event) => setProviderId(event.target.value)} placeholder="Provider UUID" disabled={busy} />
        <Label htmlFor="msp-grantee">Provider member ID</Label>
        <Input id="msp-grantee" value={granteeId} onChange={(event) => setGranteeId(event.target.value)} placeholder="Member UUID" disabled={busy} />
      </div>
      <p className="text-xs text-muted-foreground">Scope: account.health.read · Expires after one hour</p>
      <Button type="button" size="sm" disabled={busy || !providerId.trim() || !granteeId.trim()} onClick={() => void createGrant()}>
        Approve limited access
      </Button>
      {grant && (
        <div role="status" className="space-y-2 rounded-md border border-divide p-3">
          <p className="text-xs font-medium">{revoked ? "Revoked" : "Stored, not activated"}</p>
          <p className="break-all text-xs text-muted-foreground">Grant ID: {grant.id}</p>
          {!revoked && (
            <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => void revokeGrant()}>
              Revoke grant
            </Button>
          )}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Existing grants and audit history require a customer-scoped listing API before general availability.
      </p>
    </section>
  )
}
