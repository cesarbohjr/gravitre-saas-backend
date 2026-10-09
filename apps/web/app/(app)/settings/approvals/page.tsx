"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { ApprovalRulesSettings } from "@/components/settings/approval-rules-settings"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CheckCircle2, Loader2, Plus, ShieldCheck, Trash2 } from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useViewModeSafe } from "@/lib/view-mode-context"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import { settingsApi } from "@/lib/api"
import type { User } from "@/types/api"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

type ActionKind = "read" | "write" | "delete"
type ScopeType = "org" | "department" | "user"

type HitlPolicy = {
  id: string
  name: string
  enabled: boolean
  scope_type: ScopeType
  department_id: string | null
  subject_user_id: string | null
  action_kinds: ActionKind[]
  approver_roles: string[]
  approver_user_ids: string[]
  required_approvals: number
}

const ACTION_OPTIONS: ActionKind[] = ["read", "write", "delete"]
const ROLE_OPTIONS = ["owner", "admin", "member", "viewer"]

function toggleInList<T extends string>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}

export default function HitlApprovalsPage() {
  const { loading: authLoading } = useAuth()
  const { isAdmin: viewAdmin, membershipLoading } = useViewModeSafe()
  const { isAdmin: orgIsAdmin, loading: orgAdminLoading } = useOrgAdmin()
  const isAdmin = viewAdmin || orgIsAdmin
  const onSectionChange = useSettingsSectionNav("approvals")
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  if (authLoading || membershipLoading || orgAdminLoading) {
    return (
      <AppShell title="Settings">
        <SettingsShell
          activeSection="approvals"
          isAdmin={isAdmin}
          onSectionChange={onSectionChange}
          >
          <div className="flex h-64 items-center justify-center p-4 text-muted-foreground md:p-6">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading…
          </div>
        </SettingsShell>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <SettingsShell
        activeSection="approvals"
        isAdmin={isAdmin}
        mobileMenuOpen={mobileMenuOpen}
        onMobileMenuOpenChange={setMobileMenuOpen}
        onSectionChange={onSectionChange}
      >
        {isAdmin ? <ApprovalsContent /> : <ApprovalsDenied />}
      </SettingsShell>
    </AppShell>
  )
}

function ApprovalsDenied() {
  return (
    <div className="m-4 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] p-8 text-center md:m-6">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-[10px] border border-[color:var(--g-border-default)] bg-[color:var(--g-emerald-pale)]">
        <ShieldCheck className="h-6 w-6 text-muted-foreground" />
      </div>
      <h2 className="text-lg font-semibold text-foreground">Admin access required</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
        Human-in-the-loop policies can only be managed by workspace owners and admins.
      </p>
      <Button variant="outline" className="mt-6" asChild>
        <Link href="/settings">Back to settings</Link>
      </Button>
    </div>
  )
}

function ApprovalsContent() {
  const { data, error, isLoading, mutate } = useSWR<{ policies: HitlPolicy[] }>(
    "/api/settings/hitl-policies",
    fetcher,
    { revalidateOnFocus: false },
  )
  const { data: liteData } = useSWR<{ departments?: Array<{ id: string; name: string }> }>(
    "/api/settings/lite-seats",
    fetcher,
    { revalidateOnFocus: false },
  )
  const { data: teamData } = useSWR<{ team?: User[] }>("/api/settings/team", fetcher, {
    revalidateOnFocus: false,
  })

  const departments = liteData?.departments ?? []
  const team = teamData?.team ?? []
  const policies = data?.policies ?? []
  const enabledCount = policies.filter((policy) => policy.enabled).length

  const [name, setName] = useState("Write & delete approval")
  const [scopeType, setScopeType] = useState<ScopeType>("org")
  const [departmentId, setDepartmentId] = useState("")
  const [subjectUserId, setSubjectUserId] = useState("")
  const [actionKinds, setActionKinds] = useState<ActionKind[]>(["write", "delete"])
  const [approverRoles, setApproverRoles] = useState<string[]>(["admin", "owner"])
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const departmentNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const dept of departments) {
      map.set(String(dept.id), String(dept.name || dept.id))
    }
    return map
  }, [departments])

  const userLabelById = useMemo(() => {
    const map = new Map<string, string>()
    for (const member of team) {
      const id = String(member.id || "")
      if (!id) continue
      map.set(id, String(member.email || member.full_name || id))
    }
    return map
  }, [team])

  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error("Name is required")
      return
    }
    if (actionKinds.length === 0) {
      toast.error("Select at least one action: read, write, or delete")
      return
    }
    if (scopeType === "department" && !departmentId) {
      toast.error("Choose a department")
      return
    }
    if (scopeType === "user" && !subjectUserId) {
      toast.error("Choose a user")
      return
    }
    setSaving(true)
    try {
      await settingsApi.createHitlPolicy({
        name: name.trim(),
        enabled: true,
        scope_type: scopeType,
        department_id: scopeType === "department" ? departmentId : null,
        subject_user_id: scopeType === "user" ? subjectUserId : null,
        action_kinds: actionKinds,
        approver_roles: approverRoles.length ? approverRoles : ["admin", "owner"],
        required_approvals: 1,
      })
      toast.success("HITL policy created")
      setName("Write & delete approval")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create policy")
    } finally {
      setSaving(false)
    }
  }

  const handleToggleEnabled = async (policy: HitlPolicy) => {
    try {
      await settingsApi.updateHitlPolicy(policy.id, { enabled: !policy.enabled })
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update policy")
    }
  }

  const handleDelete = async (policyId: string) => {
    setDeletingId(policyId)
    try {
      await settingsApi.deleteHitlPolicy(policyId)
      toast.success("Policy deleted")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete policy")
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="relative space-y-6">
      <ApprovalRulesSettings />

      <header className="flex flex-col gap-1 pt-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-medium text-foreground">Policies by team or person</h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            Fine-tune who approves what for a department or a person. More specific rules win when several match.
          </p>
        </div>
        <p className="text-sm tabular-nums text-muted-foreground" data-testid="hitl-policy-counts">
          <span className="font-semibold text-foreground">{policies.length}</span>{" "}
          {policies.length === 1 ? "policy" : "policies"} ·{" "}
          <span className="font-semibold text-foreground">{enabledCount}</span> active
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section aria-labelledby="hitl-active-policies" className="min-w-0">
          <div className="mb-3">
            <h2 id="hitl-active-policies" className="text-base font-semibold text-foreground">
              Your policies
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Enable, pause, or remove rules without leaving Settings.
            </p>
          </div>

          {isLoading && !data ? (
            <div className="flex items-center py-10 text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading policies…
            </div>
          ) : error ? (
            <div className="border-l-2 border-destructive py-2 pl-3 text-sm text-destructive">
              Could not load HITL policies. If this is a new environment, apply the{" "}
              <code className="text-xs">hitl_policies</code> migration first.
            </div>
          ) : policies.length === 0 ? (
            <div className="border-y border-[color:var(--g-border-subtle)] py-8">
              <p className="text-sm font-medium text-foreground">No custom policies yet</p>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Write and delete actions still require admin/owner approval by default.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-default)]">
              {policies.map((policy) => (
                <li
                  key={policy.id}
                  className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-foreground">{policy.name}</p>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 text-xs font-medium",
                          policy.enabled ? "text-success" : "text-muted-foreground",
                        )}
                      >
                        <span
                          aria-hidden
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            policy.enabled ? "bg-success" : "bg-muted-foreground/60",
                          )}
                        />
                        {policy.enabled ? "Enabled" : "Disabled"}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      Scope:{" "}
                      {policy.scope_type === "org"
                        ? "Entire org"
                        : policy.scope_type === "department"
                          ? `Department · ${departmentNameById.get(policy.department_id || "") || policy.department_id}`
                          : `User · ${userLabelById.get(policy.subject_user_id || "") || policy.subject_user_id}`}
                      {" · "}
                      Actions: {(policy.action_kinds || []).join(", ") || "—"}
                      {" · "}
                      Approvers: {(policy.approver_roles || []).join(", ") || "—"}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button variant="outline" size="sm" onClick={() => handleToggleEnabled(policy)}>
                      {policy.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      disabled={deletingId === policy.id}
                      aria-label={`Delete policy ${policy.name}`}
                      onClick={() => handleDelete(policy.id)}
                    >
                      {deletingId === policy.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 border-l-2 border-[color:var(--g-brand)] py-1 pl-3">
            <p className="flex items-center gap-2 text-sm font-medium text-foreground">
              <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
              Default protection
            </p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              Write and delete actions already require admin or owner approval. Custom policies let you
              tighten or broaden that for specific teams.
            </p>
          </div>
        </section>

        <motion.aside
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          aria-labelledby="hitl-create-policy"
          className="lg:border-l lg:border-[color:var(--g-border-subtle)] lg:pl-6"
        >
          <div className="mb-5 flex items-start gap-2">
            <Plus className="mt-0.5 h-4 w-4 text-muted-foreground" aria-hidden />
            <div>
              <h2 id="hitl-create-policy" className="text-base font-semibold text-foreground">
                Create policy
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Define who needs approval and who can grant it.
              </p>
            </div>
          </div>

          <div className="space-y-5">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Name</label>
              <Input
                className="mt-1.5 h-10 rounded-[var(--np-radius-md)]"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Sales write approval"
              />
            </div>

            <ChipGroup
              label="Applies to"
              options={[
                { value: "org", label: "Entire org" },
                { value: "department", label: "Department" },
                { value: "user", label: "User" },
              ]}
              value={scopeType}
              onChange={(value) => setScopeType(value as ScopeType)}
              exclusive
            />

            {scopeType === "department" ? (
              <div>
                <label className="text-xs font-medium text-muted-foreground">Department</label>
                <select
                  className="mt-1.5 h-11 w-full rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-3 text-sm"
                  value={departmentId}
                  onChange={(e) => setDepartmentId(e.target.value)}
                >
                  <option value="">Select department…</option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.id}>
                      {dept.name}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {scopeType === "user" ? (
              <div>
                <label className="text-xs font-medium text-muted-foreground">User</label>
                <select
                  className="mt-1.5 h-11 w-full rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-3 text-sm"
                  value={subjectUserId}
                  onChange={(e) => setSubjectUserId(e.target.value)}
                >
                  <option value="">Select user…</option>
                  {team.map((member) => {
                    const id = String(member.id || "")
                    return (
                      <option key={id} value={id}>
                        {member.email || member.full_name || id}
                      </option>
                    )
                  })}
                </select>
              </div>
            ) : null}

            <ChipGroup
              label="Actions that need approval"
              options={ACTION_OPTIONS.map((kind) => ({ value: kind, label: kind }))}
              values={actionKinds}
              onToggle={(value) => setActionKinds((prev) => toggleInList(prev, value as ActionKind))}
            />

            <ChipGroup
              label="Approver roles"
              options={ROLE_OPTIONS.map((role) => ({ value: role, label: role }))}
              values={approverRoles}
              onToggle={(value) => setApproverRoles((prev) => toggleInList(prev, value))}
            />

            <Button size="lg" className="w-full gap-2 sm:w-auto" onClick={handleCreate} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Add policy
            </Button>
          </div>
        </motion.aside>
      </div>
    </div>
  )
}

function ChipGroup({
  label,
  options,
  value,
  values,
  onChange,
  onToggle,
  exclusive,
}: {
  label: string
  options: Array<{ value: string; label: string }>
  value?: string
  values?: string[]
  onChange?: (value: string) => void
  onToggle?: (value: string) => void
  exclusive?: boolean
}) {
  return (
    <div>
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <div className="mt-1.5 flex flex-wrap gap-2">
        {options.map((option) => {
          const selected = exclusive ? value === option.value : Boolean(values?.includes(option.value))
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => (exclusive ? onChange?.(option.value) : onToggle?.(option.value))}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-sm capitalize transition-colors",
                // Selected chips were hardcoded slate-900/white (theme-blind, so
                // they stayed near-black in dark mode) and off-palette sky. Both
                // selected states now use primary; exclusive stays solid so it
                // still reads as single-choice next to the tinted multi-select.
                selected
                  ? exclusive
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-primary/40 bg-primary/10 text-foreground"
                  : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
