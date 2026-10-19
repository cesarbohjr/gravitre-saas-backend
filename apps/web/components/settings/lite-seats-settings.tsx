"use client"

import { useState } from "react"
import useSWR from "swr"
import { Loader2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiFetch, fetcher as apiFetcher } from "@/lib/fetcher"
import { settingsApi } from "@/lib/api"
import type { LiteSeatDepartment } from "@/types/api"

export function LiteSeatsSettings({ isAdmin }: { isAdmin: boolean }) {
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
