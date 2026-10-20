"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"
import { fetcher } from "@/lib/fetcher"
import { settingsApi, type ApprovalRules } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { listAudit, rangeStart } from "@/lib/settings-api/audit"
import { eventActor, eventTitle, isErrorEvent } from "@/components/settings/audit-model"
import type { User } from "@/types/api"
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

function shortTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

export function TrustSafetyPolicies({ state, onOpenAudit }: { state: PolicyState; onOpenAudit: () => void }) {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const { rules, values, on } = state
  const [busy, setBusy] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

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

  async function saveRule(patch: Partial<Pick<ApprovalRules, RuleKey | "sla">>, key: string) {
    if (locked || !rules.data) return
    setBusy(key)
    const previous = rules.data
    await rules.mutate({ rules: { ...previous.rules, ...patch } }, { revalidate: false })
    try {
      await rules.mutate(await settingsApi.updateApprovalRules(patch), { revalidate: false })
    } catch (err) {
      await rules.mutate(previous, { revalidate: false })
      toast.error(err instanceof Error ? err.message : "Could not save the approval rule")
    } finally {
      setBusy(null)
    }
  }

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
    setBusy(`hitl:${policy.id}`)
    try {
      await settingsApi.deleteHitlPolicy(policy.id)
      toast.success("Policy deleted")
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
        eyebrow="Policies · guardrail coverage"
        big={on ?? "–"}
        unit={`of ${RULES.length} rules on`}
        bars={RULES.map((r) => Boolean(rules.data && values[r.key]))}
        advice={advice}
        actions={
          isAdmin ? (
            <button type="button" className="ts-btn green sm" onClick={() => setCreating(true)}>
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
                <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Applied to every agent, workflow and chat write</div>
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
                    <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>{r.help}</div>
                  </div>
                  <Switch on={v} label={r.label} disabled={locked || busy != null} onToggle={() => void saveRule({ [r.key]: !v }, r.key)} />
                  {r.key === "escalatePastDue" ? (
                    <div className="ts-sub">
                      <span style={{ fontSize: 13, color: "#6A6B64" }}>Decision window</span>
                      <select className="ts-select sm" aria-label="Decision window" value={values.sla} disabled={locked || busy != null} onChange={(e) => void saveRule({ sla: e.target.value as Sla }, "sla")}>
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
                  <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Fine tune who approves what. More specific policies win when several match.</div>
                </div>
                {!creating ? (
                  <button type="button" className="ts-btn line sm" onClick={() => setCreating(true)}>
                    <Icon name="plus" size={15} width={2} />
                    New policy
                  </button>
                ) : null}
              </div>
              {creating ? (
                <NewPolicyForm
                  departments={departments}
                  members={members}
                  onCancel={() => setCreating(false)}
                  onCreated={async () => { setCreating(false); await hitl.mutate() }}
                />
              ) : null}
              {hitl.error && !hitl.data ? (
                <div className="ts-sec" style={{ fontSize: 14, color: "#8A2530" }}>Policies could not be loaded.</div>
              ) : !hitl.data ? (
                <div className="ts-sec" style={{ fontSize: 14, color: "#6A6B64" }}>Loading policies.</div>
              ) : policies.length === 0 ? (
                <div className="ts-sec" style={{ fontSize: 14, color: "#6A6B64" }}>No team policies yet. Write and delete actions still need an admin or owner by default.</div>
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
                        <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>
                          {scope} · {(p.action_kinds ?? []).map(cap).join(", ") || "No actions"} · Approved by {(p.approver_roles ?? []).map(cap).join(", ") || "admins"}
                        </div>
                      </div>
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
              <div className="ts-mini" style={{ fontSize: 13, color: "#6A6B64" }}>{recent.data ? "No setting changes in the last 30 days." : "Loading recent changes."}</div>
            ) : (
              changes.map((log) => (
                <div key={log.id} className="ts-mini">
                  <span className="ts-dot" style={{ background: isErrorEvent(log) ? "#C4434F" : "#E2A33A" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{eventTitle(log)}</div>
                    <div style={{ fontSize: 12, color: "#6A6B64" }}>{eventActor(log)} · {shortTime(log.created_at)}</div>
                  </div>
                </div>
              ))
            )}
            <button type="button" className="ts-btn text sm" style={{ alignSelf: "flex-start", padding: "0 4px" }} onClick={onOpenAudit}>Open audit trail</button>
          </section>
          <Note>{isAdmin ? "Policies apply organization wide and every change is recorded." : "Only owners and admins can change policies. You can see what is set."}</Note>
        </aside>
      </div>
    </>
  )
}

function NewPolicyForm({
  departments,
  members,
  onCancel,
  onCreated,
}: {
  departments: Array<{ id: string; name: string }>
  members: User[]
  onCancel: () => void
  onCreated: () => Promise<void>
}) {
  const [name, setName] = useState("Write and delete approval")
  const [scope, setScope] = useState<ScopeType>("org")
  const [deptId, setDeptId] = useState("")
  const [userId, setUserId] = useState("")
  const [actions, setActions] = useState<ActionKind[]>(["write", "delete"])
  const [approvers, setApprovers] = useState<string[]>(["admin", "owner"])
  const [saving, setSaving] = useState(false)
  const toggle = <T extends string>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

  async function submit() {
    if (!name.trim()) return toast.error("Give the policy a name")
    if (actions.length === 0) return toast.error("Pick at least one action")
    if (scope === "department" && !deptId) return toast.error("Choose a team")
    if (scope === "user" && !userId) return toast.error("Choose a person")
    setSaving(true)
    try {
      await settingsApi.createHitlPolicy({
        name: name.trim(),
        enabled: true,
        scope_type: scope,
        department_id: scope === "department" ? deptId : null,
        subject_user_id: scope === "user" ? userId : null,
        action_kinds: actions,
        approver_roles: approvers.length ? approvers : ["admin", "owner"],
        required_approvals: 1,
      })
      toast.success("Policy created")
      await onCreated()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create the policy")
    } finally {
      setSaving(false)
    }
  }

  const label = { fontSize: 13, color: "#6A6B64", minWidth: 88 } as const
  return (
    <div className="ts-sec" style={{ background: "#FBFBF9", flexDirection: "column", alignItems: "stretch", gap: 12 }}>
      <label className="ts-input" style={{ flex: "0 0 auto" }}>
        <input aria-label="Policy name" placeholder="Policy name" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <span style={label}>Applies to</span>
        <select className="ts-select sm" aria-label="Applies to" value={scope} onChange={(e) => setScope(e.target.value as ScopeType)}>
          <option value="org">Whole organization</option>
          <option value="department" disabled={departments.length === 0}>A team</option>
          <option value="user">A person</option>
        </select>
        {scope === "department" ? (
          <select className="ts-select sm" aria-label="Team" value={deptId} onChange={(e) => setDeptId(e.target.value)}>
            <option value="">Choose a team</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        ) : null}
        {scope === "user" ? (
          <select className="ts-select sm" aria-label="Person" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Choose a person</option>
            {members.map((m) => <option key={m.id} value={m.id}>{m.email || m.full_name || m.id}</option>)}
          </select>
        ) : null}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <span style={label}>Actions</span>
        {ACTIONS.map((a) => (
          <button key={a} type="button" className={`ts-chip${actions.includes(a) ? " on" : ""}`} aria-pressed={actions.includes(a)} onClick={() => setActions((l) => toggle(l, a))}>{cap(a)}</button>
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        <span style={label}>Approved by</span>
        {ROLES.map((r) => (
          <button key={r} type="button" className={`ts-chip${approvers.includes(r) ? " on" : ""}`} aria-pressed={approvers.includes(r)} onClick={() => setApprovers((l) => toggle(l, r))}>{cap(r)}</button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="ts-btn line sm" onClick={onCancel}>Cancel</button>
        <button type="button" className="ts-btn dark sm" disabled={saving} onClick={() => void submit()}>{saving ? "Creating" : "Create policy"}</button>
      </div>
    </div>
  )
}
