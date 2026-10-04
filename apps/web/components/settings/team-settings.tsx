"use client"

import { useState } from "react"
import { Loader2, Users } from "lucide-react"
import { toast } from "sonner"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { settingsApi } from "@/lib/api"
import type { User } from "@/types/api"

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
  const [inviteDialog, setInviteDialog] = useState(false)
  const [editDialog, setEditDialog] = useState<User | null>(null)
  const [editRole, setEditRole] = useState("member")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [sendInviteEmail, setSendInviteEmail] = useState(true)
  const [isInviting, setIsInviting] = useState(false)
  const [isRemoving, setIsRemoving] = useState(false)
  const [isSavingRole, setIsSavingRole] = useState(false)

  const handleInvite = async () => {
    if (!isAdmin) return
    setIsInviting(true)
    try {
      await settingsApi.inviteMember(inviteEmail, inviteRole, sendInviteEmail)
      toast.success(sendInviteEmail ? `Invite email sent to ${inviteEmail}` : `${inviteEmail} added without sending invite email`)
      setInviteEmail("")
      setInviteDialog(false)
      await onUpdate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send invitation")
    } finally {
      setIsInviting(false)
    }
  }

  const handleRemoveMember = async (member: User) => {
    if (!isAdmin || !member.id) return
    if (!confirm(`Remove ${member.full_name ?? member.email} from the organization?`)) return
    setIsRemoving(true)
    try {
      await settingsApi.removeMember(member.id)
      toast.success(`${member.full_name ?? member.email} removed`)
      setEditDialog(null)
      await onUpdate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove member")
    } finally {
      setIsRemoving(false)
    }
  }

  const handleSaveRole = async () => {
    if (!isAdmin || !editDialog) return
    setIsSavingRole(true)
    try {
      await settingsApi.updateMember({ id: editDialog.id, email: editDialog.email, role: editRole })
      toast.success("Member role updated")
      setEditDialog(null)
      await onUpdate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update member role")
    } finally {
      setIsSavingRole(false)
    }
  }

  if (isLoading) return <p role="status" className="py-6 text-sm text-muted-foreground">Loading team members…</p>
  if (error) {
    return (
      <div role="alert" className="space-y-3 py-4">
        <p className="text-sm">Could not load team members.</p>
        <Button variant="outline" className="min-h-11" onClick={onRetry}>Retry team</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6" aria-label="Team members">
      {!isAdmin ? <p className="text-sm text-muted-foreground">Admin or owner permission is required to invite, edit, or remove members.</p> : null}
      <AdaptiveDataView
        mobileFallback={
          <ul className="space-y-2">
            {members.map((member) => (
              <li key={member.id ?? member.email}>
                <button type="button" disabled={!isAdmin} onClick={() => { setEditRole(member.role ?? "member"); setEditDialog(member) }} className="flex min-h-11 w-full items-start gap-3 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3 text-left">
                  <UserAccountAvatar name={member.full_name} email={member.email} avatarUrl={member.avatar_url} size="sm" />
                  <span className="min-w-0">
                    <span className="block break-words text-sm font-medium">{member.full_name ?? member.email}</span>
                    <span className="block break-words text-xs text-muted-foreground">{member.email}</span>
                    <span className="mt-1 block text-xs capitalize text-muted-foreground">{member.role ?? "member"}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        }
      >
        <table className="w-full min-w-[480px]">
          <thead>
            <tr className="border-b border-divide bg-secondary/30">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Member</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Role</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const titleLine = [member.job_title, member.department].filter(Boolean).join(" · ")
              return (
                <tr key={member.id ?? member.email} className="border-b border-divide last:border-0">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <UserAccountAvatar name={member.full_name} email={member.email} avatarUrl={member.avatar_url} size="sm" />
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium">{member.full_name ?? member.email}</p>
                        <p className="break-words text-xs text-muted-foreground">{member.email}</p>
                        {titleLine ? <p className="text-[11px] text-muted-foreground/80">{titleLine}</p> : null}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 capitalize text-xs">{member.role ?? "member"}</td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="ghost" className="min-h-11 text-xs" disabled={!isAdmin} onClick={() => { setEditRole(member.role ?? "member"); setEditDialog(member) }}>Edit</Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </AdaptiveDataView>
      <Button className="min-h-11 gap-2" onClick={() => setInviteDialog(true)} disabled={!isAdmin}>
        <Users className="h-3.5 w-3.5" />
        Invite member
      </Button>

      <Dialog open={inviteDialog} onOpenChange={setInviteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite team member</DialogTitle>
            <DialogDescription>Send an invitation to join your organization.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label htmlFor="invite-email" className="text-xs font-medium text-muted-foreground">Email address</label>
              <Input id="invite-email" type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} className="min-h-11" />
            </div>
            <div className="space-y-2">
              <label htmlFor="invite-role" className="text-xs font-medium text-muted-foreground">Role</label>
              <select id="invite-role" value={inviteRole} onChange={(event) => setInviteRole(event.target.value)} className="h-11 w-full rounded-md border border-border bg-secondary px-3 text-sm">
                <option value="member">Member</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer (Lite)</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input type="checkbox" className="rounded border-border" checked={sendInviteEmail} onChange={(event) => setSendInviteEmail(event.target.checked)} />
              Send Gravitre invite email via Supabase
            </label>
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button variant="outline" className="min-h-11" onClick={() => setInviteDialog(false)}>Cancel</Button>
            <Button className="min-h-11" onClick={() => void handleInvite()} disabled={isInviting || !inviteEmail}>
              {isInviting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send invite"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(editDialog)} onOpenChange={() => setEditDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit team member</DialogTitle>
            <DialogDescription>Update role or remove {editDialog?.full_name ?? editDialog?.email ?? "this member"}.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <select value={editRole} onChange={(event) => setEditRole(event.target.value)} className="h-11 w-full rounded-md border border-border bg-secondary px-3 text-sm" disabled={!isAdmin || isSavingRole}>
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer (Lite)</option>
            </select>
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button variant="destructive" className="min-h-11" disabled={!isAdmin || !editDialog?.id || isSavingRole || isRemoving} onClick={() => editDialog && void handleRemoveMember(editDialog)}>
              {isRemoving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Remove from team"}
            </Button>
            <Button variant="outline" className="min-h-11" onClick={() => setEditDialog(null)}>Cancel</Button>
            <Button className="min-h-11" onClick={() => void handleSaveRole()} disabled={!isAdmin || isSavingRole}>
              {isSavingRole ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
