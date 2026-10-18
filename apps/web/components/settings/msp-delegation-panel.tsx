"use client"

import { useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { mspDelegationsApi, type MspGrant } from "@/lib/msp-delegations"

const fmt = (value: string | null) =>
  value ? new Date(value).toLocaleString() : "—"

function grantStatus(grant: MspGrant): string {
  if (grant.revoked_at) return "Revoked"
  if (new Date(grant.expires_at).getTime() <= Date.now()) return "Expired"
  return "Approved"
}

/** Only rendered to a customer owner, and every API call re-checks ownership. */
export function MspDelegationPanel({ customerOrgId }: { customerOrgId: string }) {
  const [granteeId, setGranteeId] = useState("")
  const [busy, setBusy] = useState(false)
  const { data, error, isLoading, mutate } = useSWR(
    ["msp:management", customerOrgId],
    () => mspDelegationsApi.management(customerOrgId),
  )
  const provider = data?.provider
  const members = data?.provider_members ?? []
  const grants = data?.grants ?? []
  const audit = data?.audit ?? []

  async function createGrant() {
    if (!provider || !granteeId) {
      toast.error("Select a linked provider member")
      return
    }
    if (!window.confirm(
      `Approve one hour of account-health access for provider member ${granteeId}? This does not grant access to conversations or documents.`,
    )) return
    setBusy(true)
    try {
      await mspDelegationsApi.create({
        provider_org_id: provider.id,
        customer_org_id: customerOrgId,
        grantee_user_id: granteeId,
        tier: 1,
        actions: ["account.health.read"],
        expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      })
      setGranteeId("")
      await mutate()
      toast.success("Delegation saved")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create delegation")
    } finally {
      setBusy(false)
    }
  }

  async function revokeGrant(grant: MspGrant) {
    if (!window.confirm(`Revoke delegation ${grant.id}? Active access ends on the next request.`)) return
    setBusy(true)
    try {
      await mspDelegationsApi.revoke(grant.id, customerOrgId)
      await mutate()
      toast.success("Delegation revoked")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Revocation failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="msp-delegation-heading" className="mt-5 min-w-0 space-y-4 border-t border-divide pt-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 id="msp-delegation-heading" className="text-sm font-semibold text-foreground">Managed service provider access</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Customer-owner consent. Each grant is scoped to a provider member, an action, and an expiration.
          </p>
        </div>
        <Button variant="outline" size="sm" disabled={isLoading || busy} onClick={() => void mutate()}>
          Refresh
        </Button>
      </div>

      {isLoading && <p role="status" className="text-xs text-muted-foreground">Loading provider and delegation history…</p>}
      {error && <p role="alert" className="text-xs text-destructive">
        {error instanceof Error ? error.message : "Could not load delegated access"}
      </p>}
      {!isLoading && !error && !provider && (
        <p className="text-xs text-muted-foreground">
          No linked managed-service provider was found for this organization. Delegation is unavailable.
        </p>
      )}
      {provider && (
        <div className="space-y-3 rounded-md border border-divide p-3">
          <div>
            <p className="text-xs font-medium text-foreground">{provider.name}</p>
            <p className="break-all text-xs text-muted-foreground">Linked provider · {provider.id}</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="msp-provider-member">Provider member</Label>
            <select
              id="msp-provider-member"
              className="w-full min-w-0 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              value={granteeId}
              onChange={(event) => setGranteeId(event.target.value)}
              disabled={busy || members.length === 0}
            >
              <option value="">Select a provider member</option>
              {members.map((member) => (
                <option key={member.user_id} value={member.user_id}>
                  {member.role} · {member.user_id}
                </option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              Only members of the linked provider can be selected. Account-health read only · 1 hour.
            </p>
          </div>
          <Button type="button" size="sm" disabled={busy || !granteeId} onClick={() => void createGrant()}>
            Approve limited access
          </Button>
        </div>
      )}

      {!isLoading && !error && (
        <>
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">Delegations</h4>
            {grants.length === 0 ? (
              <p className="text-xs text-muted-foreground">No delegations have been issued for this organization.</p>
            ) : (
              <ul className="space-y-2">
                {grants.map((grant) => (
                  <li key={grant.id} className="min-w-0 rounded-md border border-divide p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-foreground">{grantStatus(grant)}</span>
                      {!grant.revoked_at && (
                        <Button type="button" variant="outline" size="sm" disabled={busy}
                          onClick={() => void revokeGrant(grant)}>Revoke</Button>
                      )}
                    </div>
                    <p className="mt-1 break-all text-xs text-muted-foreground">Member: {grant.grantee_user_id}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Tier {grant.tier} · {grant.actions.join(", ")} · Expires {fmt(grant.expires_at)}
                    </p>
                    {grant.revoked_at && <p className="text-xs text-muted-foreground">Revoked {fmt(grant.revoked_at)}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">Access audit history</h4>
            {audit.length === 0 ? (
              <p className="text-xs text-muted-foreground">No recorded delegation events.</p>
            ) : (
              <ul className="space-y-2">
                {audit.map((event) => (
                  <li key={event.id} className="border-b border-divide pb-2 text-xs">
                    <p className="font-medium text-foreground">{event.action}</p>
                    <p className="text-muted-foreground">{fmt(event.recorded_at)} · Actor {event.actor_user_id}</p>
                    {event.delegation_id && <p className="break-all text-muted-foreground">Grant {event.delegation_id}</p>}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-muted-foreground">Showing the latest 100 grants and audit events. Provider member selection is limited to the first 100 members.</p>
          </div>
        </>
      )}
    </section>
  )
}
