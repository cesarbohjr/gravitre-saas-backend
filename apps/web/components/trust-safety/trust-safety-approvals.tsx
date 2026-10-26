"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR, { useSWRConfig } from "swr"
import { toast } from "./overlays/toast"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useMyCapability } from "@/lib/use-my-capability"
import {
  ROLE_PERMISSIONS_KEY,
  draftsFromMatrix,
  saveRolePermissions,
  type RolePermissionsResponse,
} from "@/lib/settings-api/roles"
import { approvalsApi } from "@/lib/api"
import { resolveProvider } from "@/lib/provider-registry"
import {
  formatDuration,
  isExtensionGate,
  isPastSla,
  normalizeApprovals,
  parseTime,
  titleCase,
  type Approval,
  type RiskLevel,
} from "@/components/approvals/decision-queue/model"
import { TrustSafetyDialog, TrustSafetyField } from "./overlays/dialog"
import { useApprovalRuleSaver, type PolicyState } from "./trust-safety-policies"
import { Hero, Icon, Pill, Segmented, Switch, TONE } from "./ts-ui"

const ALREADY_DONE = /already started|already resolved|not pending approval|already approved|no longer pending/i

const RISK: Record<RiskLevel, { label: string; tone: (typeof TONE)[keyof typeof TONE] }> = {
  high: { label: "High risk", tone: TONE.bad },
  medium: { label: "Medium risk", tone: TONE.warn },
  low: { label: "Low risk", tone: TONE.mute },
}

/** Live counts from the approvals API; the page uses them for the tab badge and the Live chip. */
export function useApprovalCounts() {
  const { user } = useAuth()
  const pendingSwr = useSWR(user ? "/api/approvals" : null, apiFetcher, { revalidateOnFocus: true, refreshInterval: 30_000 })
  const historySwr = useSWR(user ? "/api/approvals?status=history" : null, apiFetcher, { revalidateOnFocus: false, refreshInterval: 120_000 })
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  useEffect(() => {
    if (pendingSwr.data) setUpdatedAt(Date.now())
  }, [pendingSwr.data])

  const pending = useMemo(() => normalizeApprovals(pendingSwr.data).filter((a) => a.status === "pending"), [pendingSwr.data])
  const history = useMemo(
    () => (historySwr.data ? normalizeApprovals(historySwr.data).filter((a) => a.status === "approved" || a.status === "rejected") : null),
    [historySwr.data],
  )
  return {
    pending,
    history,
    waiting: pendingSwr.data ? pending.length : null,
    loading: !pendingSwr.data && !pendingSwr.error,
    error: pendingSwr.error as unknown,
    updatedAt,
    mutatePending: pendingSwr.mutate,
    mutateHistory: historySwr.mutate,
  }
}

function appName(slug: string | null): string | null {
  if (!slug) return null
  return resolveProvider(slug)?.name ?? titleCase(slug)
}

type ApproverChoice = "admins" | "members" | "custom"

const NON_ADMIN_ROLES = ["member", "viewer"] as const

/** Who holds "Approve write actions" among the built in roles, as the Routing select reads it. */
export function approverChoice(matrix: RolePermissionsResponse | undefined): ApproverChoice | null {
  const cap = matrix?.capabilities.find((c) => c.key === "approve_writes")
  if (!cap) return null
  if (cap.access.viewer) return "custom"
  return cap.access.member ? "members" : "admins"
}

/** Custom roles that can also approve, named for the Routing card. */
function customApprovers(matrix: RolePermissionsResponse | undefined): string[] {
  const cap = matrix?.capabilities.find((c) => c.key === "approve_writes")
  if (!cap || !matrix) return []
  return (matrix.custom_roles ?? []).filter((role) => cap.access[role]).map((role) => matrix.role_names?.[role] || role)
}

/**
 * Approval routing, wired to the backend: who can approve is the "Approve write
 * actions" permission on the Member role (PUT /api/org/role-permissions, which
 * the approve and reject endpoints enforce), and skipping read only actions is
 * the org rule autoApproveReadOnly (PATCH /api/settings/approval-rules).
 */
