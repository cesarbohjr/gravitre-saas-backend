"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "./overlays/toast"
import { useAuth } from "@/lib/auth-context"
import { fetcher } from "@/lib/fetcher"
import { settingsApi, type ApprovalRules } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { listAudit, rangeStart } from "@/lib/settings-api/audit"
import { eventActor, eventTitle, isErrorEvent } from "@/components/settings/audit-model"
import type { User } from "@/types/api"
import { confirmTrustSafety } from "./overlays/confirm"
import { TrustSafetyDialog, TrustSafetyField } from "./overlays/dialog"
import { Hero, Icon, Note, Pill, Switch, type IconName } from "./ts-ui"

type RuleKey = "customerEmailApproval" | "twoApprovalsHighRisk" | "autoApproveReadOnly" | "escalatePastDue"
type Sla = ApprovalRules["sla"]
type ActionKind = "read" | "write" | "delete"
type ScopeType = "org" | "department" | "user"

interface HitlPolicy {
  id: string
  name: string
  enabled: boolean
  scope_type: ScopeType
  department_id: string | null
  subject_user_id: string | null
  action_kinds: ActionKind[]
  approver_roles: string[]
}

const RULES: Array<{ key: RuleKey; label: string; help: string; icon: IconName; recommend?: boolean }> = [
  { key: "customerEmailApproval", label: "Customer email waits for approval", help: "Agents draft messages but a person sends them", icon: "shield" },
  { key: "twoApprovalsHighRisk", label: "Two approvals for high risk actions", help: "Money, deletes and bulk changes need a second person", icon: "warn", recommend: true },
  { key: "autoApproveReadOnly", label: "Auto approve read only lookups", help: "Searches and reports run without waiting", icon: "search" },
  { key: "escalatePastDue", label: "Escalate past due requests", help: "Notify the next approver when the decision window runs out", icon: "clock" },
]
const SLAS: Array<[Sla, string]> = [["1h", "1 hour"], ["4h", "4 hours"], ["1bd", "1 business day"]]
const ACTIONS: ActionKind[] = ["read", "write", "delete"]
const ROLES = ["owner", "admin", "member", "viewer"]
const RULES_KEY = "/api/settings/approval-rules"
const HITL_KEY = "/api/settings/hitl-policies"

