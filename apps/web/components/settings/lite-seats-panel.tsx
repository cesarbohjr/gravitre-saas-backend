"use client"

/** Side panel for one Lite seats department (design p15 aside). */
import { useEffect, useRef, useState } from "react"
import useSWR from "swr"
import { Loader2, Mail, Minus, Plus, Trash2, X } from "lucide-react"
import { toast } from "@/components/agents/overlays/toast"
import { settingsApi } from "@/lib/api"
import {
  LITE_RESOURCE_TYPES,
  assignmentsKey,
  liteApi,
  loadResourceOptions,
  membersKey,
  type LiteAssignment,
  type LiteDepartment,
  type LiteResourceOption,
  type LiteResourceType,
} from "@/lib/settings-api/lite"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { SetError, SetNote, SetSkeleton, avatarTone, initialsOf } from "./settings-kit"

const SAVE_DELAY_MS = 600

export function LiteSeatsPanel({
  department,
  allocation,
  onDraftAllocation,
  onChanged,
  onDeleted,
}: {
  department: LiteDepartment
  /** Allocation shown now (server value or an unsaved +/- draft). */
  allocation: number
  /** Set the draft allocation, or null to fall back to the server value. */
  onDraftAllocation: (value: number | null) => void
  onChanged: () => Promise<unknown>
  onDeleted: () => void
}) {
  const used = Number(department.used_seats || 0)
  const free = Math.max(allocation - used, 0)

  // Seat allocation: update on every click, save once the clicks settle.
  const pending = useRef<number | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [savingSeats, setSavingSeats] = useState(false)
  const saveAllocation = async (value: number) => {
    setSavingSeats(true)
    try {
      await settingsApi.updateDepartment({ id: department.id, lite_seat_allocation: value })
      await onChanged()
      onDraftAllocation(null)
    } catch (err) {
      onDraftAllocation(null)
      toast.error(err instanceof Error ? `Seats not saved: ${err.message}` : "Seats not saved. Try again.")
    } finally {
      setSavingSeats(false)
    }
  }
  const step = (delta: number) => {
    const next = Math.max(0, allocation + delta)
    if (next === allocation) return
    pending.current = next
    onDraftAllocation(next)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      const value = pending.current
      pending.current = null
      timer.current = null
      if (value !== null) void saveAllocation(value)
    }, SAVE_DELAY_MS)
  }
  useEffect(
    () => () => {
      // Switching departments mid-click still saves the last value.
      if (timer.current) clearTimeout(timer.current)
      if (pending.current !== null) {
        const value = pending.current
        pending.current = null
        void settingsApi
          .updateDepartment({ id: department.id, lite_seat_allocation: value })
          .then(() => onChanged())
          .catch(() => toast.error("Seats not saved. Try again."))
          .finally(() => onDraftAllocation(null))
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unmount only
    [],
  )

  // Delete
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const handleDelete = async () => {
    setDeleting(true)
    try {
      await settingsApi.deleteDepartment(department.id)
      toast.success("Department removed")
      setConfirmDelete(false)
      onDeleted()
      await onChanged()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove department")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div className="ls-side-head">
        <div style={{ minWidth: 0 }}>
          <div className="gs-eyebrow">Department</div>
          <h3>{department.name || "Untitled department"}</h3>
        </div>
        <button
          type="button"
          className="gs-iconbtn danger"
          aria-label={`Delete ${department.name || "department"}`}
          onClick={() => setConfirmDelete(true)}
        >
          <Trash2 size={16} aria-hidden />
        </button>
      </div>

      <div className="ls-seats">
        <div>
          <div className="l">Seats allocated</div>
          <div className="v" aria-live="polite">
            {allocation}
          </div>
          <div className="s">
            {used} in use, {free} free{savingSeats ? " · Saving…" : ""}
          </div>
        </div>
        <div className="ls-row">
          <button
            type="button"
            className="gs-btn line sm icon"
            aria-label="Remove a seat"
            disabled={allocation <= 0}
            onClick={() => step(-1)}
          >
            <Minus size={16} aria-hidden />
          </button>
          <button type="button" className="gs-btn line sm icon" aria-label="Add a seat" onClick={() => step(1)}>
            <Plus size={16} aria-hidden />
          </button>
        </div>
      </div>

      <AssignUser department={department} free={free} onChanged={onChanged} />
      <AssignedResources department={department} onChanged={onChanged} />

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {department.name || "this department"}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its Lite seats, assigned users and assigned resources are removed. Users keep their organization
              membership.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Keep department</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault()
                void handleDelete()
              }}
              disabled={deleting}
            >
              {deleting ? "Deleting…" : "Delete department"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function AssignUser({
  department,
  free,
  onChanged,
}: {
  department: LiteDepartment
  free: number
  onChanged: () => Promise<unknown>
}) {
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<"viewer" | "admin">("viewer")
  const [sendInvite, setSendInvite] = useState(true)
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState<string | null>(null)
  const { data, error, isLoading, mutate } = useSWR(membersKey(department.id), () => liteApi.members(department.id), {
    revalidateOnFocus: false,
  })
  const members = data?.members ?? []

  const assign = async () => {
    const value = email.trim()
    if (!value) {
      toast.error("Enter a member email")
      return
    }
    setSaving(true)
    try {
      const response = await settingsApi.addDepartmentMember({
        department_id: department.id,
        user_email: value,
        role,
        send_invite: sendInvite,
      })
      const invite = (response as { invite?: { invite_email_sent?: boolean } }).invite
      toast.success(invite?.invite_email_sent ? "Lite seat assigned and invite email sent" : "Lite seat assigned")
      setEmail("")
      await Promise.all([mutate(), onChanged()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign member")
    } finally {
      setSaving(false)
    }
  }

  const remove = async (userId: string, label: string) => {
    setRemoving(userId)
    try {
      await settingsApi.removeDepartmentMember(department.id, userId)
      toast.success(`${label} removed from ${department.name || "the department"}`)
      await Promise.all([mutate(), onChanged()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove member")
    } finally {
      setRemoving(null)
    }
  }

  return (
    <div>
      <div className="ls-block-title">Assign a Lite user</div>
      <form
        style={{ marginTop: 8 }}
        onSubmit={(event) => {
          event.preventDefault()
          void assign()
        }}
      >
        <div className="ls-row">
          <label className="gs-input" style={{ minHeight: 40 }}>
            <Mail size={16} aria-hidden />
            <input
              type="email"
              aria-label="Email"
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={saving}
            />
          </label>
          <select
            className="gs-select"
            aria-label="Seat role"
            value={role}
            onChange={(e) => setRole(e.target.value === "admin" ? "admin" : "viewer")}
            disabled={saving}
          >
            <option value="viewer">Lite user</option>
            <option value="admin">Department manager</option>
          </select>
        </div>
        <label className="ls-check">
          <input type="checkbox" checked={sendInvite} onChange={(e) => setSendInvite(e.target.checked)} disabled={saving} />
          Send an invite email so they can verify and onboard
        </label>
        {free <= 0 ? (
          <SetNote tone="amber" className="ls-note">
            Every seat in this department is in use. Add a seat before assigning someone new.
          </SetNote>
        ) : null}
        <button type="submit" className="gs-btn dark sm" style={{ marginTop: 10 }} disabled={saving || !email.trim()}>
          {saving ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
          Assign seat
        </button>
      </form>

      <div style={{ marginTop: 14 }}>
        <div className="ls-block-sub">
          {members.length ? `${members.length} assigned` : "Assigned Lite users"}
        </div>
        {isLoading && !data ? (
          <SetSkeleton rows={2} label="Loading assigned users" />
        ) : error && !data ? (
          <SetError message="Could not load assigned users." onRetry={() => void mutate()} />
        ) : members.length === 0 ? (
          <span className="ls-muted">No one assigned yet</span>
        ) : (
          <ul className="ls-members" aria-label="Assigned Lite users">
            {members.map((m) => {
              const label = m.name || m.email || "Invited user"
              return (
                <li key={m.id} className="ls-member">
                  <span className={`gs-avatar round ${avatarTone(m.user_id)}`} aria-hidden style={{ width: 30, height: 30, fontSize: 11 }}>
                    {initialsOf(m.name || m.email)}
                  </span>
                  <span className="who">
                    <b>{label}</b>
                    <span>
                      {m.role === "admin" ? "Department manager" : "Lite user"}
                      {m.name && m.email ? ` · ${m.email}` : ""}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="gs-iconbtn danger"
                    aria-label={`Remove ${label}`}
                    disabled={removing !== null}
                    onClick={() => void remove(m.user_id, label)}
                  >
                    {removing === m.user_id ? <Loader2 size={15} className="animate-spin" aria-hidden /> : <X size={15} aria-hidden />}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

function useResourceOptions(type: LiteResourceType, enabled: boolean) {
  return useSWR<LiteResourceOption[]>(
    enabled && type !== "council" ? `lite-resource-options:${type}` : null,
    () => loadResourceOptions(type),
    { revalidateOnFocus: false },
  )
}

function AssignedResources({ department, onChanged }: { department: LiteDepartment; onChanged: () => Promise<unknown> }) {
  const { data, error, isLoading, mutate } = useSWR(assignmentsKey(department.id), () => liteApi.assignments(department.id), {
    revalidateOnFocus: false,
  })
  const assignments = data?.assignments ?? []
  const [type, setType] = useState<LiteResourceType>("workflow")
  const [resourceId, setResourceId] = useState("")
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState<string | null>(null)

  const hasType = (t: LiteResourceType) => type === t || assignments.some((a) => a.resource_type === t)
  const workflows = useResourceOptions("workflow", hasType("workflow"))
  const agents = useResourceOptions("agent", hasType("agent"))
  const packs = useResourceOptions("knowledge_pack", hasType("knowledge_pack"))
  const optionsFor = (t: LiteResourceType) =>
    t === "workflow" ? workflows : t === "agent" ? agents : t === "knowledge_pack" ? packs : null
  const current = optionsFor(type)
  const assignedIds = new Set(assignments.filter((a) => a.resource_type === type).map((a) => a.resource_id))
  const choices = (current?.data ?? []).filter((o) => !assignedIds.has(o.id))

  const nameOf = (a: LiteAssignment) => {
    const hit = optionsFor(a.resource_type)?.data?.find((o) => o.id === a.resource_id)
    return hit?.name ?? `${a.resource_id.slice(0, 8)}…`
  }
  const typeLabel = (t: LiteResourceType) => LITE_RESOURCE_TYPES.find((x) => x.id === t)?.label ?? t

  const assign = async () => {
    const id = resourceId.trim()
    if (!id) {
      toast.error(type === "council" ? "Enter a council id" : `Pick a ${typeLabel(type).toLowerCase()}`)
      return
    }
    setSaving(true)
    try {
      await liteApi.assign(department.id, type, id)
      toast.success("Assigned to department")
      setResourceId("")
      await Promise.all([mutate(), onChanged()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign resource")
    } finally {
      setSaving(false)
    }
  }

  const unassign = async (a: LiteAssignment) => {
    const key = `${a.resource_type}:${a.resource_id}`
    setRemoving(key)
    try {
      await liteApi.unassign(department.id, a.resource_type, a.resource_id)
      await Promise.all([mutate(), onChanged()])
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove resource")
    } finally {
      setRemoving(null)
    }
  }

  return (
    <div className="ls-divider">
      <div className="ls-block-title">Assigned resources</div>
      <div className="ls-block-sub">What Lite users here can run</div>
      {isLoading && !data ? (
        <SetSkeleton rows={1} label="Loading assigned resources" />
      ) : error && !data ? (
        <SetError message="Could not load assigned resources." onRetry={() => void mutate()} />
      ) : (
        <div className="ls-chips">
          {assignments.length === 0 ? (
            <span className="ls-muted">Nothing assigned yet</span>
          ) : (
            assignments.map((a) => {
              const key = `${a.resource_type}:${a.resource_id}`
              const name = nameOf(a)
              return (
                <span key={key} className="gs-chip" title={a.resource_id}>
                  <span className="ls-chip-type">{typeLabel(a.resource_type)}</span>
                  {name}
                  <button
                    type="button"
                    aria-label={`Remove ${name}`}
                    disabled={removing !== null}
                    onClick={() => void unassign(a)}
                  >
                    <X size={13} aria-hidden />
                  </button>
                </span>
              )
            })
          )}
        </div>
      )}
      <form
        className="ls-row"
        style={{ marginTop: 10 }}
        onSubmit={(event) => {
          event.preventDefault()
          void assign()
        }}
      >
        <select
          className="gs-select"
          aria-label="Resource type"
          value={type}
          onChange={(e) => {
            setType(e.target.value as LiteResourceType)
            setResourceId("")
          }}
          disabled={saving}
        >
          {LITE_RESOURCE_TYPES.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        {type === "council" ? (
          <label className="gs-input" style={{ minHeight: 40 }}>
            <input
              aria-label="Council id"
              placeholder="Council id"
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              disabled={saving}
            />
          </label>
        ) : (
          <select
            className="gs-select"
            aria-label={typeLabel(type)}
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
            disabled={saving || !current || current.isLoading || Boolean(current.error) || choices.length === 0}
          >
            <option value="">
              {current?.isLoading
                ? "Loading…"
                : current?.error
                  ? `Could not load ${typeLabel(type).toLowerCase()}s`
                  : choices.length === 0
                    ? `No ${typeLabel(type).toLowerCase()}s to assign`
                    : `Choose a ${typeLabel(type).toLowerCase()}`}
            </option>
            {choices.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        )}
        <button type="submit" className="gs-btn line sm" disabled={saving || !resourceId.trim()}>
          {saving ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
          Assign resource
        </button>
      </form>
      {current?.error ? (
        <button type="button" className="gs-btn text sm" onClick={() => void current.mutate()}>
          Try loading {typeLabel(type).toLowerCase()}s again
        </button>
      ) : null}
    </div>
  )
}
