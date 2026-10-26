"use client"

/**
 * The client side of the partner program, for the current workspace:
 * - a partner's request to manage it (owner approves or declines, picks access),
 * - "Managed by <partner>" with detach and health access for health-only links.
 * Renders nothing when the workspace has no partner and no request.
 */
import { confirmDialog } from "@/components/agents/overlays/confirm"
import { useState } from "react"
import { useMspOverview } from "@/lib/use-msp-overview"
import { Building2, ShieldCheck } from "lucide-react"
import { toast } from "@/components/agents/overlays/toast"
import { SetNote, SetPill } from "@/components/settings/settings-kit"
import { MspDelegationPanel } from "@/components/settings/msp-delegation-panel"
import {
  accessLevelLabel,
  mspProgramApi,
  personLabel,
  type MspAccessLevel,
  type MspOverview,
} from "@/lib/msp-program"

export function MspClientRelationship() {
  const { data, mutate } = useMspOverview()
  if (!data) return null
  if (data.pending_request) return <PendingRequest overview={data} onDone={() => void mutate()} />
  if (data.managed_by) return <ManagedBy overview={data} onDone={() => void mutate()} />
  return null
}

function PendingRequest({ overview, onDone }: { overview: MspOverview; onDone: () => void }) {
  const request = overview.pending_request!
  const [access, setAccess] = useState<MspAccessLevel>("health_only")
  const [people, setPeople] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const toggle = (id: string) => setPeople((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]))

  async function approve() {
    if (access === "full" && people.length === 0) {
      toast.error("Choose at least one person for full access")
      return
    }
    setBusy(true)
    try {
      await mspProgramApi.approve(request.relationship_id, { access_level: access, member_user_ids: people })
      toast.success(`${request.msp_name} now manages and bills this workspace`)
      onDone()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not approve")
    } finally {
      setBusy(false)
    }
  }

  async function decline() {
    if (!(await confirmDialog({ title: `Decline ${request.msp_name}'s request?`, description: "Nothing changes for this workspace.", confirmLabel: "Decline" }))) return
    setBusy(true)
    try {
      await mspProgramApi.decline(request.relationship_id)
      toast.success("Request declined")
      onDone()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not decline")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="gs-card" aria-labelledby="msp-request-heading" data-review-surface="msp-client-request" style={{ padding: 20, marginBottom: 16 }}>
      <div className="gs-card-title" style={{ marginBottom: 10 }}>
        <Building2 size={18} aria-hidden />
        <h3 id="msp-request-heading">{request.msp_name} wants to manage this workspace</h3>
      </div>
      <p className="gs-sub" style={{ marginTop: 0 }}>
        If you approve, {request.msp_name} pays Gravitre for this workspace on the {request.plan_name} plan and bills
        you directly at the price you agreed with them. Gravitre stops billing you. You can detach at any time.
      </p>
      {request.own_subscription_conflict ? (
        <SetNote tone="amber">{request.own_subscription_conflict}</SetNote>
      ) : null}
      <fieldset style={{ border: 0, padding: 0, margin: "14px 0 0" }}>
        <legend className="gs-strong" style={{ fontSize: 14, marginBottom: 8 }}>
          What can their team see and do?
        </legend>
        <label className="gs-orow" style={{ borderTop: 0, padding: "8px 0" }}>
          <input type="radio" name="msp-access" checked={access === "health_only"} onChange={() => setAccess("health_only")} />
          <span>
            <b>Health only.</b> The people you choose can see whether the workspace is healthy, its member count and
            usage totals. Nothing else: no conversations, documents, agents or settings.
          </span>
        </label>
        <label className="gs-orow" style={{ padding: "8px 0" }}>
          <input type="radio" name="msp-access" checked={access === "full"} onChange={() => setAccess("full")} />
          <span>
            <b>Full access.</b> The people you choose join this workspace as admins, so they can set it up and run it
            for you. They are removed again if you detach.
          </span>
        </label>
      </fieldset>
      <div style={{ marginTop: 12 }}>
        <p className="gs-strong" style={{ fontSize: 14, margin: "0 0 6px" }}>
          People on {request.msp_name}&apos;s team {access === "health_only" ? "(optional)" : ""}
        </p>
        {request.msp_members.length === 0 ? (
          <p className="gs-sub">Their team has no members yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
            {request.msp_members.map((member) => (
              <li key={member.user_id}>
                <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
                  <input type="checkbox" checked={people.includes(member.user_id)} onChange={() => toggle(member.user_id)} />
                  {personLabel(member)}
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 16 }}>
        <button type="button" className="gs-btn dark sm" disabled={busy || Boolean(request.own_subscription_conflict)} onClick={() => void approve()}>
          Approve
        </button>
        <button type="button" className="gs-btn line sm" disabled={busy} onClick={() => void decline()}>
          Decline
        </button>
      </div>
    </section>
  )
}

function ManagedBy({ overview, onDone }: { overview: MspOverview; onDone: () => void }) {
  const managed = overview.managed_by!
  const [busy, setBusy] = useState(false)

  async function detach() {
    if (
      !(await confirmDialog({
        title: `Detach from ${managed.msp_name}?`,
        description:
          "They stop billing you and lose any access you gave them. This workspace moves to a 7-day trial, so pick a plan in Billing to keep going.",
        confirmLabel: "Detach",
      }))
    )
      return
    setBusy(true)
    try {
      await mspProgramApi.detach(managed.relationship_id)
      toast.success(`Detached from ${managed.msp_name}`)
      onDone()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not detach")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="gs-card" aria-labelledby="msp-managed-heading" data-review-surface="msp-managed-by" style={{ padding: 20, marginBottom: 16 }}>
      <div className="gs-card-title" style={{ marginBottom: 8, justifyContent: "space-between", flexWrap: "wrap" }}>
        <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <ShieldCheck size={18} aria-hidden />
          <h3 id="msp-managed-heading">Managed by {managed.msp_name}</h3>
        </span>
        <SetPill tone="green">{accessLevelLabel(managed.access_level)}</SetPill>
      </div>
      <p className="gs-sub" style={{ marginTop: 0 }}>
        {managed.msp_name} pays for this workspace on the {managed.plan_name} plan and bills you directly. Questions
        about your invoice go to them.
      </p>
      {managed.can_detach ? (
        <>
          {managed.access_level === "health_only" ? (
            <div style={{ marginTop: 14 }}>
              <MspDelegationPanel customerOrgId={overview.org.id} />
            </div>
          ) : null}
          <button type="button" className="gs-btn line sm" style={{ marginTop: 14 }} disabled={busy} onClick={() => void detach()}>
            Detach from {managed.msp_name}
          </button>
        </>
      ) : (
        <p className="gs-sub">Only the workspace owner can change this.</p>
      )}
    </section>
  )
}