const DEFAULTS: Pick<ApprovalRules, RuleKey | "sla"> = {
  customerEmailApproval: true,
  twoApprovalsHighRisk: false,
  autoApproveReadOnly: false,
  escalatePastDue: false,
  sla: "4h",
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** Org approval rules from /api/settings/approval-rules; the page reads `on` for the tab badge. */
export function usePolicyState() {
  const rules = useSWR<{ rules: ApprovalRules }>(RULES_KEY, fetcher, { revalidateOnFocus: false })
  const values = { ...DEFAULTS, ...rules.data?.rules }
  const on = rules.data ? RULES.filter((r) => values[r.key]).length : null
  return { rules, values, on }
}

export type PolicyState = ReturnType<typeof usePolicyState>

export type RulePatch = Partial<Pick<ApprovalRules, RuleKey | "sla">>

function describeRule(patch: RulePatch): string {
  if (patch.sla) return `Requests are past due after ${SLAS.find(([id]) => id === patch.sla)?.[1] ?? patch.sla}.`
  const key = (Object.keys(patch) as RuleKey[]).find((k) => k !== ("sla" as string))
  const rule = RULES.find((r) => r.key === key)
  if (!key || !rule) return "Applies to new requests."
  return `${rule.label} is ${patch[key] ? "on" : "off"}. Applies to new requests.`
}

/**
 * Saves org approval rules (PATCH /api/settings/approval-rules) optimistically,
 * then offers Undo, which sends the previous values back. `onView` adds a
 * View policy button when the change was made outside the Policies tab.
 */
export function useApprovalRuleSaver(state: PolicyState, canEdit: boolean, onView?: () => void) {
  const { rules, values } = state
  const [busy, setBusy] = useState<string | null>(null)

  async function save(patch: RulePatch, key: string, undo = true): Promise<void> {
    if (!canEdit || !rules.data) return
    setBusy(key)
    const previous = rules.data
    const before = Object.fromEntries(Object.keys(patch).map((k) => [k, values[k as RuleKey | "sla"]])) as RulePatch
    await rules.mutate({ rules: { ...previous.rules, ...patch } }, { revalidate: false })
    try {
      await rules.mutate(await settingsApi.updateApprovalRules(patch), { revalidate: false })
      toast.success(undo ? "Policy updated" : "Change undone", {
        eyebrow: "Policies",
        description: describeRule(patch),
        action: onView ? { label: "View policy", onClick: onView } : undefined,
        cancel: undo ? { label: "Undo", onClick: () => void save(before, key, false) } : undefined,
      })
    } catch (err) {
      await rules.mutate(previous, { revalidate: false })
      toast.error("Couldn’t save the approval rule", {
        eyebrow: "Policies",
        description: err instanceof Error ? err.message : "Nothing was changed.",
        action: { label: "Try again", onClick: () => void save(patch, key, undo) },
      })
    } finally {
      setBusy(null)
    }
  }

  return { busy, save }
}

function shortTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

export function TrustSafetyPolicies({ state, onOpenAudit }: { state: PolicyState; onOpenAudit: () => void }) {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const { rules, values, on } = state
  const [busy, setBusy] = useState<string | null>(null)
  const [editing, setEditing] = useState<HitlPolicy | "new" | null>(null)

  const hitl = useSWR<{ policies: HitlPolicy[] }>(isAdmin ? HITL_KEY : null, fetcher, { revalidateOnFocus: false })
  const depts = useSWR<{ departments?: Array<{ id: string; name: string }> }>(isAdmin ? "/api/settings/lite-seats" : null, fetcher, { revalidateOnFocus: false })
  const team = useSWR<{ team?: User[] }>(isAdmin ? "/api/settings/team" : null, fetcher, { revalidateOnFocus: false })
  const recent = useSWR(user ? (["trust-safety/policies/recent", user.id] as const) : null, () =>
    listAudit({ range: "30d", category: "setting" }, rangeStart("30d"), { limit: 2, offset: 0 }),
  { revalidateOnFocus: false })

  const policies = hitl.data?.policies ?? []
  const departments = useMemo(() => depts.data?.departments ?? [], [depts.data])
  const members = useMemo(() => team.data?.team ?? [], [team.data])
  const changes = (recent.data?.logs ?? []).slice(0, 2)
  const locked = !isAdmin || !rules.data

  const deptName = useMemo(() => new Map(departments.map((d) => [String(d.id), String(d.name || d.id)])), [departments])
  const userName = useMemo(() => new Map(members.map((m) => [String(m.id), String(m.email || m.full_name || m.id)])), [members])

  const saver = useApprovalRuleSaver(state, !locked)
  const saveRule = (patch: RulePatch, key: string) => saver.save(patch, key)

  async function togglePolicy(policy: HitlPolicy) {
    setBusy(`hitl:${policy.id}`)
    try {
      await settingsApi.updateHitlPolicy(policy.id, { enabled: !policy.enabled })
      await hitl.mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update the policy")
    } finally {
      setBusy(null)
    }
  }

  async function deletePolicy(policy: HitlPolicy) {
    const ok = await confirmTrustSafety({
      title: `Delete ${policy.name}?`,
      description: "Requests it covers fall back to the organization rules. Requests already waiting keep their approvers.",
      confirmLabel: "Delete",
    })
    if (!ok) return
    setBusy(`hitl:${policy.id}`)
    try {
      await settingsApi.deleteHitlPolicy(policy.id)
      toast.success("Policy deleted", { description: `${policy.name} no longer applies to new requests.` })
      await hitl.mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete the policy")
    } finally {
      setBusy(null)
    }
  }

  const slaLabel = SLAS.find(([id]) => id === values.sla)?.[1] ?? "4 hours"
  const advice = !rules.data
    ? rules.error ? "Approval rules could not be loaded." : "Loading approval rules."
    : !values.twoApprovalsHighRisk
      ? "Turn on two approvals for high risk actions so money, deletes and bulk changes need a second person."
      : !values.escalatePastDue
        ? "Turn on escalation so requests past the decision window reach the next approver."
        : "Write and delete actions wait for a person, and nothing sits past its decision window."

  return (
    <>
      <Hero
        art="policies"
        artState={{ rules: rules.data ? RULES.map((r) => Boolean(values[r.key])) : undefined }}
        eyebrow="Policies · guardrail coverage"
        big={on ?? "–"}
        unit={`of ${RULES.length} rules on`}
        bars={RULES.map((r) => Boolean(rules.data && values[r.key]))}
        advice={advice}
        actions={
          isAdmin ? (
            <button type="button" className="ts-btn green sm" onClick={() => setEditing("new")}>
              <Icon name="plus" size={15} width={2} />
              New policy
            </button>
          ) : null
        }
        tiles={[
          { value: on == null ? "–" : `${on} of ${RULES.length}`, label: "Rules on", tone: "good" },
          { value: slaLabel, label: "Decision window" },
          { value: isAdmin ? policies.length : "–", label: "Team policies" },
          { value: isAdmin ? policies.filter((p) => p.enabled).length : "–", label: "Active policies" },
        ]}
      />
      <div className="ts-cols">
        <div className="ts-colmain">
          <section className="ts-card" style={{ overflow: "hidden" }}>
            <div className="ts-cardhead">
              <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>Approval rules</div>
                <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>Applied to every agent, workflow and chat write</div>
              </div>
            </div>
            {RULES.map((r) => {
              const v = Boolean(values[r.key])
              return (
                <div key={r.key} className="ts-sec">
                  <span className={r.recommend && !v ? "ts-ico warn" : "ts-ico"}><Icon name={r.icon} /></span>
                  <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      <span style={{ fontWeight: 600 }}>{r.label}</span>
                      {r.recommend && !v && rules.data ? <Pill bg="#FBF1DC" fg="#8A5A06" dot="#E2A33A">Recommended</Pill> : null}
                    </div>
                    <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>{r.help}</div>
                  </div>
                  <Switch on={v} label={r.label} disabled={locked || saver.busy != null} onToggle={() => void saveRule({ [r.key]: !v }, r.key)} />
                  {r.key === "escalatePastDue" ? (
                    <div className="ts-sub">
                      <span style={{ fontSize: 13, color: "#55564F" }}>Decision window</span>
                      <select className="ts-select sm" aria-label="Decision window" value={values.sla} disabled={locked || saver.busy != null} onChange={(e) => void saveRule({ sla: e.target.value as Sla }, "sla")}>
                        {SLAS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                      </select>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </section>
          {isAdmin ? (
            <section className="ts-card" style={{ overflow: "hidden" }}>
              <div className="ts-cardhead">
                <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>Policies by team or person</div>
                  <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>Fine tune who approves what. More specific policies win when several match.</div>
                </div>
                <button type="button" className="ts-btn line sm" onClick={() => setEditing("new")}>
                  <Icon name="plus" size={15} width={2} />
                  New policy
                </button>
              </div>
              {hitl.error && !hitl.data ? (
                <div className="ts-sec" style={{ fontSize: 14, color: "#A3333D" }}>Policies could not be loaded.</div>
              ) : !hitl.data ? (
                <div className="ts-sec" style={{ fontSize: 14, color: "#55564F" }}>Loading policies.</div>
              ) : policies.length === 0 ? (
                <div className="ts-sec" style={{ fontSize: 14, color: "#55564F" }}>No team policies yet. Write and delete actions still need an admin or owner by default.</div>
              ) : (
                policies.map((p) => {
                  const scope = p.scope_type === "org"
                    ? "Whole organization"
                    : p.scope_type === "department"
                      ? `Team · ${deptName.get(p.department_id ?? "") ?? p.department_id}`
                      : `Person · ${userName.get(p.subject_user_id ?? "") ?? p.subject_user_id}`
                  return (
                    <div key={p.id} className="ts-sec">
                      <span className={p.enabled ? "ts-ico" : "ts-ico mute"}><Icon name="users" /></span>
                      <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                        <div style={{ fontWeight: 600 }}>{p.name}</div>
                        <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>
                          {scope} · {(p.action_kinds ?? []).map(cap).join(", ") || "No actions"} · Approved by {(p.approver_roles ?? []).map(cap).join(", ") || "admins"}
                        </div>
                      </div>
                      <button type="button" className="ts-btn text sm" disabled={busy != null} onClick={() => setEditing(p)}>Edit</button>
                      <button type="button" className="ts-btn text sm" disabled={busy != null} aria-label={`Delete ${p.name}`} onClick={() => void deletePolicy(p)}>
                        <Icon name="x" size={14} width={2.2} />
                      </button>
                      <Switch on={p.enabled} label={`${p.name} on`} disabled={busy != null} onToggle={() => void togglePolicy(p)} />
                    </div>
                  )
                })
              )}
            </section>
          ) : null}
        </div>
        <aside className="ts-colside" aria-label="Recent policy activity">
          <section className="ts-card ts-side">
            <div className="ts-sidetitle"><span className="ts-ico sm warn"><Icon name="clock" size={15} /></span>Recent changes</div>
            {changes.length === 0 ? (
              <div className="ts-mini" style={{ fontSize: 13, color: "#55564F" }}>{recent.data ? "No setting changes in the last 30 days." : "Loading recent changes."}</div>
            ) : (
              changes.map((log) => (
                <div key={log.id} className="ts-mini">
                  <span className="ts-dot" style={{ background: isErrorEvent(log) ? "#A3333D" : "#E2A33A" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{eventTitle(log)}</div>
                    <div style={{ fontSize: 12, color: "#55564F" }}>{eventActor(log)} · {shortTime(log.created_at)}</div>
                  </div>
                </div>
              ))
            )}
            <button type="button" className="ts-btn text sm" style={{ alignSelf: "flex-start", padding: "0 4px" }} onClick={onOpenAudit}>Open audit trail</button>
          </section>
          <Note>{isAdmin ? "Policies apply organization wide and every change is recorded." : "Only owners and admins can change policies. You can see what is set."}</Note>
        </aside>
      </div>
      {isAdmin ? (
        <PolicyDialog
          key={editing === null ? "closed" : editing === "new" ? "new" : editing.id}
          policy={editing}
          departments={departments}
          members={members}
          onClose={() => setEditing(null)}
          onSaved={async () => { setEditing(null); await hitl.mutate() }}
        />
      ) : null}
    </>
  )
}

/** Create a team or person policy, or edit one (POST and PATCH /api/settings/hitl-policies). */
function PolicyDialog({
  policy,
  departments,
  members,
  onClose,
  onSaved,
}: {
  policy: HitlPolicy | "new" | null
  departments: Array<{ id: string; name: string }>
  members: User[]
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const existing = policy && policy !== "new" ? policy : null
  const [name, setName] = useState(existing?.name ?? "Write and delete approval")
  const [scope, setScope] = useState<ScopeType>(existing?.scope_type ?? "org")
  const [deptId, setDeptId] = useState(existing?.department_id ?? "")
  const [userId, setUserId] = useState(existing?.subject_user_id ?? "")
  const [actions, setActions] = useState<ActionKind[]>(existing?.action_kinds ?? ["write", "delete"])
  const [approvers, setApprovers] = useState<string[]>(existing?.approver_roles?.length ? existing.approver_roles : ["admin", "owner"])
  const [saving, setSaving] = useState(false)
  const toggle = <T extends string>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

  async function submit() {
    if (!name.trim()) return toast.error("Give the policy a name")
    if (actions.length === 0) return toast.error("Pick at least one action")
    if (scope === "department" && !deptId) return toast.error("Choose a team")
    if (scope === "user" && !userId) return toast.error("Choose a person")
    const body = {
      name: name.trim(),
      scope_type: scope,
      department_id: scope === "department" ? deptId : null,
      subject_user_id: scope === "user" ? userId : null,
      action_kinds: actions,
      approver_roles: approvers.length ? approvers : ["admin", "owner"],
    }
    setSaving(true)
    try {
      if (existing) await settingsApi.updateHitlPolicy(existing.id, body)
      else await settingsApi.createHitlPolicy({ ...body, enabled: true, required_approvals: 1 })
      toast.success(existing ? "Policy updated" : "Policy created", {
        description: `${actions.map(cap).join(", ")} actions now wait for ${(approvers.length ? approvers : ["admin", "owner"]).map(cap).join(" or ")}. Applies to new requests.`,
      })
      await onSaved()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : existing ? "Could not update the policy" : "Could not create the policy")
    } finally {
      setSaving(false)
    }
  }

  return (
    <TrustSafetyDialog
      open={policy != null}
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={existing ? "Edit policy" : "New policy"}
      description="Decide which actions pause for a person, and who approves them."
      footer={
        <>
          <button type="button" className="tso-btn ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="tso-btn dark" disabled={saving} onClick={() => void submit()}>
            {saving ? "Saving" : existing ? "Save policy" : "Create policy"}
          </button>
        </>
      }
    >
      <TrustSafetyField label="Name" htmlFor="ts-policy-name">
        <input id="ts-policy-name" className="tso-in" value={name} onChange={(e) => setName(e.target.value)} />
      </TrustSafetyField>
      <TrustSafetyField label="Applies to" htmlFor="ts-policy-scope">
        <select id="ts-policy-scope" className="tso-in" value={scope} onChange={(e) => setScope(e.target.value as ScopeType)}>
          <option value="org">Whole organization</option>
          <option value="department" disabled={departments.length === 0}>A team</option>
          <option value="user">A person</option>
        </select>
      </TrustSafetyField>
      {scope === "department" ? (
        <TrustSafetyField label="Team" htmlFor="ts-policy-team">
          <select id="ts-policy-team" className="tso-in" value={deptId} onChange={(e) => setDeptId(e.target.value)}>
            <option value="">Choose a team</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </TrustSafetyField>
      ) : null}
      {scope === "user" ? (
        <TrustSafetyField label="Person" htmlFor="ts-policy-person">
          <select id="ts-policy-person" className="tso-in" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Choose a person</option>
            {members.map((m) => <option key={m.id} value={m.id}>{m.email || m.full_name || m.id}</option>)}
          </select>
        </TrustSafetyField>
      ) : null}
      <TrustSafetyField label="Actions that wait">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {ACTIONS.map((a) => (
            <button key={a} type="button" className={`ts-chip${actions.includes(a) ? " on" : ""}`} aria-pressed={actions.includes(a)} onClick={() => setActions((l) => toggle(l, a))}>{cap(a)}</button>
          ))}
        </div>
      </TrustSafetyField>
      <TrustSafetyField label="Approved by">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {ROLES.map((r) => (
            <button key={r} type="button" className={`ts-chip${approvers.includes(r) ? " on" : ""}`} aria-pressed={approvers.includes(r)} onClick={() => setApprovers((l) => toggle(l, r))}>{cap(r)}</button>
          ))}
        </div>
      </TrustSafetyField>
    </TrustSafetyDialog>
  )
}
