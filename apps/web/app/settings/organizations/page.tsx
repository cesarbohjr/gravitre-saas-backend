"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { useAuth } from "@/lib/auth-context"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { organizationsApi } from "@/lib/api"
import { getSelectedOrgFromStorage, invalidateOrgCache, setSelectedOrgInStorage } from "@/lib/org-context"
import { Icon } from "@/lib/icons"
import { EmptyState } from "@/components/gravitre/empty-state"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { Building2 } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"
import type { Organization, User } from "@/types/api"

type OrganizationWithRole = Organization & { role?: string }
type Member = User & { role: string }

export default function ManageOrganizationsPage() {
  const { user } = useAuth()
  // Controls which tiers the settings rail exposes.
  const { isAdmin } = useOrgAdmin()
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showMembersDialog, setShowMembersDialog] = useState(false)
  // Bug fix (2026-09-11): this used to start at `null` and fall back to
  // `organizations[0]?.id`, so on every fresh page load the "Current" badge
  // and the "Switch to this org" menu item were keyed off "whichever org the
  // list API happened to return first" instead of the REAL active org. That
  // silently hid the "Switch to this org" action for organizations[0] any
  // time the real active org (localStorage `gravitre:selectedOrg`, the same
  // value the top-bar switcher and every API call's `x-org-id` header read)
  // was something else — permanently blocking switching back to it from this
  // page. Seed from the real source of truth instead.
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(
    () => getSelectedOrgFromStorage()?.id ?? null
  )
  // Separate from `selectedOrgId`: which org's members dialog is open. This
  // used to reuse `selectedOrgId` itself, which meant opening "Manage members"
  // on a non-active org would also (wrongly) relabel that org as "Current"
  // and hide its own "Switch to this org" action — the same bug class as
  // above, via a different path.
  const [membersDialogOrgId, setMembersDialogOrgId] = useState<string | null>(null)
  const [newOrgName, setNewOrgName] = useState("")
  const [newOrgSlug, setNewOrgSlug] = useState("")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [sendInviteEmail, setSendInviteEmail] = useState(true)
  const [isMutating, setIsMutating] = useState(false)
  const [inspectId, setInspectId] = useState<string | null>(null)

  const { data, isLoading, mutate } = useSWR(
    user ? "organizations:list" : null,
    () => organizationsApi.list()
  )

  const organizations = useMemo(
    () => (data?.organizations as OrganizationWithRole[] | undefined) ?? [],
    [data]
  )

  const currentOrgId = selectedOrgId ?? organizations[0]?.id ?? null

  // If the org id read from storage is no longer a valid membership (e.g. the
  // user left or was removed from it), fall back to organizations[0] rather
  // than getting stuck pointing at an org that no longer exists.
  useEffect(() => {
    if (!selectedOrgId || organizations.length === 0) return
    if (!organizations.some((org) => org.id === selectedOrgId)) {
      setSelectedOrgId(null)
    }
  }, [organizations, selectedOrgId])

  const membersDialogOrg = organizations.find((org) => org.id === membersDialogOrgId) ?? null
  const inspectOrg = organizations.find((org) => org.id === inspectId) ?? null

  const { data: membersData, isLoading: membersLoading, mutate: mutateMembers } = useSWR(
    user && showMembersDialog && membersDialogOrg?.id ? `organizations:members:${membersDialogOrg.id}` : null,
    () => organizationsApi.listMembers(membersDialogOrg!.id)
  )
  const members = (membersData?.members as Member[] | undefined) ?? []

  const handleNameChange = (name: string) => {
    setNewOrgName(name)
    setNewOrgSlug(name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
  }

  const handleCreateOrganization = async () => {
    if (!newOrgName.trim()) {
      toast.error("Organization name is required")
      return
    }
    try {
      setIsMutating(true)
      await organizationsApi.create({ name: newOrgName.trim(), slug: newOrgSlug.trim() || undefined })
      await mutate()
      setNewOrgName("")
      setNewOrgSlug("")
      setShowCreateDialog(false)
      toast.success("Organization created")
    } catch (error) {
      console.error("Failed to create organization", error)
      toast.error(error instanceof Error ? error.message : "Failed to create organization")
    } finally {
      setIsMutating(false)
    }
  }

  const handleSwitchOrganization = async (orgId: string) => {
    try {
      setIsMutating(true)
      await organizationsApi.switch(orgId)
      // Bug fix (2026-09-11): the backend switch succeeded and this toasted
      // success, but nothing ever updated the client-side org context that
      // every other page's API calls actually read (`x-org-id` comes from
      // localStorage via getSelectedOrgFromStorage — see lib/fetcher.ts),
      // so the rest of the app kept operating on the previous org. Mirror
      // the working top-bar switch pattern: persist the new org to
      // localStorage, drop the cached org id, then reload so every
      // SWR-cached, org-scoped fetch picks up the new org_id header.
      const targetOrg = organizations.find((org) => org.id === orgId)
      setSelectedOrgInStorage({ id: orgId, name: targetOrg?.name ?? "Organization" })
      invalidateOrgCache()
      setSelectedOrgId(orgId)
      toast.success("Organization switched")
      window.location.reload()
    } catch (error) {
      console.error("Failed to switch organization", error)
      toast.error(error instanceof Error ? error.message : "Failed to switch organization")
    } finally {
      setIsMutating(false)
    }
  }

  const handleDeleteOrganization = async (orgId: string) => {
    if (!window.confirm("Delete this organization? This action cannot be undone.")) return
    try {
      setIsMutating(true)
      await organizationsApi.delete(orgId)
      await mutate()
      if (selectedOrgId === orgId) setSelectedOrgId(null)
      if (membersDialogOrgId === orgId) setMembersDialogOrgId(null)
      toast.success("Organization deleted")
    } catch (error) {
      console.error("Failed to delete organization", error)
      toast.error(error instanceof Error ? error.message : "Failed to delete organization")
    } finally {
      setIsMutating(false)
    }
  }

  const handleInviteMember = async () => {
    if (!membersDialogOrg || !inviteEmail.trim()) {
      toast.error("Invite email is required")
      return
    }
    try {
      setIsMutating(true)
      await organizationsApi.inviteMember(membersDialogOrg.id, inviteEmail.trim(), inviteRole, sendInviteEmail)
      setInviteEmail("")
      await mutateMembers()
      toast.success(sendInviteEmail ? "Invitation sent" : "Member added without invite email")
    } catch (error) {
      console.error("Failed to invite member", error)
      toast.error(error instanceof Error ? error.message : "Failed to invite member")
    } finally {
      setIsMutating(false)
    }
  }

  const handleUpdateMemberRole = async (member: Member, role: "admin" | "member") => {
    if (!membersDialogOrg) return
    try {
      setIsMutating(true)
      await organizationsApi.updateMemberRole(membersDialogOrg.id, member.id, role)
      await mutateMembers()
      toast.success("Member role updated")
    } catch (error) {
      console.error("Failed to update member role", error)
      toast.error(error instanceof Error ? error.message : "Failed to update role")
    } finally {
      setIsMutating(false)
    }
  }

  const handleRemoveMember = async (member: Member) => {
    if (!membersDialogOrg) return
    if (!window.confirm(`Remove ${member.email ?? member.id} from organization?`)) return
    try {
      setIsMutating(true)
      await organizationsApi.removeMember(membersDialogOrg.id, member.id)
      await mutateMembers()
      toast.success("Member removed")
    } catch (error) {
      console.error("Failed to remove member", error)
      toast.error(error instanceof Error ? error.message : "Failed to remove member")
    } finally {
      setIsMutating(false)
    }
  }

  if (!user) {
    return (
      <AppShell title="Settings">
        <SettingsShell activeSection="organizations" isAdmin={isAdmin} hideHeader>
          <div className="px-6 py-12">
            <p className={TYPE.sectionTitle}>Sign in required</p>
            <p className={cn(TYPE.pageLead, "mt-2")}>Sign in to manage organizations and members.</p>
          </div>
        </SettingsShell>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <SettingsShell activeSection="organizations" isAdmin={isAdmin} hideHeader>
      <GravitrePageHeader
        className="!px-0 border-b-0 mb-6"
        title="Organizations"
        description="Create and manage your organizations and workspaces"
        icon={<Building2 className="h-5 w-5" aria-hidden />}
        actions={
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button className="gap-2">
                <Icon name="plus" size="sm" />
                Create organization
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create Organization</DialogTitle>
                <DialogDescription>
                  Create a new organization to collaborate with your team
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="org-name">Organization Name</Label>
                    <Input
                      id="org-name"
                      placeholder="Acme Inc"
                      value={newOrgName}
                      onChange={(e) => handleNameChange(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="org-slug">URL Slug</Label>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">gravitre.ai/</span>
                      <Input
                        id="org-slug"
                        placeholder="acme-inc"
                        value={newOrgSlug}
                        onChange={(e) => setNewOrgSlug(e.target.value)}
                        className="flex-1"
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      This will be used in URLs and cannot be changed later
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateOrganization} disabled={isMutating || !newOrgName.trim()}>
                    Create organization
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
        }
      />

      <div className="px-4 py-4 sm:px-6" data-review-surface="settings-orgs">
        {isLoading && <p className={cn(TYPE.meta, "py-4")}>Loading organizations…</p>}
        <div className="flex flex-col border-t border-divide lg:flex-row lg:border-t-0">
          <ul
            className={cn("min-w-0 flex-1 divide-y divide-divide", inspectOrg ? "hidden lg:block" : "block")}
            data-review-surface="settings-orgs-queue"
          >
            {organizations.map((org) => (
              <li key={org.id}>
                <button
                  type="button"
                  onClick={() => setInspectId(org.id)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-1 py-3 text-left",
                    inspectId === org.id
                      ? "bg-[color:var(--g-surface-active)]"
                      : "hover:bg-[color:var(--g-surface-2)]",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-foreground">{org.name}</span>
                    <span className={cn(TYPE.meta, "mt-0.5 block truncate")}>
                      {org.slug}
                      {currentOrgId === org.id ? " · current workspace" : ""}
                      {org.role ? ` · ${org.role}` : ""}
                    </span>
                  </span>
                  <Icon name="more" size="sm" className="shrink-0 text-muted-foreground" />
                </button>
              </li>
            ))}
          </ul>
          {inspectOrg ? (
            <aside
              className="min-w-0 flex-1 border-t border-divide p-4 lg:max-w-sm lg:border-l lg:border-t-0"
              data-review-surface="settings-orgs-inspect"
            >
              <Button variant="ghost" size="sm" className="mb-3 lg:hidden" onClick={() => setInspectId(null)}>
                Back to list
              </Button>
              <p className={TYPE.eyebrow}>Organization</p>
              <h2 className={cn(TYPE.sectionTitle, "mt-1")}>{inspectOrg.name}</h2>
              <p className={cn(TYPE.meta, "mt-1")}>{inspectOrg.slug}</p>
              {inspectOrg.plan ? (
                <p className={cn(TYPE.meta, "mt-2")}>Plan on record: {inspectOrg.plan}</p>
              ) : (
                <p className={cn(TYPE.meta, "mt-2")}>Plan is shown from billing when the org has one on record.</p>
              )}
              {inspectOrg.role ? <p className={cn(TYPE.meta, "mt-1")}>Your role: {inspectOrg.role}</p> : null}
              <div className="mt-4 flex flex-col gap-2">
                {currentOrgId !== inspectOrg.id ? (
                  <Button
                    data-review-cta="switch-org"
                    disabled={isMutating}
                    onClick={() => void handleSwitchOrganization(inspectOrg.id)}
                  >
                    Switch to this org
                  </Button>
                ) : (
                  <Button data-review-cta="open-org-settings" asChild>
                    <Link href={`/settings?org=${inspectOrg.id}`}>Organization settings</Link>
                  </Button>
                )}
                {currentOrgId !== inspectOrg.id ? (
                  <Button variant="ghost" asChild>
                    <Link href={`/settings?org=${inspectOrg.id}`}>Organization settings</Link>
                  </Button>
                ) : null}
                <Button
                  variant="ghost"
                  onClick={() => {
                    setMembersDialogOrgId(inspectOrg.id)
                    setShowMembersDialog(true)
                  }}
                >
                  Manage members
                </Button>
                <Button variant="ghost" asChild>
                  <Link href="/settings/billing">Billing</Link>
                </Button>
                {(inspectOrg.role ?? "").toLowerCase() === "admin" ? (
                  <Button
                    variant="ghost"
                    className="text-destructive"
                    disabled={isMutating}
                    onClick={() => void handleDeleteOrganization(inspectOrg.id)}
                  >
                    Delete organization
                  </Button>
                ) : null}
              </div>
            </aside>
          ) : null}
        </div>
        {!inspectOrg && !isLoading && organizations.length > 0 ? (
          <p className={cn(TYPE.meta, "pt-3")}>Select an organization — inspector stays closed until then.</p>
        ) : null}
        {!isLoading && organizations.length === 0 && (
          <EmptyState
            icon={Building2}
            title="No organizations yet"
            description="Organizations keep your teams, clients, and projects separate — each with its own agents, workflows, and billing. Create your first one to get started."
            action={{ label: "Create organization", onClick: () => setShowCreateDialog(true) }}
            className="mt-4"
          />
        )}
        <p className={cn(TYPE.meta, "mt-8")}>
          Each organization has its own agents, workflows, and billing. Switch workspaces from this list after you
          select one.
        </p>
        <Link href="/docs/organizations" className="mt-2 inline-block text-sm text-[color:var(--g-brand)] hover:underline">
          Documentation
        </Link>
      </div>

      <Dialog open={showMembersDialog} onOpenChange={setShowMembersDialog}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Manage Members</DialogTitle>
            <DialogDescription>
              Invite and manage members in {membersDialogOrg?.name ?? "organization"}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
              <Input
                placeholder="member@company.com"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
                disabled={isMutating}
              />
              <select
                className="h-9 rounded-md border border-border bg-secondary px-2 text-sm sm:w-[180px]"
                value={inviteRole}
                disabled={isMutating}
                onChange={(event) => setInviteRole(event.target.value)}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer (Lite)</option>
              </select>
              <Button onClick={() => void handleInviteMember()} disabled={isMutating || !inviteEmail.trim()}>
                Invite
              </Button>
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  className="rounded border-border"
                  checked={sendInviteEmail}
                  onChange={(event) => setSendInviteEmail(event.target.checked)}
                  disabled={isMutating}
                />
                Send branded Gravitre invite email via Supabase
              </label>
            </div>
            <div className="space-y-2">
              {membersLoading && <p className="text-sm text-muted-foreground">Loading members...</p>}
              {!membersLoading && members.length === 0 && (
                <p className="text-sm text-muted-foreground">No members found.</p>
              )}
              {members.map((member) => (
                <div key={member.id} className="flex items-center justify-between rounded-lg border p-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <UserAccountAvatar
                      name={member.full_name}
                      email={member.email}
                      avatarUrl={member.avatar_url}
                      size="sm"
                    />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{member.full_name || member.email || member.id}</p>
                      <p className="truncate text-xs text-muted-foreground">{member.email ?? member.id}</p>
                      {[member.job_title, member.department].filter(Boolean).length > 0 ? (
                        <p className="truncate text-[11px] text-muted-foreground/80">
                          {[member.job_title, member.department].filter(Boolean).join(" · ")}
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{member.role}</Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isMutating}
                      onClick={() =>
                        void handleUpdateMemberRole(member, member.role === "admin" ? "member" : "admin")
                      }
                    >
                      Toggle Role
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      disabled={isMutating}
                      onClick={() => void handleRemoveMember(member)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMembersDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </SettingsShell>
    </AppShell>
  )
}
