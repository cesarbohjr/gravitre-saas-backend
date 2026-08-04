"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { GlowOrb } from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  ArrowRight,
  CheckCircle2,
  Inbox,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react"
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
          hideHeader
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
        hideHeader
      >
        {isAdmin ? <ApprovalsContent /> : <ApprovalsDenied />}
      </SettingsShell>
    </AppShell>
  )
}

function ApprovalsDenied() {
  return (
    <div className="m-4 rounded-2xl border border-border bg-card/60 p-8 text-center md:m-6">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
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
  const { data: teamData } = useSWR<{ team?: User[] }>(
    "/api/settings/team",
    fetcher,
    { revalidateOnFocus: false },
  )

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
    <div className="relative space-y-8 p-4 md:p-6">
      {/* Each settings hero used its own two-hue gradient (this one sky ->
          violet, team permissions emerald -> sky), so sibling pages in the same
          section looked unrelated. Both now share one primary wash. */}
      <div className="relative overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-br from-primary/10 via-card to-primary/5 p-6 md:p-8">
        <div className="pointer-events-none absolute -right-10 -top-10 opacity-70">
          <GlowOrb size={220} color="blue" intensity={0.25} />
        </div>
        <div className="pointer-events-none absolute -bottom-16 left-8 opacity-50">
          <GlowOrb size={180} color="violet" intensity={0.2} />
        </div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between"
        >
          <div className="max-w-xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground backdrop-blur">
              <ShieldCheck className="h-3.5 w-3.5 text-primary" />
              Governance
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground md:text-3xl">
              Human-in-the-loop
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Require approval before high-impact actions run. Scope by organization, department, or
              person — more specific rules win when several match.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:min-w-[240px]">
            <div className="rounded-2xl border border-border/70 bg-background/75 px-4 py-3 backdrop-blur">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Policies</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{policies.length}</p>
            </div>
            <div className="rounded-2xl border border-border/70 bg-background/75 px-4 py-3 backdrop-blur">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Active</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{enabledCount}</p>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-3xl border border-border bg-card/70 p-5 shadow-sm md:p-6"
        >
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-foreground">Create policy</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Define who needs approval and who can grant it.
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Plus className="h-5 w-5" />
            </div>
          </div>

          <div className="space-y-5">
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Name
              </label>
              <Input
                className="mt-1.5 h-11 rounded-xl"
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
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Department
                </label>
                <select
                  className="mt-1.5 h-11 w-full rounded-xl border border-border bg-secondary/60 px-3 text-sm"
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
                <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  User
                </label>
                <select
                  className="mt-1.5 h-11 w-full rounded-xl border border-border bg-secondary/60 px-3 text-sm"
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

            <Button size="lg" className="w-full gap-2 rounded-xl sm:w-auto" onClick={handleCreate} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Add policy
            </Button>
          </div>
        </motion.section>

        <motion.aside
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-4"
        >
          <div className="rounded-3xl border border-border bg-card/70 p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-success" />
              <h3 className="text-sm font-semibold text-foreground">Default protection</h3>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Write and delete actions already require admin or owner approval. Custom policies let
              you tighten or broaden that for specific teams.
            </p>
          </div>
          {/* Was hardcoded slate-900 + text-white, so this card stayed dark in
              light mode and ignored the theme. The sky-300 icon on it was the
              lowest-contrast text in Settings. Now themed via primary. */}
          <div className="rounded-3xl border border-primary/20 bg-primary p-5 text-primary-foreground shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Inbox className="h-4 w-4" />
              <h3 className="text-sm font-semibold">Decision Queue</h3>
            </div>
            <p className="text-sm leading-relaxed text-primary-foreground/80">
              Review pending approvals from operators and agents in one place.
            </p>
            <Button
              asChild
              variant="secondary"
              className="mt-4 w-full justify-between rounded-xl"
            >
              <Link href="/approvals">
                Open Decision Queue
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </motion.aside>
      </div>

      <section className="rounded-3xl border border-border bg-card/70 p-5 shadow-sm md:p-6">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-foreground">Active policies</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Enable, pause, or remove rules without leaving Settings.
            </p>
          </div>
        </div>

        {isLoading && !data ? (
          <div className="flex items-center py-10 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading policies…
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            Could not load HITL policies. If this is a new environment, apply the{" "}
            <code className="text-xs">hitl_policies</code> migration first.
          </div>
        ) : policies.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-secondary/20 px-6 py-10 text-center">
            <p className="text-sm font-medium text-foreground">No custom policies yet</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              Write and delete actions still require admin/owner approval by default.
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {policies.map((policy) => (
              <li
                key={policy.id}
                className="flex flex-col gap-3 rounded-2xl border border-border/80 bg-background/60 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-foreground">{policy.name}</p>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        policy.enabled
                          ? "bg-emerald-500/10 text-emerald-700"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
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
                  <Button variant="outline" size="sm" className="rounded-xl" onClick={() => handleToggleEnabled(policy)}>
                    {policy.enabled ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-xl text-destructive hover:text-destructive"
                    disabled={deletingId === policy.id}
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
      </section>
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
      <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
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
                selected
                  ? exclusive
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-sky-600/40 bg-sky-500/10 text-foreground"
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
