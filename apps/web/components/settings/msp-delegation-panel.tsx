"use client"

import { useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { mspDelegationsApi, type MspAuditEvent, type MspGrant } from "@/lib/msp-delegations"
import { personLabel } from "@/lib/msp-program"

const HEALTH_ACTIONS = ["account.health.read", "billing.summary.read", "usage.aggregate.read"] as const

const DURATIONS = [
  { id: "day", label: "1 day", ms: 24 * 60 * 60 * 1000 },
  { id: "month", label: "30 days", ms: 30 * 24 * 60 * 60 * 1000 },
  { id: "year", label: "1 year", ms: 365 * 24 * 60 * 60 * 1000 },
] as const

const fmt = (value: string | null) => (value ? new Date(value).toLocaleDateString(undefined, { dateStyle: "medium" }) : "")

function grantStatus(grant: MspGrant): string {
  if (grant.revoked_at) return "Removed"
  if (new Date(grant.expires_at).getTime() <= Date.now()) return "Expired"
  return `Active until ${fmt(grant.expires_at)}`
}

const AUDIT_LABEL: Record<MspAuditEvent["action"], string> = {
  "grant.created": "gave health access",
  "grant.revoked": "removed health access",
  "grant.denied": "was refused health access",
}

/**
 * Health-only access for the people at this workspace's partner (MSP).
 * Shown only to the workspace owner; every call re-checks ownership server side.
 */
export function MspDelegationPanel({ customerOrgId }: { customerOrgId: string }) {
  const [granteeId, setGranteeId] = useState("")
  const [duration, setDuration] = useState<(typeof DURATIONS)[number]["id"]>("month")
  const [busy, setBusy] = useState(false)
  const { data, error, isLoading, mutate } = useSWR(["msp:management", customerOrgId], () =>
    mspDelegationsApi.management(customerOrgId),
  )
  const provider = data?.provider
  const members = data?.provider_members ?? []
  const grants = data?.grants ?? []
  const audit = data?.audit ?? []
  const memberById = new Map(members.map((member) => [member.user_id, member]))

  async function createGrant() {
    if (!provider || !granteeId) {
      toast.error("Choose someone from your partner's team")
      return
    }
    const person = memberById.get(granteeId)
    const span = DURATIONS.find((row) => row.id === duration) ?? DURATIONS[1]
    setBusy(true)
    try {
      await mspDelegationsApi.create({
        provider_org_id: provider.id,
        customer_org_id: customerOrgId,
        grantee_user_id: granteeId,
        tier: 1,
        actions: [...HEALTH_ACTIONS],
        expires_at: new Date(Date.now() + span.ms).toISOString(),
      })
      setGranteeId("")
      await mutate()
      toast.success(`${personLabel(person ?? {}, "They")} can now see this workspace's health for ${span.label}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not give access")
    } finally {
      setBusy(false)
    }
  }

  async function revokeGrant(grant: MspGrant) {
    const who = personLabel({ name: grant.grantee_name, email: grant.grantee_email }, "this person")
    if (!window.confirm(`Remove health access for ${who}? It stops on their next request.`)) return
    setBusy(true)
    try {
      await mspDelegationsApi.revoke(grant.id, customerOrgId)
      await mutate()
      toast.success("Access removed")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove access")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="msp-delegation-heading" className="min-w-0 space-y-4">
      <div>
        <h3 id="msp-delegation-heading" className="text-sm font-semibold text-foreground">
          Health access for {provider?.name ?? "your partner"}
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Without access, your partner sees only your plan and billing status. Health access also lets one person on
          their team see whether this workspace is healthy, how many members it has and its usage totals. They never
          see conversations, documents or memory, and you can remove access at any time.
        </p>
      </div>

      {isLoading && (
        <p role="status" className="text-xs text-muted-foreground">
          Loading your partner&apos;s team…
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error instanceof Error ? error.message : "Could not load access"}
        </p>
      )}
      {!isLoading && !error && !provider && (
        <p className="text-xs text-muted-foreground">This workspace isn&apos;t managed by a partner.</p>
      )}
      {provider && (
        <div className="space-y-3 rounded-md border border-divide p-3">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <div className="space-y-1.5">
              <Label htmlFor="msp-provider-member">Person on {provider.name}&apos;s team</Label>
              <select
                id="msp-provider-member"
                className="w-full min-w-0 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                value={granteeId}
                onChange={(event) => setGranteeId(event.target.value)}
                disabled={busy || members.length === 0}
              >
                <option value="">Choose a person</option>
                {members.map((member) => (
                  <option key={member.user_id} value={member.user_id}>
                    {personLabel(member)}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="msp-grant-duration">For</Label>
              <select
                id="msp-grant-duration"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                value={duration}
                onChange={(event) => setDuration(event.target.value as typeof duration)}
                disabled={busy}
              >
                {DURATIONS.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <Button type="button" size="sm" disabled={busy || !granteeId} onClick={() => void createGrant()}>
            Give health access
          </Button>
        </div>
      )}

      {!isLoading && !error && provider && (
        <>
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">Who has access</h4>
            {grants.length === 0 ? (
              <p className="text-xs text-muted-foreground">Nobody on your partner&apos;s team has health access.</p>
            ) : (
              <ul className="space-y-2">
                {grants.map((grant) => (
                  <li key={grant.id} className="min-w-0 rounded-md border border-divide p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-foreground">
                        {personLabel({ name: grant.grantee_name, email: grant.grantee_email })}
                      </span>
                      {!grant.revoked_at && new Date(grant.expires_at).getTime() > Date.now() && (
                        <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => void revokeGrant(grant)}>
                          Remove
                        </Button>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{grantStatus(grant)}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {audit.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-foreground">History</h4>
              <ul className="space-y-1.5">
                {audit.map((event) => (
                  <li key={event.id} className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">
                      {personLabel({ name: event.actor_name, email: event.actor_email }, "Someone")}
                    </span>{" "}
                    {AUDIT_LABEL[event.action] ?? event.action} · {fmt(event.recorded_at)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}
