"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Armchair, Loader2, MailPlus, Search, Send, UserCheck, Users, X } from "lucide-react"
import { toast } from "sonner"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import {
  SetArt,
  SetError,
  SetHeader,
  SetNote,
  SetPill,
  SetSkeleton,
  SetStat,
  SetTabs,
  formatAgo,
} from "@/components/settings/settings-kit"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { organizationsApi, settingsApi } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { ROLE_PERMISSIONS_KEY, type RolePermissionsResponse } from "@/lib/settings-api/roles"
import {
  assignableRoles,
  buildTeamRows,
  filterTeamRows,
  INVITES_KEY,
  LITE_SEATS_KEY,
  roleTitle,
  teamApi,
  teamCounts,
  type InvitesResponse,
  type TeamApiMember,
  type TeamRow,
  type TeamTab,
} from "@/lib/settings-api/team"
import type { LiteSeatsResponse, User } from "@/types/api"
import "./team.css"

export function TeamSettings({
  members,
  isLoading,
  error,
  onRetry,
  onUpdate,
  isAdmin,
}: {
  members: User[]
  isLoading?: boolean
  error?: Error
  onRetry?: () => void
  onUpdate: () => Promise<void>
  isAdmin: boolean
}) {
  const invites = useSWR<InvitesResponse>(INVITES_KEY, apiFetcher, { revalidateOnFocus: false })
  const liteSeats = useSWR<LiteSeatsResponse>(LITE_SEATS_KEY, apiFetcher, { revalidateOnFocus: false })
  const rolePermissions = useSWR<RolePermissionsResponse>(ROLE_PERMISSIONS_KEY, apiFetcher, { revalidateOnFocus: false })
  const roleNames = rolePermissions.data?.role_names ?? null
  const roleOptions = useMemo(
    () => assignableRoles(rolePermissions.data?.custom_roles, rolePermissions.data?.role_names),
    [rolePermissions.data],
  )
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [sendInviteEmail, setSendInviteEmail] = useState(true)
  const [isInviting, setIsInviting] = useState(false)
  const [tab, setTab] = useState<TeamTab>("all")
  const [query, setQuery] = useState("")
  const [editRow, setEditRow] = useState<TeamRow | null>(null)
  const [editRole, setEditRole] = useState("member")
  const [isSavingRole, setIsSavingRole] = useState(false)
  const [isRemoving, setIsRemoving] = useState(false)
  const [revokeRow, setRevokeRow] = useState<TeamRow | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)

  const teamMembers = members as TeamApiMember[]
  const rows = useMemo(() => buildTeamRows(teamMembers, invites.data?.invites), [teamMembers, invites.data])
  const counts = teamCounts(rows)
  const visible = filterTeamRows(rows, tab, query)
  const orgId = teamMembers.find((member) => member.orgId)?.orgId ?? null

  const refresh = async () => {
    await Promise.all([onUpdate(), invites.mutate()])
  }

  const handleInvite = async () => {
    if (!isAdmin) return
    const email = inviteEmail.trim()
    if (!email) return
    setIsInviting(true)
    try {
      await settingsApi.inviteMember(email, inviteRole, sendInviteEmail)
      toast.success(sendInviteEmail ? `Invite email sent to ${email}` : `${email} added without sending invite email`)
      setInviteEmail("")
      setInviteOpen(false)
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send invitation")
    } finally {
      setIsInviting(false)
    }
  }

  const openEdit = (row: TeamRow) => {
    setEditRole(row.role === "owner" ? "admin" : row.role)
    setEditRow(row)
  }

  // Role changes and removals go to the org membership endpoints, keyed by the
  // auth user id; they check admin and owner rules and write the audit trail.
  const handleSaveRole = async () => {
    if (!isAdmin || !editRow) return
    setIsSavingRole(true)
    try {
      if (orgId && editRow.userId) await organizationsApi.updateMemberRole(orgId, editRow.userId, editRole)
      else await settingsApi.updateMember({ id: editRow.id ?? undefined, email: editRow.email ?? undefined, role: editRole })
      toast.success("Member role updated")
      setEditRow(null)
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update member role")
    } finally {
      setIsSavingRole(false)
    }
  }

  const removeRow = async (row: TeamRow) => {
    if (orgId && row.userId) await organizationsApi.removeMember(orgId, row.userId)
    else if (row.id) await settingsApi.removeMember(row.id)
    else throw new Error("This member can't be removed from here")
  }

  const handleRemoveMember = async (row: TeamRow) => {
    if (!isAdmin) return
    if (!confirm(`Remove ${row.name} from the organization?`)) return
    setIsRemoving(true)
    try {
      await removeRow(row)
      toast.success(`${row.name} removed`)
      setEditRow(null)
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove member")
    } finally {
      setIsRemoving(false)
    }
  }

  const handleResend = async (row: TeamRow) => {
    if (!isAdmin || !row.userId) return
    setBusyKey(row.key)
    try {
      const result = await teamApi.resendInvite(row.userId)
      toast.success(`Invite sent again to ${result.email ?? row.email ?? row.name}`)
      await invites.mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not resend the invite")
    } finally {
      setBusyKey(null)
    }
  }

  const handleRevoke = async () => {
    if (!isAdmin || !revokeRow) return
    setBusyKey(revokeRow.key)
    try {
      await removeRow(revokeRow)
      toast.success(`Invite for ${revokeRow.email ?? revokeRow.name} revoked`)
      setRevokeRow(null)
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not revoke the invite")
    } finally {
      setBusyKey(null)
    }
  }

  const header = (
    <SetHeader
      crumb="Settings / People and plan"
      title="Team members"
      description="Invite people, set their role and see who has access."
      actions={
        <button
          type="button"
          className="gs-btn dark"
          onClick={() => setInviteOpen(true)}
          disabled={!isAdmin}
          title={isAdmin ? undefined : "Only admins and owners can invite"}
        >
          <MailPlus size={16} aria-hidden />
          Invite member
        </button>
      }
    />
  )

  if (isLoading) {
    return (
      <>
        {header}
        <section className="gs-card">
          <p role="status" className="sr-only">
            Loading team members…
          </p>
          <SetSkeleton rows={4} label="Loading team members" />
        </section>
      </>
    )
  }
  if (error) {
    return (
      <>
        {header}
        <section className="gs-card">
          <SetError message="Could not load team members." onRetry={onRetry} />
        </section>
      </>
    )
  }

  const liteAllocated = liteSeats.data?.summary?.allocated
  const invitesUnavailable = Boolean(invites.error) && !invites.data

  return (
    <div className="flex flex-col gap-5" aria-label="Team members">
      {header}

      <div className="gs-stats">
        <SetStat icon={Users} tone="green" label="Members" value={counts.fullSeats} hint="Full seats" />
        <SetStat
          icon={UserCheck}
          tone="warn"
          label="Pending invites"
          value={invitesUnavailable ? "n/a" : invites.isLoading && !invites.data ? "…" : counts.pending}
          hint={invitesUnavailable ? "Could not check invites" : "Awaiting sign up"}
        />
        <SetStat
          icon={Armchair}
          tone="mute"
          label="Lite seats"
          value={liteSeats.error && !liteSeats.data ? "n/a" : typeof liteAllocated === "number" ? liteAllocated : liteSeats.isLoading ? "…" : null}
          hint="Allocated by department"
        />
      </div>

      {!isAdmin ? (
        <SetNote>Admin or owner permission is required to invite, edit, or remove members.</SetNote>
      ) : null}

      {inviteOpen && isAdmin ? (
        <section className="gs-card team-invite" aria-label="Invite a member">
          <form
            onSubmit={(event) => {
              event.preventDefault()
              void handleInvite()
            }}
          >
            <div className="team-invite-row">
              <label className="gs-field">
                Email address
                <input
                  id="invite-email"
                  type="email"
                  placeholder="name@company.com"
                  value={inviteEmail}
                  autoFocus
                  required
                  onChange={(event) => setInviteEmail(event.target.value)}
                />
              </label>
              <label className="gs-field">
                Role
                <select id="invite-role" value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>
                  {roleOptions.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.label}
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" className="gs-btn green" disabled={isInviting || !inviteEmail.trim()}>
                {isInviting ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Send size={16} aria-hidden />}
                Send invite
              </button>
              <button type="button" className="gs-btn text" onClick={() => setInviteOpen(false)}>
                Cancel
              </button>
            </div>
            <label className="team-invite-opts">
              <input type="checkbox" checked={sendInviteEmail} onChange={(event) => setSendInviteEmail(event.target.checked)} />
              Send the Gravitre invite email. Turn off to add someone who already has an account.
            </label>
          </form>
        </section>
      ) : null}

      <section className="gs-card clip">
        <div className="gs-toolbar">
          <label className="gs-input">
            <Search size={16} aria-hidden />
            <input
              type="search"
              aria-label="Search members"
              placeholder="Search by name or email"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <SetTabs<TeamTab>
            mode="tabs"
            label="Filter"
            value={tab}
            onChange={setTab}
            options={[
              { id: "all", label: "All", count: counts.all },
              { id: "active", label: "Active", count: counts.active },
              { id: "pending", label: "Pending", count: counts.pending },
            ]}
          />
        </div>
        {invitesUnavailable ? (
          <div style={{ padding: "12px 20px 0" }}>
            <SetNote tone="amber">
              Could not check which invites are still pending, so everyone shows as active.{" "}
              <button type="button" className="gs-link" style={{ background: "none", border: 0, padding: 0, cursor: "pointer" }} onClick={() => void invites.mutate()}>
                Try again
              </button>
            </SetNote>
          </div>
        ) : null}
        <div className="gs-tbl stack team-tbl" role="table" aria-label="Team members">
          <div className="gs-tr head" role="row">
            <div className="gs-th" role="columnheader">Member</div>
            <div className="gs-th" role="columnheader">Role</div>
            <div className="gs-th" role="columnheader">Status</div>
            <div className="gs-th" role="columnheader" style={{ textAlign: "right" }}>
              Actions
            </div>
          </div>
          {visible.length === 0 ? (
            <div className="gs-empty" role="row">
              <b role="cell">
                {rows.length === 0
                  ? "No team members yet"
                  : query.trim()
                    ? "No one matches that search"
                    : tab === "pending"
                      ? "No pending invites"
                      : "No one here yet"}
              </b>
            </div>
          ) : (
            visible.map((row) => (
              <div key={row.key} className="gs-row" role="row">
                <div className="gs-td" role="cell">
                  <div className="team-member">
                    <UserAccountAvatar name={row.name} email={row.email} avatarUrl={row.avatarUrl} size="sm" />
                    <div>
                      <div className="t">{row.name}</div>
                      <div className="s">{[row.email, row.subtitle].filter(Boolean).join(" · ")}</div>
                    </div>
                  </div>
                </div>
                <div className="gs-td" role="cell">
                  <span className="gs-chip">{roleTitle(row.role, roleNames)}</span>
                </div>
                <div className="gs-td" role="cell">
                  {row.status === "active" ? (
                    <SetPill tone="green" dot>
                      Active
                    </SetPill>
                  ) : (
                    <span title={row.invitedAt ? `Invited ${formatAgo(row.invitedAt) ?? ""}` : undefined}>
                      <SetPill tone="amber" dot>
                        Pending
                      </SetPill>
                    </span>
                  )}
                </div>
                <div className="gs-td team-actions-cell" role="cell">
                  <div className="team-actions">
                    {row.status === "active" ? (
                      <button
                        type="button"
                        className="gs-btn text sm"
                        disabled={!isAdmin}
                        onClick={() => openEdit(row)}
                        aria-label={`Edit ${row.name}`}
                      >
                        Edit
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="gs-btn text sm"
                          disabled={!isAdmin || busyKey === row.key}
                          onClick={() => void handleResend(row)}
                          aria-label={`Resend invite to ${row.email ?? row.name}`}
                        >
                          {busyKey === row.key ? <Loader2 size={14} className="animate-spin" aria-hidden /> : null}
                          Resend
                        </button>
                        <button
                          type="button"
                          className="gs-iconbtn danger"
                          disabled={!isAdmin || busyKey === row.key}
                          onClick={() => setRevokeRow(row)}
                          aria-label={`Revoke invite for ${row.email ?? row.name}`}
                          title="Revoke invite"
                        >
                          <X size={15} aria-hidden />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="gs-card team-promo">
        <SetArt name="settings-team" ratio="320 / 180" />
        <div>
          <div className="gs-eyebrow">Better together</div>
          <h3>Bring in the people who approve the work</h3>
          <p>Approvers do not need a full seat. Give them a Lite seat and they can review and approve from Slack or email.</p>
          <Link href="/settings?section=lite-seats" className="gs-btn line sm" style={{ marginTop: 12 }}>
            Set up Lite seats
          </Link>
        </div>
      </section>

      <Dialog open={Boolean(editRow)} onOpenChange={(open) => !open && setEditRow(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit team member</DialogTitle>
            <DialogDescription>Update role or remove {editRow?.name ?? "this member"}.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <label htmlFor="edit-role" className="text-xs font-medium text-muted-foreground">
              Role
            </label>
            <select
              id="edit-role"
              value={editRole}
              onChange={(event) => setEditRole(event.target.value)}
              className="h-11 w-full rounded-md border border-border bg-secondary px-3 text-sm"
              disabled={!isAdmin || isSavingRole}
            >
              {roleOptions.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.id === "viewer" ? "Viewer (Lite)" : role.label}
                </option>
              ))}
            </select>
            {editRow?.role === "owner" ? (
              <p className="text-xs text-muted-foreground">
                This person is an owner. Only an owner can change an owner&apos;s role, and the workspace always keeps one owner.
              </p>
            ) : null}
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button
              variant="destructive"
              className="min-h-11"
              disabled={!isAdmin || !editRow || isSavingRole || isRemoving}
              onClick={() => editRow && void handleRemoveMember(editRow)}
            >
              {isRemoving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Remove from team"}
            </Button>
            <Button variant="outline" className="min-h-11" onClick={() => setEditRow(null)}>
              Cancel
            </Button>
            <Button className="min-h-11" onClick={() => void handleSaveRole()} disabled={!isAdmin || isSavingRole}>
              {isSavingRole ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(revokeRow)} onOpenChange={(open) => !open && setRevokeRow(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke this invite?</AlertDialogTitle>
            <AlertDialogDescription>
              {revokeRow?.email ?? revokeRow?.name} loses access to this workspace. You can invite them again later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={Boolean(busyKey)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={Boolean(busyKey)}
              onClick={(event) => {
                event.preventDefault()
                void handleRevoke()
              }}
            >
              Revoke invite
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