function RoutingCard({ policy, onViewPolicies }: { policy: PolicyState; onViewPolicies: () => void }) {
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const roles = useSWR<RolePermissionsResponse>(ROLE_PERMISSIONS_KEY, apiFetcher, { revalidateOnFocus: false })
  const saver = useApprovalRuleSaver(policy, isAdmin && Boolean(policy.rules.data), onViewPolicies)
  const [savingRoles, setSavingRoles] = useState(false)
  const choice = approverChoice(roles.data)
  const extra = customApprovers(roles.data)
  const canEdit = isAdmin && !adminLoading

  const setApprovers = async (next: ApproverChoice) => {
    if (!roles.data || !canEdit || next === "custom" || next === choice) return
    const drafts = draftsFromMatrix(roles.data).map((d) =>
      (NON_ADMIN_ROLES as readonly string[]).includes(d.key)
        ? {
            ...d,
            capabilities:
              next === "members" && d.key === "member"
                ? Array.from(new Set([...d.capabilities, "approve_writes"]))
                : d.capabilities.filter((c) => c !== "approve_writes"),
          }
        : d,
    )
    setSavingRoles(true)
    try {
      await roles.mutate(await saveRolePermissions(drafts), { revalidate: false })
      toast.success("Approvers updated", {
        description: next === "members" ? "Admins and members can approve or reject requests." : "Only admins and owners can approve or reject requests.",
      })
    } catch (err) {
      toast.error("Couldn’t change who can approve", {
        description: err instanceof Error ? err.message : "Nothing was changed.",
        action: { label: "Try again", onClick: () => void setApprovers(next) },
      })
    } finally {
      setSavingRoles(false)
    }
  }

  const skipReadOnly = Boolean(policy.values.autoApproveReadOnly)
  return (
    <section className="ts-card ts-side">
      <div className="ts-sidetitle"><span className="ts-ico sm blue"><Icon name="route" size={15} /></span>Routing</div>
      <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "#55564F" }}>
        Who can approve
        <select
          className="ts-select sm"
          value={choice ?? ""}
          disabled={!canEdit || !roles.data || savingRoles}
          onChange={(e) => void setApprovers(e.target.value as ApproverChoice)}
        >
          {choice == null ? <option value="">{roles.data || roles.error ? "Not available" : "Loading"}</option> : null}
          <option value="admins">Admins</option>
          <option value="members">Admins and members</option>
          {choice === "custom" ? <option value="custom" disabled>Custom, set in Role permissions</option> : null}
        </select>
        {extra.length ? <span style={{ fontSize: 12 }}>Also {extra.join(", ")}, from Role permissions.</span> : null}
      </label>
      <div className="ts-mini">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>Skip read only actions</div>
          <div style={{ fontSize: 12, color: "#55564F" }}>Lookups run without pausing</div>
        </div>
        <Switch
          on={skipReadOnly}
          label="Skip approval for read only actions"
          disabled={!canEdit || !policy.rules.data || saver.busy != null}
          onToggle={() => void saver.save({ autoApproveReadOnly: !skipReadOnly }, "autoApproveReadOnly")}
        />
      </div>
      {!canEdit && !adminLoading ? <div style={{ fontSize: 12, color: "#55564F" }}>Only owners and admins can change routing.</div> : null}
    </section>
  )
}

