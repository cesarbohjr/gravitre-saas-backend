"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Check, LayoutGrid, List, Loader2, Plus, Search } from "lucide-react"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { MspClientRelationship } from "@/components/settings/msp-client-relationship"
import { SettingsShell } from "@/components/settings/settings-shell"
import {
  SetArt,
  SetError,
  SetPill,
  SetSkeleton,
  SetTabs,
  avatarTone,
  initialsOf,
} from "@/components/settings/settings-kit"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { organizationsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { getSelectedOrgFromStorage, invalidateOrgCache, setSelectedOrgInStorage } from "@/lib/org-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import {
  countLabel,
  createdLabel,
  filterOrgs,
  ORGS_DOCS_HREF,
  ORGS_KEY,
  planLabel,
  roleName,
  sortOrgs,
  type OrgListItem,
} from "@/lib/settings-api/orgs"
import type { User } from "@/types/api"
import "@/components/settings/orgs.css"

type Member = User & { role: string; user_id?: string }
type View = "list" | "grid"

export default function ManageOrganizationsPage() {
  const { user } = useAuth()
  // Controls which sections the settings rail exposes.
  const { showAdmin } = useOrgAdmin()
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  if (!user) {
    return (
      <AppShell title="Settings">
        <SettingsShell activeSection="organizations" isAdmin={showAdmin}>
          <section className="gs-card">
            <div className="gs-empty">
              <b>Sign in required</b>
              <p>Sign in to manage organizations and members.</p>
            </div>
          </section>
        </SettingsShell>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <SettingsShell
        activeSection="organizations"
        isAdmin={showAdmin}
        actions={
          <button type="button" className="gs-btn dark" onClick={() => setShowCreateDialog(true)}>
            <Plus size={16} aria-hidden />
            Create organization
          </button>
        }
      >
        <OrganizationsContent showCreateDialog={showCreateDialog} setShowCreateDialog={setShowCreateDialog} />
      </SettingsShell>
    </AppShell>
  )
}

function OrganizationsContent({
  showCreateDialog,
  setShowCreateDialog,
}: {
  showCreateDialog: boolean
  setShowCreateDialog: (open: boolean) => void
}) {
  // The real active org: localStorage `gravitre:selectedOrg` is what the top
  // bar switcher and every API call's `x-org-id` header read; /api/auth/me's
  // resolved org is the fallback when nothing is stored yet.
  const [storedOrgId, setStoredOrgId] = useState<string | null>(() => getSelectedOrgFromStorage()?.id ?? null)
  const [query, setQuery] = useState("")
  const [view, setView] = useState<View>("list")
  const [inspectId, setInspectId] = useState<string | null>(null)
  const [membersDialogOrgId, setMembersDialogOrgId] = useState<string | null>(null)
  const [deleteOrgId, setDeleteOrgId] = useState<string | null>(null)
  const [newOrgName, setNewOrgName] = useState("")
  const [newOrgSlug, setNewOrgSlug] = useState("")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [sendInviteEmail, setSendInviteEmail] = useState(true)
  const [isMutating, setIsMutating] = useState(false)

  const { data, error, isLoading, mutate } = useSWR(ORGS_KEY, () => organizationsApi.list())
  const { data: me } = useSWR<{ org_id?: string | null }>("/api/auth/me", apiFetcher, { revalidateOnFocus: false })
  const organizations = useMemo(() => (data?.organizations as OrgListItem[] | undefined) ?? [], [data])

  // If the stored org is no longer a membership (left or removed), stop pointing at it.
  useEffect(() => {
    if (!storedOrgId || organizations.length === 0) return
    if (!organizations.some((org) => org.id === storedOrgId)) setStoredOrgId(null)
  }, [organizations, storedOrgId])

  const currentOrgId =
    storedOrgId ??
    (me?.org_id && organizations.some((org) => org.id === me.org_id) ? me.org_id : null) ??
    organizations[0]?.id ??
    null
  const sorted = useMemo(() => sortOrgs(organizations, currentOrgId), [organizations, currentOrgId])
  const rows = useMemo(() => filterOrgs(sorted, query), [sorted, query])
  const inspectOrg = organizations.find((org) => org.id === (inspectId ?? currentOrgId)) ?? sorted[0] ?? null
  const membersDialogOrg = organizations.find((org) => org.id === membersDialogOrgId) ?? null
  const deleteOrg = organizations.find((org) => org.id === deleteOrgId) ?? null

  const { data: membersData, isLoading: membersLoading, mutate: mutateMembers } = useSWR(
    membersDialogOrg?.id ? `organizations:members:${membersDialogOrg.id}` : null,
    () => organizationsApi.listMembers(membersDialogOrg!.id),
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
      const created = await organizationsApi.create({ name: newOrgName.trim(), slug: newOrgSlug.trim() || undefined })
      await mutate()
      setNewOrgName("")
      setNewOrgSlug("")
      setShowCreateDialog(false)
      if (created?.id) setInspectId(created.id)
      toast.success("Organization created")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create organization")
    } finally {
      setIsMutating(false)
    }
  }

  const handleSwitchOrganization = async (orgId: string) => {
    try {
      setIsMutating(true)
      await organizationsApi.switch(orgId)
      // Same as the top bar switcher: persist the org every API call's x-org-id
      // header reads, drop the cached org id, then reload so every org scoped
      // fetch picks up the new org.
      const targetOrg = organizations.find((org) => org.id === orgId)
      setSelectedOrgInStorage({ id: orgId, name: targetOrg?.name ?? "Organization" })
      invalidateOrgCache()
      setStoredOrgId(orgId)
      toast.success("Organization switched")
      window.location.reload()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to switch organization")
      setIsMutating(false)
    }
  }

  const handleDeleteOrganization = async (orgId: string) => {
    try {
      setIsMutating(true)
      await organizationsApi.delete(orgId)
      await mutate()
      if (storedOrgId === orgId) setStoredOrgId(null)
      if (membersDialogOrgId === orgId) setMembersDialogOrgId(null)
      if (inspectId === orgId) setInspectId(null)
      setDeleteOrgId(null)
      toast.success("Organization deleted")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete organization")
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
      await Promise.all([mutateMembers(), mutate()])
      toast.success(sendInviteEmail ? "Invitation sent" : "Member added without invite email")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to invite member")
    } finally {
      setIsMutating(false)
    }
  }

  // The backend keys member changes by the auth user id (user_id), not public.users.id.
  const memberKey = (member: Member) => member.user_id ?? member.id

  const handleUpdateMemberRole = async (member: Member, role: "admin" | "member") => {
    if (!membersDialogOrg) return
    try {
      setIsMutating(true)
      await organizationsApi.updateMemberRole(membersDialogOrg.id, memberKey(member), role)
      await mutateMembers()
      toast.success("Member role updated")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update role")
    } finally {
      setIsMutating(false)
    }
  }

  const handleRemoveMember = async (member: Member) => {
    if (!membersDialogOrg) return
    if (!window.confirm(`Remove ${member.email ?? member.id} from organization?`)) return
    try {
      setIsMutating(true)
      await organizationsApi.removeMember(membersDialogOrg.id, memberKey(member))
      await Promise.all([mutateMembers(), mutate()])
      toast.success("Member removed")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove member")
    } finally {
      setIsMutating(false)
    }
  }

  const inspectRole = String(inspectOrg?.role ?? "").toLowerCase()
  const inspectIsCurrent = Boolean(inspectOrg && inspectOrg.id === currentOrgId)

  return (
    <>
      {/* A partner's request to manage the current workspace, or who manages it. */}
      <MspClientRelationship />

      <section className="gs-card clip" data-review-surface="settings-orgs">
        <div className="gs-toolbar">
          <label className="gs-input">
            <Search size={16} aria-hidden />
            <input
              type="search"
              aria-label="Search organizations"
              placeholder="Search organizations"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <SetTabs<View>
            label="View"
            value={view}
            onChange={setView}
            options={[
              { id: "list", label: "List", icon: List },
              { id: "grid", label: "Grid", icon: LayoutGrid },
            ]}
          />
        </div>

        {error && !data ? (
          <SetError message="Could not load your organizations." onRetry={() => void mutate()} />
        ) : isLoading && !data ? (
          <SetSkeleton rows={4} label="Loading organizations" />
        ) : organizations.length === 0 ? (
          <div className="gs-empty">
            <b>No organizations yet</b>
            <p>
              Organizations keep your teams, clients and projects separate, each with its own agents, workflows and
              billing. Create your first one to get started.
            </p>
            <button type="button" className="gs-btn dark sm" onClick={() => setShowCreateDialog(true)}>
              <Plus size={15} aria-hidden />
              Create organization
            </button>
          </div>
        ) : (
          <div className="gs-split">
            <div className="gs-split-main">
              <div data-review-surface="settings-orgs-queue" role="group" aria-label="Organizations">
                {rows.length === 0 ? (
                  <p role="status" style={{ padding: "32px 18px", textAlign: "center", fontSize: 14, color: "var(--gs-muted)", margin: 0 }}>
                    No organization matches that search.
                  </p>
                ) : view === "list" ? (
                  rows.map((org) => (
                    <button
                      key={org.id}
                      type="button"
                      className="gs-orow"
                      aria-pressed={inspectOrg?.id === org.id}
                      onClick={() => setInspectId(org.id)}
                    >
                      <OrgAvatar org={org} />
                      <span className="orgs-row-body">
                        <span className="orgs-name">
                          <span>{org.name}</span>
                          {org.id === currentOrgId ? <SetPill tone="green">Current</SetPill> : null}
                        </span>
                        <span className="orgs-slug gs-mono">{org.slug}</span>
                      </span>
                      <span className="gs-chip">{roleName(org.role)}</span>
                    </button>
                  ))
                ) : (
                  <div className="gs-cards">
                    {rows.map((org) => (
                      <button
                        key={org.id}
                        type="button"
                        className="gs-wcard"
                        aria-pressed={inspectOrg?.id === org.id}
                        onClick={() => setInspectId(org.id)}
                      >
                        <span className="orgs-card-top">
                          <OrgAvatar org={org} />
                          {org.id === currentOrgId ? <SetPill tone="green">Current</SetPill> : null}
                        </span>
                        <span className="orgs-card-name">{org.name}</span>
                        <span className="orgs-card-counts">
                          <span>{countLabel(org.agent_count)} agents</span>
                          <span>{countLabel(org.workflow_count)} workflows</span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="orgs-list-foot" role="status" aria-live="polite">
                Showing {rows.length} of {organizations.length} organization{organizations.length === 1 ? "" : "s"}
              </div>
            </div>

            {inspectOrg ? (
              <aside className="gs-split-side" aria-label="Organization details" data-review-surface="settings-orgs-inspect">
                <SetArt name="settings-organizations" ratio="320 / 170" />
                <div className="orgs-panel-head">
                  <OrgAvatar org={inspectOrg} />
                  <div style={{ minWidth: 0 }}>
                    <h3>{inspectOrg.name}</h3>
                    <div className="orgs-slug gs-mono">{inspectOrg.slug}</div>
                  </div>
                </div>
                <div className="orgs-tiles">
                  <CountTile value={inspectOrg.member_count} label="Members" />
                  <CountTile value={inspectOrg.agent_count} label="Agents" />
                  <CountTile value={inspectOrg.workflow_count} label="Workflows" />
                </div>
                <div className="gs-kv">
                  <div>
                    <span>Your role</span>
                    <strong>{roleName(inspectOrg.role)}</strong>
                  </div>
                  <div>
                    <span>Plan</span>
                    <strong>{planLabel(inspectOrg) ?? "No plan on record"}</strong>
                  </div>
                  <div>
                    <span>Created</span>
                    <strong>{createdLabel(inspectOrg.created_at) ?? "Not recorded"}</strong>
                  </div>
                  <div>
                    <span title="Share it with your IT partner so they can ask to manage this workspace">Workspace ID</span>
                    <strong className="gs-mono" style={{ fontSize: 12, wordBreak: "break-all" }}>
                      {inspectOrg.id}
                    </strong>
                  </div>
                </div>
                <div className="orgs-actions">
                  {inspectIsCurrent ? (
                    <SetPill tone="green">
                      <Check size={13} aria-hidden />
                      You are here
                    </SetPill>
                  ) : (
                    <button
                      type="button"
                      className="gs-btn green sm"
                      data-review-cta="switch-org"
                      disabled={isMutating}
                      onClick={() => void handleSwitchOrganization(inspectOrg.id)}
                    >
                      {isMutating ? <Loader2 size={14} className="animate-spin" aria-hidden /> : null}
                      Switch to this workspace
                    </button>
                  )}
                  {inspectIsCurrent ? (
                    <Link href="/settings?section=organization" className="gs-btn line sm" data-review-cta="open-org-settings">
                      Manage
                    </Link>
                  ) : null}
                </div>
                {!inspectIsCurrent ? (
                  <p className="gs-sub" style={{ margin: 0 }}>
                    Switch to this workspace to manage its general settings and billing.
                  </p>
                ) : null}
                <div className="orgs-more">
                  <button type="button" className="gs-btn text sm" onClick={() => setMembersDialogOrgId(inspectOrg.id)}>
                    Manage members
                  </button>
                  {inspectIsCurrent ? (
                    <Link href="/settings/billing" className="gs-btn text sm">
                      Billing
                    </Link>
                  ) : null}
                  {inspectRole === "owner" ? (
                    <button
                      type="button"
                      className="gs-btn text sm"
                      style={{ color: "var(--gs-red-ink)" }}
                      disabled={isMutating}
                      onClick={() => setDeleteOrgId(inspectOrg.id)}
                    >
                      Delete organization
                    </button>
                  ) : null}
                </div>
              </aside>
            ) : null}
          </div>
        )}
      </section>

      <p className="orgs-docs">
        New to organizations?{" "}
        <Link href={ORGS_DOCS_HREF} className="gs-link">
          Read the documentation
        </Link>
      </p>

      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create organization</DialogTitle>
            <DialogDescription>Create a new organization to collaborate with your team</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">Organization name</Label>
              <Input id="org-name" placeholder="Acme Inc" value={newOrgName} onChange={(e) => handleNameChange(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="org-slug">URL slug</Label>
              <Input id="org-slug" placeholder="acme-inc" value={newOrgSlug} onChange={(e) => setNewOrgSlug(e.target.value)} />
              <p className="text-xs text-muted-foreground">Used in URLs and the API org context.</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleCreateOrganization()} disabled={isMutating || !newOrgName.trim()}>
              Create organization
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleteOrg)} onOpenChange={(open) => !open && setDeleteOrgId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleteOrg?.name ?? "this organization"}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its agents, workflows, members and billing go with it. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMutating}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isMutating}
              onClick={(event) => {
                event.preventDefault()
                if (deleteOrg) void handleDeleteOrganization(deleteOrg.id)
              }}
            >
              Delete organization
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={Boolean(membersDialogOrg)} onOpenChange={(open) => !open && setMembersDialogOrgId(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Manage members</DialogTitle>
            <DialogDescription>Invite and manage members in {membersDialogOrg?.name ?? "organization"}.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  aria-label="Invite email"
                  placeholder="member@company.com"
                  value={inviteEmail}
                  onChange={(event) => setInviteEmail(event.target.value)}
                  disabled={isMutating}
                  className="min-w-0 flex-1"
                />
                <select
                  aria-label="Invite role"
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
            <div className="max-h-[50vh] space-y-2 overflow-y-auto">
              {membersLoading ? <p className="text-sm text-muted-foreground">Loading members…</p> : null}
              {!membersLoading && members.length === 0 ? <p className="text-sm text-muted-foreground">No members found.</p> : null}
              {members.map((member) => (
                <div key={memberKey(member)} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <UserAccountAvatar name={member.full_name} email={member.email} avatarUrl={member.avatar_url} size="sm" />
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
                      disabled={isMutating || member.role === "owner"}
                      onClick={() => void handleUpdateMemberRole(member, member.role === "admin" ? "member" : "admin")}
                    >
                      {member.role === "admin" ? "Make member" : "Make admin"}
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
            <Button variant="outline" onClick={() => setMembersDialogOrgId(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function OrgAvatar({ org }: { org: OrgListItem }) {
  return (
    <span className={`gs-avatar ${avatarTone(org.id)}`} aria-hidden>
      {initialsOf(org.name, "O")}
    </span>
  )
}

function CountTile({ value, label }: { value: number | null | undefined; label: string }) {
  return (
    <div className="gs-tile white" title={typeof value === "number" ? undefined : "Could not be counted right now"}>
      <b>{countLabel(value)}</b>
      <span>{label}</span>
    </div>
  )
}
