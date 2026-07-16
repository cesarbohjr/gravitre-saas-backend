"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2, Plus, ShieldCheck, Trash2 } from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
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
  const { user, loading: authLoading } = useAuth()
  const isAdmin = user?.role === "admin" || user?.role === "owner"

  const { data, error, isLoading, mutate } = useSWR<{ policies: HitlPolicy[] }>(
    isAdmin ? "/api/settings/hitl-policies" : null,
    fetcher,
    { revalidateOnFocus: false },
  )
  const { data: liteData } = useSWR<{ departments?: Array<{ id: string; name: string }> }>(
    isAdmin ? "/api/settings/lite-seats" : null,
    fetcher,
    { revalidateOnFocus: false },
  )
  const { data: teamData } = useSWR<{ team?: User[] }>(
    isAdmin ? "/api/settings/team" : null,
    fetcher,
    { revalidateOnFocus: false },
  )

  const departments = liteData?.departments ?? []
  const team = teamData?.team ?? []
  const policies = data?.policies ?? []

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

  if (authLoading) {
    return (
      <AppShell title="Human-in-the-loop">
        <div className="flex h-64 items-center justify-center text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading…
        </div>
      </AppShell>
    )
  }

  if (!isAdmin) {
    return (
      <AppShell title="Human-in-the-loop">
        <div className="mx-auto max-w-3xl px-4 py-8">
          <p className="text-sm text-muted-foreground">
            Admin or owner permission is required to manage human-in-the-loop policies.
          </p>
          <Button variant="ghost" className="mt-4" asChild>
            <Link href="/settings">Back to settings</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Human-in-the-loop">
      <div className="mx-auto max-w-3xl px-4 py-8 md:px-6">
        <div className="mb-8">
          <div className="mb-2 flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold text-foreground">Human-in-the-loop</h1>
          </div>
          <p className="text-sm text-muted-foreground text-pretty">
            Require approval for read, write, or delete actions by organization, department, or
            specific user. More specific rules (user → department → org) win when several match.
          </p>
        </div>

        <section className="mb-8 space-y-4 rounded-xl border border-border bg-card/40 p-4">
          <h2 className="text-sm font-medium text-foreground">Add policy</h2>
          <div>
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Name
            </label>
            <Input
              className="mt-1.5"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sales write approval"
            />
          </div>

          <div>
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Applies to
            </label>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {(["org", "department", "user"] as ScopeType[]).map((scope) => (
                <button
                  key={scope}
                  type="button"
                  onClick={() => setScopeType(scope)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-sm capitalize transition-colors",
                    scopeType === scope
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground",
                  )}
                >
                  {scope === "org" ? "Entire org" : scope}
                </button>
              ))}
            </div>
          </div>

          {scopeType === "department" ? (
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Department
              </label>
              <select
                className="mt-1.5 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm"
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
                className="mt-1.5 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm"
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

          <div>
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Actions that need approval
            </label>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {ACTION_OPTIONS.map((kind) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => setActionKinds((prev) => toggleInList(prev, kind))}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-sm capitalize transition-colors",
                    actionKinds.includes(kind)
                      ? "border-primary bg-primary/15 text-foreground"
                      : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground",
                  )}
                >
                  {kind}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Approver roles
            </label>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {ROLE_OPTIONS.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => setApproverRoles((prev) => toggleInList(prev, role))}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-sm capitalize transition-colors",
                    approverRoles.includes(role)
                      ? "border-primary bg-primary/15 text-foreground"
                      : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground",
                  )}
                >
                  {role}
                </button>
              ))}
            </div>
          </div>

          <Button size="sm" className="gap-2" onClick={handleCreate} disabled={saving}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
            Add policy
          </Button>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">Active policies</h2>
          {isLoading && !data ? (
            <div className="flex items-center py-8 text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading policies…
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              Could not load HITL policies. If this is a new environment, apply the{" "}
              <code className="text-xs">hitl_policies</code> migration first.
            </div>
          ) : policies.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No custom policies yet. Write and delete actions still require admin/owner approval by
              default.
            </p>
          ) : (
            <ul className="space-y-3">
              {policies.map((policy) => (
                <li
                  key={policy.id}
                  className="flex flex-col gap-3 rounded-xl border border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-foreground">{policy.name}</p>
                      {!policy.enabled ? (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">
                          Disabled
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
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
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggleEnabled(policy)}
                    >
                      {policy.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
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

        <div className="mt-8 flex flex-wrap gap-3">
          <Button variant="outline" asChild>
            <Link href="/approvals">Open Decision Queue</Link>
          </Button>
          <Button variant="ghost" asChild>
            <Link href="/settings">Back to settings</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