export function TrustSafetyApprovals({
  policy,
  onViewPast,
  onViewPolicies,
}: {
  policy: PolicyState
  onViewPast: () => void
  onViewPolicies: () => void
}) {
  const { user } = useAuth()
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const canApproveWrites = useMyCapability("approve_writes")
  const { mutate: mutateCache } = useSWRConfig()
  const { pending, history, waiting, loading, error, mutatePending, mutateHistory } = useApprovalCounts()

  const [risk, setRisk] = useState<"all" | RiskLevel>("all")
  const [busyId, setBusyId] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] = useState<Approval | null>(null)
  const [rejectReason, setRejectReason] = useState("")
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  const refresh = useCallback(async () => {
    // A decision can resume or cancel a run; refresh other mounted views too.
    await Promise.all([
      mutatePending(),
      mutateHistory(),
      mutateCache((key) => typeof key === "string" && (key.startsWith("/api/runs") || key.startsWith("/api/agents") || key.startsWith("/api/sessions"))),
    ])
  }, [mutatePending, mutateHistory, mutateCache])

  const breached = pending.filter((a) => isPastSla(a, now)).length
  const approved = history ? history.filter((a) => a.status === "approved").length : null
  const rejected = history ? history.filter((a) => a.status === "rejected").length : null

  // Oldest first, high risk ahead of the rest.
  const order: Record<string, number> = { high: 0, medium: 1, low: 2 }
  const open = pending
    .filter((a) => risk === "all" || a.context.riskLevel === risk)
    .sort((x, y) => {
      const r = (order[x.context.riskLevel ?? ""] ?? 3) - (order[y.context.riskLevel ?? ""] ?? 3)
      return r !== 0 ? r : (parseTime(x.requestedAt) ?? 0) - (parseTime(y.requestedAt) ?? 0)
    })

  const canDecide = (a: Approval) => adminLoading || isAdmin || canApproveWrites || (isExtensionGate(a) && Boolean(user?.id) && a.requestedById === user?.id)

  const approve = async (a: Approval) => {
    if (busyId) return
    setBusyId(a.id)
    try {
      const result = (await approvalsApi.approve(a.id)) as unknown as Record<string, unknown> | null
      await refresh()
      if (result && result.success === false) {
        toast.error(String(result.message ?? "The approved action did not run."))
        return
      }
      toast.dismiss(`approval-${a.id}`)
      toast.success("Approved", {
        description: String(result?.status ?? "") === "pending_approval" ? "Recorded. Another approver is still needed." : "The paused work is continuing.",
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not approve"
      if (ALREADY_DONE.test(message)) {
        await refresh()
        toast.success("Already decided", { description: "This request is no longer waiting in the queue." })
      } else toast.error(message)
    } finally {
      setBusyId(null)
    }
  }

  const reject = async () => {
    const a = rejectTarget
    const reason = rejectReason.trim()
    if (!a) return
    if (!reason) {
      toast.error("Add a reason so the requester knows what to change")
      return
    }
    setBusyId(a.id)
    try {
      await approvalsApi.reject(a.id, { comment: reason })
      await refresh()
      setRejectTarget(null)
      toast.success("Rejected", { description: "Nothing was run. Your reason is on the record." })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not reject"
      if (ALREADY_DONE.test(message)) {
        await refresh()
        setRejectTarget(null)
        toast.success("Already decided", { description: "This request is no longer waiting in the queue." })
      } else toast.error(message)
    } finally {
      setBusyId(null)
    }
  }

  // A request that arrives while the page is open gets an approval toast; the first load doesn't.
  const router = useRouter()
  const seen = useRef<Set<string> | null>(null)
  useEffect(() => {
    if (waiting == null) return
    const ids = new Set(pending.map((a) => a.id))
    const previous = seen.current
    seen.current = ids
    if (!previous) return
    const fresh = pending.filter((a) => !previous.has(a.id) && canDecide(a))
    if (fresh.length === 1) {
      const a = fresh[0]
      const level = a.context.riskLevel
      toast.approval(`${a.title} needs your approval`, {
        id: `approval-${a.id}`,
        description: [appName(a.context.integration), level ? RISK[level].label : null, `Requested by ${a.requestedBy}`].filter(Boolean).join(" · "),
        action: { label: "Approve", onClick: () => void approve(a) },
        cancel: { label: "Review", onClick: () => router.push(`/approvals?id=${encodeURIComponent(a.id)}`) },
      })
    } else if (fresh.length > 1) {
      toast.approval(`${fresh.length} new requests need your approval`, {
        description: "They are in the decision queue, high risk first.",
        cancel: { label: "Review", onClick: () => setRisk("all") },
      })
    }
    // canDecide and approve read the latest render; only a change in the queue should raise a toast.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending, waiting])

  const count = waiting ?? 0
  const advice =
    waiting == null
      ? loading
        ? "Loading the decision queue."
        : "The decision queue could not be loaded. It refreshes on its own."
      : count > 0
        ? `${count} ${count > 1 ? "requests are" : "request is"} paused until someone decides. High risk items come first.`
        : "No decisions are waiting. New requests appear the moment an agent pauses."

  return (
    <>
      <Hero
        art="approvals"
        artState={{ waiting: waiting ?? 0 }}
        eyebrow="Approvals · decision queue"
        big={waiting ?? "–"}
        unit="waiting on you"
        advice={advice}
        actions={
          <>
            <Link href="/settings?section=notifications" className="ts-btn dark sm">Notification rules</Link>
            <button type="button" className="ts-btn text sm" onClick={onViewPast}>View past decisions</button>
          </>
        }
        tiles={[
          { value: waiting ?? "–", label: "Waiting on you" },
          { value: waiting == null ? "–" : breached, label: "Past SLA", tone: breached > 0 ? "bad" : undefined },
          { value: approved ?? "–", label: "Approved", tone: "good" },
          { value: rejected ?? "–", label: "Rejected" },
        ]}
      />
      <div className="ts-cols">
        <div className="ts-colmain">
          <section className="ts-card" style={{ overflow: "hidden" }}>
            <div className="ts-cardhead">
              <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>Decision queue</div>
                <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>Oldest first, across every agent and workflow</div>
              </div>
              <Segmented
                label="Risk level"
                value={risk}
                onChange={setRisk}
                options={[["all", "All"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]] as const}
              />
            </div>
            {open.length === 0 ? (
              <div style={{ padding: "48px 24px", display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 6 }}>
                <span className="ts-ico" style={{ width: 52, height: 52, borderRadius: "50%", marginBottom: 8 }}>
                  <Icon name="tick" size={22} width={2} />
                </span>
                <div style={{ fontWeight: 600, fontSize: 16 }}>{error && waiting == null ? "Queue unavailable" : "All clear"}</div>
                <div style={{ fontSize: 14, color: "#55564F", maxWidth: 420, lineHeight: 1.5 }}>
                  {error && waiting == null
                    ? "The decision queue could not be loaded. It refreshes on its own."
                    : pending.length > 0
                      ? "Nothing at this risk level is waiting."
                      : "No decisions are waiting. New requests appear the moment an agent pauses for a human."}
                </div>
              </div>
            ) : (
              open.map((a) => {
                const level = a.context.riskLevel
                const tone = level ? RISK[level].tone : TONE.mute
                const requested = parseTime(a.requestedAt)
                const meta = [
                  appName(a.context.integration),
                  requested != null ? `waiting ${formatDuration(now - requested)}` : null,
                ].filter(Boolean)
                const allowed = canDecide(a)
                return (
                  <div key={a.id} className="ts-sec">
                    <span className={tone.ico}><Icon name="agent" /></span>
                    <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <span style={{ fontWeight: 600 }}>{a.title}</span>
                        <Pill bg={tone.bg} fg={tone.fg} dot={tone.dot}>{level ? RISK[level].label : "Not scored"}</Pill>
                      </div>
                      <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>
                        <span className="ts-mono" style={{ fontSize: 12 }}>{a.requestedBy}</span>
                        {meta.length ? ` · ${meta.join(" · ")}` : ""}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <Link href={`/approvals?id=${encodeURIComponent(a.id)}`} className="ts-btn text sm">Details</Link>
                      {allowed ? (
                        <>
                          <button type="button" className="ts-btn danger sm" disabled={busyId === a.id} onClick={() => { setRejectReason(""); setRejectTarget(a) }}>Reject</button>
                          <button type="button" className="ts-btn green sm" disabled={busyId === a.id} onClick={() => void approve(a)}>
                            <Icon name="tick" size={15} width={2} />
                            Approve
                          </button>
                        </>
                      ) : null}
                    </div>
                  </div>
                )
              })
            )}
          </section>
        </div>
        <aside className="ts-colside" aria-label="Approval routing">
          <RoutingCard policy={policy} onViewPolicies={onViewPolicies} />
          <section className="ts-card ts-side">
            <div className="ts-sidetitle"><span className="ts-ico sm"><Icon name="info" size={15} /></span>How a request flows</div>
            <div className="ts-step"><span className="ts-stepn">1</span>An agent reaches a step a policy guards and pauses.</div>
            <div className="ts-step"><span className="ts-stepn">2</span>Approvers are notified and decide here or in chat.</div>
            <div className="ts-step"><span className="ts-stepn" style={{ background: "#0B8A5C" }}>3</span>The decision is written to the audit trail.</div>
          </section>
        </aside>
      </div>

      <TrustSafetyDialog
        open={rejectTarget != null}
        onOpenChange={(openState) => { if (!openState) setRejectTarget(null) }}
        title="Reject this request?"
        description="Nothing will run. Tell the requester what to change."
        footer={
          <>
            <button type="button" className="tso-btn ghost" onClick={() => setRejectTarget(null)}>Cancel</button>
            <button type="button" className="tso-btn danger" disabled={busyId != null} onClick={() => void reject()}>Reject</button>
          </>
        }
      >
        <TrustSafetyField label="Reason" htmlFor="ts-reject-reason">
          <textarea id="ts-reject-reason" className="tso-in" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} rows={3} placeholder="What should change before this runs" />
        </TrustSafetyField>
      </TrustSafetyDialog>
    </>
  )
}
