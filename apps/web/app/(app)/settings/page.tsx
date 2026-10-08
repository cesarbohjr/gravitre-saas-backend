"use client"

import React, { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { 
  Loader2,
  Plus,
  Trash2,
} from "lucide-react"
import { apiFetch, fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { settingsApi } from "@/lib/api"
import type { BillingUsageResponse, LiteSeatDepartment, MesonAddon, User } from "@/types/api"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { OrganizationSettings } from "@/components/settings/organization-settings"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { SecuritySettings } from "@/components/settings/security-settings"
import { TeamSettings } from "@/components/settings/team-settings"
import { ApiKeysSettings } from "@/components/settings/api-keys-settings"
import { AIModelsSettings } from "@/components/settings/ai-models-settings"
import { WebhooksSettings } from "@/components/settings/webhooks-settings"
import { SettingsShell, canAccessSettingsSection } from "@/components/settings/settings-shell"
import { SETTINGS_SECTIONS, settingsHrefForSection, type SettingsSectionId } from "@/lib/settings-sections"
import { useOrgAdmin } from "@/lib/use-org-admin"

function LiteSeatsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(isAdmin ? "/api/settings/lite-seats" : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const [newDeptName, setNewDeptName] = useState("")
  const [newDeptSeats, setNewDeptSeats] = useState(0)
  const [memberEmailByDept, setMemberEmailByDept] = useState<Record<string, string>>({})
  const [memberRoleByDept, setMemberRoleByDept] = useState<Record<string, "viewer" | "admin">>({})
  const [sendInviteByDept, setSendInviteByDept] = useState<Record<string, boolean>>({})
  const [assignByDept, setAssignByDept] = useState<
    Record<string, { resource_type: "workflow" | "agent" | "council" | "knowledge_pack"; resource_id: string }>
  >({})
  const [isSaving, setIsSaving] = useState(false)
  if (!isAdmin) return <p className="text-sm text-muted-foreground">Admin or owner permission is required to manage Lite seats.</p>
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading Lite seats…</p>
  if (error) return <div role="alert" className="space-y-3"><p className="text-sm">Could not load Lite seats.</p><Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry Lite seats</Button></div>
  const summary = (
    data as {
      summary?: {
        included: number | null
        included_display?: string
        unlimited?: boolean
        allocated: number
        used: number
        plan_code?: string
      }
    } | undefined
  )?.summary
  const departments = ((data as { departments?: LiteSeatDepartment[] } | undefined)?.departments ?? []) as LiteSeatDepartment[]

  const handleAddDepartment = async () => {
    if (!newDeptName.trim()) return
    setIsSaving(true)
    try {
      await settingsApi.createDepartment({
        name: newDeptName.trim(),
        lite_seat_allocation: Math.max(0, newDeptSeats),
      })
      toast.success("Department added")
      setNewDeptName("")
      setNewDeptSeats(0)
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to add department:", err)
      toast.error("Failed to add department")
    } finally {
      setIsSaving(false)
    }
  }

  const handleUpdateAllocation = async (department: LiteSeatDepartment, delta: number) => {
    const nextValue = Math.max(0, Number(department.lite_seat_allocation ?? 0) + delta)
    setIsSaving(true)
    try {
      await settingsApi.updateDepartment({
        id: department.id,
        lite_seat_allocation: nextValue,
      })
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to update allocation:", err)
      toast.error("Failed to update seat allocation")
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteDepartment = async (departmentId: string, name: string) => {
    if (!confirm(`Delete department "${name}"?`)) return
    setIsSaving(true)
    try {
      await settingsApi.deleteDepartment(departmentId)
      toast.success("Department removed")
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to delete department:", err)
      toast.error("Failed to remove department")
    } finally {
      setIsSaving(false)
    }
  }

  const handleInviteMember = async (departmentId: string) => {
    const email = (memberEmailByDept[departmentId] || "").trim()
    const role = memberRoleByDept[departmentId] === "admin" ? "admin" : "viewer"
    const sendInvite = sendInviteByDept[departmentId] ?? true
    if (!email) {
      toast.error("Enter a member email")
      return
    }
    setIsSaving(true)
    try {
      const response = await settingsApi.addDepartmentMember({
        department_id: departmentId,
        user_email: email,
        role,
        send_invite: sendInvite,
      })
      const invitePayload = (response as { invite?: { invite_email_sent?: boolean } }).invite
      toast.success(
        invitePayload?.invite_email_sent
          ? "Lite seat assigned and invite email sent"
          : "Lite seat assigned",
      )
      setMemberEmailByDept((prev) => ({ ...prev, [departmentId]: "" }))
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign member")
    } finally {
      setIsSaving(false)
    }
  }

  const handleAssignResource = async (departmentId: string) => {
    const draft = assignByDept[departmentId] || { resource_type: "workflow" as const, resource_id: "" }
    const resourceId = draft.resource_id.trim()
    if (!resourceId) {
      toast.error("Enter a workflow, agent, council, or knowledge pack id")
      return
    }
    setIsSaving(true)
    try {
      const res = await apiFetch("/api/departments/assignments", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          department_id: departmentId,
          resource_type: draft.resource_type,
          resource_id: resourceId,
        }),
      })
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}))
        throw new Error(
          (payload as { detail?: string; error?: string }).detail ||
            (payload as { error?: string }).error ||
            `Assign failed (${res.status})`,
        )
      }
      toast.success("Assigned to department")
      setAssignByDept((prev) => ({
        ...prev,
        [departmentId]: { resource_type: draft.resource_type, resource_id: "" },
      }))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign resource")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-divide py-3">
        <p className="text-sm font-medium text-foreground">Gravitre Lite seats</p>
        <p className="text-xs text-muted-foreground mt-1">
          Included: {summary?.included_display ?? (summary?.unlimited ? "Unlimited" : String(summary?.included ?? 0))}
          {" | "}Allocated: {summary?.allocated ?? 0}
          {" | "}Used: {summary?.used ?? 0}
          {summary?.plan_code ? ` · Plan ${summary.plan_code}` : ""}
        </p>
      </div>

      <div className="space-y-3">
        {departments.map((department) => (
          <div key={department.id} className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-foreground">{department.name}</p>
                <p className="text-xs text-muted-foreground">
                  Used {department.used_seats ?? 0} / Allocated {department.lite_seat_allocation ?? 0}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleUpdateAllocation(department, -1)}
                  disabled={!isAdmin || isSaving}
                >
                  -
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleUpdateAllocation(department, 1)}
                  disabled={!isAdmin || isSaving}
                >
                  +
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => handleDeleteDepartment(department.id, department.name)}
                  disabled={!isAdmin || isSaving}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={memberEmailByDept[department.id] ?? ""}
                onChange={(event) =>
                  setMemberEmailByDept((prev) => ({
                    ...prev,
                    [department.id]: event.target.value,
                  }))
                }
                placeholder="Assign Lite user by email"
                disabled={!isAdmin || isSaving}
              />
              <select
                className="h-9 rounded-md border border-border bg-secondary px-2 text-sm sm:w-[220px]"
                value={memberRoleByDept[department.id] ?? "viewer"}
                disabled={!isAdmin || isSaving}
                onChange={(event) =>
                  setMemberRoleByDept((prev) => ({
                    ...prev,
                    [department.id]: event.target.value === "admin" ? "admin" : "viewer",
                  }))
                }
              >
                <option value="viewer">Lite user</option>
                <option value="admin">Department manager</option>
              </select>
              <Button
                size="sm"
                variant="secondary"
                disabled={!isAdmin || isSaving}
                onClick={() => handleInviteMember(department.id)}
              >
                Assign seat
              </Button>
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="rounded border-border"
                  checked={sendInviteByDept[department.id] ?? true}
                  onChange={(event) =>
                    setSendInviteByDept((prev) => ({
                      ...prev,
                      [department.id]: event.target.checked,
                    }))
                  }
                  disabled={!isAdmin || isSaving}
                />
                Send Gravitre invite email so this user can verify and onboard
              </label>
            </div>
            <div className="mt-3 space-y-2 border-t border-divide pt-3">
              <p className="text-xs font-medium text-foreground">Assign workflow / agent / council / knowledge pack</p>
              <p className="text-[11px] text-muted-foreground">
                Lite seats in this department can run assigned workflows (Meson build still requires a full seat).
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <select
                  className="h-9 rounded-md border border-border bg-secondary px-2 text-sm"
                  value={(assignByDept[department.id] || { resource_type: "workflow" }).resource_type}
                  disabled={!isAdmin || isSaving}
                  onChange={(event) =>
                    setAssignByDept((prev) => ({
                      ...prev,
                      [department.id]: {
                        resource_type: event.target.value as "workflow" | "agent" | "council" | "knowledge_pack",
                        resource_id: prev[department.id]?.resource_id || "",
                      },
                    }))
                  }
                >
                  <option value="workflow">Workflow</option>
                  <option value="agent">Agent</option>
                  <option value="council">Council</option>
                  <option value="knowledge_pack">Knowledge pack</option>
                </select>
                <Input
                  value={assignByDept[department.id]?.resource_id ?? ""}
                  onChange={(event) =>
                    setAssignByDept((prev) => ({
                      ...prev,
                      [department.id]: {
                        resource_type: prev[department.id]?.resource_type || "workflow",
                        resource_id: event.target.value,
                      },
                    }))
                  }
                  placeholder="Resource id"
                  disabled={!isAdmin || isSaving}
                />
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!isAdmin || isSaving}
                  onClick={() => handleAssignResource(department.id)}
                >
                  Assign resource
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-3 border-b border-divide py-3">
        <p className="text-sm font-medium text-foreground">Add department</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            value={newDeptName}
            onChange={(e) => setNewDeptName(e.target.value)}
            placeholder="Department name"
            disabled={!isAdmin || isSaving}
            className="bg-secondary border-border"
          />
          <Input
            value={String(newDeptSeats)}
            onChange={(e) => setNewDeptSeats(Number.parseInt(e.target.value || "0", 10) || 0)}
            placeholder="Seat allocation"
            disabled={!isAdmin || isSaving}
            className="bg-secondary border-border"
          />
        </div>
        <Button
          size="sm"
          className="gap-2"
          onClick={handleAddDepartment}
          disabled={!isAdmin || isSaving || !newDeptName.trim()}
        >
          {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Add department
        </Button>
      </div>
    </div>
  )
}

function MesonAddonsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(isAdmin ? "/api/settings/meson-addons" : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const [isSaving, setIsSaving] = useState(false)
  if (!isAdmin) return <p className="text-sm text-muted-foreground">Admin or owner permission is required to manage Meson addons.</p>
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading Meson addons…</p>
  if (error) return <div role="alert" className="space-y-3"><p className="text-sm">Could not load Meson addons.</p><Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry Meson addons</Button></div>
  const addons = ((data as { addons?: MesonAddon[] } | undefined)?.addons ?? []) as MesonAddon[]
  const monthlyTotal = Number((data as { monthly_total_usd?: number } | undefined)?.monthly_total_usd ?? 0)
  const voice = (data as { voice?: { enabled?: boolean; note?: string; billing_href?: string } } | undefined)?.voice

  const handleToggle = async (addon: MesonAddon) => {
    setIsSaving(true)
    try {
      await settingsApi.toggleMesonAddon(addon.code, !addon.enabled)
      toast.success(`${addon.name} ${addon.enabled ? "disabled" : "enabled"}`)
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to toggle addon:", err)
      toast.error("Failed to update addon")
    } finally {
      setIsSaving(false)
    }
  }

  const handleVoiceToggle = async () => {
    if (!isAdmin) return
    setIsSaving(true)
    try {
      const res = await apiFetch("/api/settings/voice-access", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ enabled: !voice?.enabled }),
      })
      if (!res.ok) throw new Error("voice toggle failed")
      toast.success(`Voice ${voice?.enabled ? "disabled" : "enabled"} for this organization`)
      await mutate()
    } catch {
      toast.error("Failed to update voice access")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">Internal voice (staff chat)</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Policy control for Text|Voice in Gravitre chat. On by default. This is
              staff speaking to your org AI — not outbound phone calls (Twilio/Vapi connectors).
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Status: {voice?.enabled === false ? "Off for this org" : "On"}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Button
              variant={voice?.enabled === false ? "default" : "outline"}
              size="sm"
              onClick={handleVoiceToggle}
              disabled={!isAdmin || isSaving}
            >
              {voice?.enabled === false ? "Allow voice" : "Disable voice"}
            </Button>
          </div>
        </div>
      </div>

      {addons.length > 0 ? (
        <>
          <div className="border-b border-divide py-3">
            <p className="text-sm font-medium text-foreground">Monthly addon total</p>
            <p className="text-lg font-semibold text-foreground mt-1">${monthlyTotal.toFixed(2)}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Sum of enabled Stripe-wired Meson addons only.
            </p>
          </div>
          <div className="space-y-3">
            {addons.map((addon) => (
              <div key={addon.code} className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">{addon.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{addon.description}</p>
                    <p className="text-xs text-muted-foreground mt-1">${addon.monthly_price_usd}/mo</p>
                  </div>
                  <Button
                    variant={addon.enabled ? "outline" : "default"}
                    size="sm"
                    onClick={() => handleToggle(addon)}
                    disabled={!isAdmin || isSaving}
                  >
                    {addon.enabled ? "Disable" : "Enable"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
          <p className="text-sm font-medium text-foreground">No billable Meson addons</p>
          <p className="mt-1 text-xs text-muted-foreground">
            There are no Stripe-wired Meson addons available for purchase. Voice is plan-included above.
          </p>
        </div>
      )}
    </div>
  )
}

function SoftUsageMeter({
  label,
  used,
  included,
  unit,
  hint,
  note,
}: {
  label: string
  used: number
  included?: number | null
  unit?: string
  hint?: string
  note?: string
}) {
  const hasLimit = typeof included === "number" && included > 0
  const pct = hasLimit ? Math.min(100, (used / included) * 100) : 0

  return (
    <div className="flex flex-col border-b border-divide py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {hasLimit ? (
          <span className="text-xs tabular-nums text-muted-foreground">{Math.round(pct)}%</span>
        ) : null}
      </div>
      <div className="mb-3 flex items-baseline gap-1.5">
        <p className="text-2xl font-semibold tracking-tight tabular-nums text-foreground">
          {used.toLocaleString()}
        </p>
        {hasLimit ? (
          <p className="text-sm tabular-nums text-muted-foreground">
            / {included.toLocaleString()}
            {unit ? ` ${unit}` : ""}
          </p>
        ) : unit ? (
          <p className="text-sm text-muted-foreground">{unit}</p>
        ) : null}
      </div>
      {hasLimit ? (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted/80">
          <div
            className={cn("h-full rounded-full", pct >= 90 ? "bg-warning" : "bg-primary/70")}
            style={{ width: `${pct}%` }}
          />
        </div>
      ) : null}
      {note ? <p className="mt-2 text-[11px] font-medium text-warning">{note}</p> : null}
      {hint ? <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function BillingUsageSettings() {
  const { data, isLoading, mutate } = useSWR("/api/settings/billing-usage", apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 30000,
  })
  const usage = (data ?? {}) as BillingUsageResponse
  const totals = usage.totals ?? { outputs: 0, workflow_runs: 0, api_calls: 0, ai_tokens: 0, research_lookups: 0 }
  const showResearch = Boolean(usage.research_lookups_billing_visible)
  const researchUsed = totals.research_lookups ?? 0
  const researchIncluded = usage.included_research_lookups ?? 0
  const researchOverage = usage.overage_research_lookups ?? 0
  const outputOverageUsd = Number(usage.overage_cost_usd ?? 0)
  const researchOverageUsd = Number(usage.overage_research_cost_usd ?? 0)
  const totalEstimatedOverage = outputOverageUsd + (showResearch ? researchOverageUsd : 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Usage for the current billing cycle</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => mutate()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <SoftUsageMeter
          label="Outputs"
          used={totals.outputs}
          included={usage.included_outputs}
          unit="outputs"
          note={
            usage.overage_outputs
              ? `${usage.overage_outputs} overage`
              : undefined
          }
        />
        <SoftUsageMeter label="Workflow runs" used={totals.workflow_runs} unit="runs" />
        <SoftUsageMeter label="API Calls" used={totals.api_calls} unit="calls" />
        <SoftUsageMeter
          label="AI Credits"
          used={totals.ai_tokens}
          included={usage.ai_credits_included}
          unit="credits"
          hint="LLM tokens only — separate from Research Lookups"
        />
        {showResearch ? (
          <SoftUsageMeter
            label="Research lookups"
            used={researchUsed}
            included={researchIncluded}
            unit="lookups"
            hint="Live internet research — billed separately from AI credits"
            note={
              researchOverage
                ? `${researchOverage} overage @ $${(usage.research_lookup_overage_rate_usd ?? 0.35).toFixed(2)}/lookup`
                : undefined
            }
          />
        ) : null}
      </div>

      <div className="border-b border-divide py-3">
        <p className="text-sm font-medium text-foreground">Estimated overage</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">${totalEstimatedOverage.toFixed(2)}</p>
        {showResearch && researchOverageUsd > 0 ? (
          <p className="mt-1 text-[11px] text-muted-foreground">
            Includes ${researchOverageUsd.toFixed(2)} research lookup overage
          </p>
        ) : null}
        {isLoading ? <p className="mt-2 text-xs text-muted-foreground">Loading usage…</p> : null}
      </div>
    </div>
  )
}

function SettingsContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { user } = useAuth()
  // `isAdmin` is server-confirmed and gates every admin-only control below;
  // `showAdmin` may come from the last confirmed answer cached for this
  // user + org, so the admin nav renders immediately and corrects itself.
  const { isAdmin, showAdmin, pending: adminPending } = useOrgAdmin()
  const sectionParam = (searchParams.get("section") || "organization") as SettingsSectionId
  const [activeSection, setActiveSection] = useState<SettingsSectionId>(sectionParam)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const section = searchParams.get("section")
    if (section === "enterprise") {
      router.replace("/settings/enterprise")
      return
    }
    if (section === "federation") {
      router.replace("/settings/federation")
      return
    }
    if (section === "environments") {
      router.replace("/environments")
      return
    }
    if (section === "profile") {
      router.replace("/settings/profile")
      return
    }
    if (section === "organizations") {
      router.replace("/settings/organizations")
      return
    }
    if (section === "billing" || section === "billing-usage") {
      router.replace("/settings/billing")
      return
    }
    if (section === "approvals") {
      router.replace("/settings/approvals")
      return
    }
    if (section === "permissions") {
      router.replace("/settings/team/permissions")
      return
    }
    if (section === "audit") {
      router.replace("/audit")
      return
    }
    if (section) {
      setActiveSection(section as SettingsSectionId)
    }
  }, [searchParams, router])

  const { data: orgData, error: orgError, isLoading: orgLoading, mutate: mutateOrg } = useSWR(
    user ? "/api/settings/organization" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const { data: teamData, error: teamError, isLoading: teamLoading, mutate: mutateTeam } = useSWR(
    user ? "/api/settings/team" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const organization = (orgData as { organization?: Record<string, unknown> } | undefined)?.organization
  const team = ((teamData as { team?: User[] } | undefined)?.team ?? []) as User[]

  const renderContent = () => {
    if (!canAccessSettingsSection(activeSection, isAdmin)) {
      // Admin-only section before the role is confirmed: keep the settings
      // layout up and wait inline, instead of flashing "permission required"
      // at an admin (or blocking the whole page on the role round trip).
      if (adminPending || showAdmin) {
        return (
          <p role="status" className="py-6 text-sm text-muted-foreground">
            Checking admin access…
          </p>
        )
      }
      return (
        <div className="border-b border-divide py-3 text-sm text-muted-foreground">
          Admin or owner permission is required to manage this section.
        </div>
      )
    }

    if (activeSection === "organization" || !SETTINGS_SECTIONS.some(section => section.id === activeSection)) {
      if (orgLoading) return <p role="status" className="py-6 text-sm text-muted-foreground">Loading organization settings…</p>
      if (orgError || !organization) return <div role="alert" className="space-y-3 py-4">
        <p className="text-sm">Could not load organization settings. Try again before making changes.</p>
        <Button variant="outline" className="min-h-11" onClick={() => void mutateOrg()}>Retry organization</Button>
      </div>
    }
    switch (activeSection) {
      case "organization":
        return (
          <OrganizationSettings
            key={String(organization?.id ?? "organization")}
            orgData={organization!}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateOrg()
            }}
          />
        )
      case "ai-models": return <AIModelsSettings isAdmin={isAdmin} />
      case "security": return <SecuritySettings />
      case "api-keys": return <ApiKeysSettings isAdmin={isAdmin} />
      case "notifications": return <NotificationSettings isAdmin={isAdmin} />
      case "team":
        return (
          <TeamSettings
            members={team}
            isLoading={teamLoading}
            error={teamError}
            onRetry={() => void mutateTeam()}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateTeam()
            }}
          />
        )
      case "lite-seats":
        return <LiteSeatsSettings isAdmin={isAdmin} />
      case "meson-addons":
        return <MesonAddonsSettings isAdmin={isAdmin} />
      case "webhooks": return <WebhooksSettings isAdmin={isAdmin} />
      case "billing-usage":
      case "billing":
      case "approvals":
      case "permissions":
      case "audit":
      case "enterprise":
      case "federation":
      case "environments":
      case "profile":
      case "organizations":
        return (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Opening…
          </div>
        )
      default:
        return (
          <OrganizationSettings
            key={String(organization?.id ?? "organization")}
            orgData={organization!}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateOrg()
            }}
          />
        )
    }
  }

  const handleSectionChange = (section: SettingsSectionId) => {
    const href = settingsHrefForSection(section)
    if (href.startsWith("/settings?") || href === "/settings") {
      setActiveSection(section)
      router.push(href)
      return
    }
    router.push(href)
  }

  return (
    <div data-composition="configure" className="h-full min-h-0">
      <SettingsShell
      activeSection={activeSection}
      onSectionChange={handleSectionChange}
      isAdmin={showAdmin}
      mobileMenuOpen={mobileMenuOpen}
      onMobileMenuOpenChange={setMobileMenuOpen}
    >
      {renderContent()}
      </SettingsShell>
    </div>
  )
}

export default function SettingsPage() {
  return (
    <AppShell title="Settings">
      <Suspense fallback={<div className="flex h-full items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" /></div>}>
        <SettingsContent />
      </Suspense>
    </AppShell>
  )
}
