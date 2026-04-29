"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth-context"
import { organizationsApi } from "@/lib/api"
import { Icon } from "@/lib/icons"
import { toast } from "sonner"
import type { Organization, User } from "@/types/api"

type OrganizationWithRole = Organization & { role?: string }
type Member = User & { role: string }

export default function ManageOrganizationsPage() {
  const { user } = useAuth()
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showMembersDialog, setShowMembersDialog] = useState(false)
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)
  const [newOrgName, setNewOrgName] = useState("")
  const [newOrgSlug, setNewOrgSlug] = useState("")
  const [inviteEmail, setInviteEmail] = useState("")
  const [isMutating, setIsMutating] = useState(false)

  const { data, isLoading, mutate } = useSWR(
    user ? "organizations:list" : null,
    () => organizationsApi.list()
  )

  const organizations = useMemo(
    () => (data?.organizations as OrganizationWithRole[] | undefined) ?? [],
    [data]
  )

  const currentOrgId = selectedOrgId ?? organizations[0]?.id ?? null
  const selectedOrg = organizations.find((org) => org.id === currentOrgId) ?? null

  const { data: membersData, isLoading: membersLoading, mutate: mutateMembers } = useSWR(
    user && showMembersDialog && selectedOrg?.id ? `organizations:members:${selectedOrg.id}` : null,
    () => organizationsApi.listMembers(selectedOrg!.id)
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
      setSelectedOrgId(orgId)
      toast.success("Organization switched")
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
      toast.success("Organization deleted")
    } catch (error) {
      console.error("Failed to delete organization", error)
      toast.error(error instanceof Error ? error.message : "Failed to delete organization")
    } finally {
      setIsMutating(false)
    }
  }

  const handleInviteMember = async () => {
    if (!selectedOrg || !inviteEmail.trim()) {
      toast.error("Invite email is required")
      return
    }
    try {
      setIsMutating(true)
      await organizationsApi.inviteMember(selectedOrg.id, inviteEmail.trim())
      setInviteEmail("")
      await mutateMembers()
      toast.success("Invitation sent")
    } catch (error) {
      console.error("Failed to invite member", error)
      toast.error(error instanceof Error ? error.message : "Failed to invite member")
    } finally {
      setIsMutating(false)
    }
  }

  const handleUpdateMemberRole = async (member: Member, role: "admin" | "member") => {
    if (!selectedOrg) return
    try {
      setIsMutating(true)
      await organizationsApi.updateMemberRole(selectedOrg.id, member.id, role)
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
    if (!selectedOrg) return
    if (!window.confirm(`Remove ${member.email ?? member.id} from organization?`)) return
    try {
      setIsMutating(true)
      await organizationsApi.removeMember(selectedOrg.id, member.id)
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
      <div className="min-h-screen bg-background">
        <div className="max-w-5xl mx-auto px-6 py-12">
          <Card>
            <CardHeader>
              <CardTitle>Sign in required</CardTitle>
              <CardDescription>Sign in to manage organizations and members.</CardDescription>
            </CardHeader>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border">
        <div className="max-w-5xl mx-auto px-6 py-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
            <Link href="/settings" className="hover:text-foreground transition-colors">Settings</Link>
            <Icon name="chevronRight" size="xs" />
            <span className="text-foreground">Organizations</span>
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Organizations</h1>
              <p className="text-muted-foreground mt-1">
                Create and manage your organizations and workspaces
              </p>
            </div>
            
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button className="gap-2">
                  <Icon name="plus" size="sm" />
                  Create Organization
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
                    Create Organization
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        {isLoading && (
          <Card className="mb-4">
            <CardContent className="p-6 text-sm text-muted-foreground">Loading organizations...</CardContent>
          </Card>
        )}
        <div className="space-y-4">
          {organizations.map((org, index) => (
            <Card 
              key={org.id} 
              className={`relative overflow-hidden transition-all hover:shadow-md ${
                currentOrgId === org.id ? "ring-2 ring-primary/20 bg-primary/[0.02]" : ""
              }`}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {currentOrgId === org.id && (
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary via-primary to-transparent" />
              )}
              
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    {/* Org Avatar */}
                    <div className="relative">
                      <div className={`h-14 w-14 rounded-xl flex items-center justify-center text-lg font-semibold ${
                        currentOrgId === org.id
                          ? "bg-primary/10 text-primary" 
                          : "bg-secondary text-muted-foreground"
                      }`}>
                        {org.name.charAt(0)}
                      </div>
                      {currentOrgId === org.id && (
                        <div className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-emerald-500 flex items-center justify-center ring-2 ring-background">
                          <Icon name="check" size="xs" className="text-white" />
                        </div>
                      )}
                    </div>
                    
                    {/* Org Info */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-semibold text-foreground">{org.name}</h3>
                        {currentOrgId === org.id && (
                          <Badge variant="secondary" className="text-xs bg-emerald-500/10 text-emerald-600 border-0">
                            Current
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        gravitre.ai/{org.slug}
                      </p>
                      <div className="flex items-center gap-4 pt-2">
                        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                          <Icon name="users" size="sm" />
                          <span>{currentOrgId === org.id ? members.length : "-" } members</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Right Side */}
                  <div className="flex items-start gap-4">
                    <div className="text-right space-y-1">
                      <Badge
                        variant="outline" 
                        className={`${
                          org.plan === "Business" 
                            ? "bg-primary/10 text-primary border-primary/20" 
                            : org.plan === "Team"
                            ? "bg-blue-500/10 text-blue-600 border-blue-500/20"
                            : "bg-secondary text-muted-foreground"
                        }`}
                      >
                        {org.plan ?? "Free"}
                      </Badge>
                      <p className="text-xs text-muted-foreground">{org.role ?? "member"}</p>
                    </div>
                    
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <Icon name="more" size="sm" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        {currentOrgId !== org.id && (
                          <DropdownMenuItem
                            className="gap-2 cursor-pointer"
                            disabled={isMutating}
                            onClick={() => void handleSwitchOrganization(org.id)}
                          >
                            <Icon name="check" size="sm" />
                            Switch to this org
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem className="gap-2 cursor-pointer" asChild>
                          <Link href={`/settings?org=${org.id}`}>
                            <Icon name="settings" size="sm" />
                            Organization settings
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="gap-2 cursor-pointer"
                          onClick={() => {
                            setSelectedOrgId(org.id)
                            setShowMembersDialog(true)
                          }}
                        >
                          <Icon name="users" size="sm" />
                          Manage members
                        </DropdownMenuItem>
                        <DropdownMenuItem className="gap-2 cursor-pointer">
                          <Icon name="billing" size="sm" />
                          Billing & plan
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        {(org.role ?? "").toLowerCase() === "admin" && (
                          <>
                            <DropdownMenuItem className="gap-2 cursor-pointer" disabled>
                              <Icon name="share" size="sm" />
                              Transfer ownership
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="gap-2 cursor-pointer text-destructive focus:text-destructive"
                              onClick={() => void handleDeleteOrganization(org.id)}
                              disabled={isMutating}
                            >
                              <Icon name="trash" size="sm" />
                              Delete organization
                            </DropdownMenuItem>
                          </>
                        )}
                        {(org.role ?? "").toLowerCase() !== "admin" && (
                          <DropdownMenuItem className="gap-2 cursor-pointer text-destructive focus:text-destructive" disabled>
                            <Icon name="signOut" size="sm" />
                            Leave organization
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        {!isLoading && organizations.length === 0 && (
          <Card className="mt-4">
            <CardContent className="p-6 text-sm text-muted-foreground">
              You are not a member of any organizations yet.
            </CardContent>
          </Card>
        )}

        {/* Help Section */}
        <div className="mt-12 p-6 rounded-xl bg-secondary/30 border border-border">
          <div className="flex items-start gap-4">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Icon name="help" size="sm" className="text-primary" />
            </div>
            <div>
              <h3 className="font-medium text-foreground">Need help with organizations?</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Organizations help you separate different teams, clients, or projects. Each organization 
                has its own agents, workflows, and billing. You can be a member of multiple organizations 
                and switch between them anytime.
              </p>
              <div className="flex items-center gap-4 mt-4">
                <Button variant="outline" size="sm" className="gap-2" asChild>
                  <Link href="/docs/organizations">
                    <Icon name="file" size="sm" />
                    Documentation
                  </Link>
                </Button>
                <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
                  <Icon name="chat" size="sm" />
                  Contact support
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Dialog open={showMembersDialog} onOpenChange={setShowMembersDialog}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Manage Members</DialogTitle>
            <DialogDescription>
              Invite and manage members in {selectedOrg?.name ?? "organization"}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Input
                placeholder="member@company.com"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
                disabled={isMutating}
              />
              <Button onClick={() => void handleInviteMember()} disabled={isMutating || !inviteEmail.trim()}>
                Invite
              </Button>
            </div>
            <div className="space-y-2">
              {membersLoading && <p className="text-sm text-muted-foreground">Loading members...</p>}
              {!membersLoading && members.length === 0 && (
                <p className="text-sm text-muted-foreground">No members found.</p>
              )}
              {members.map((member) => (
                <div key={member.id} className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <p className="text-sm font-medium">{member.full_name || member.email || member.id}</p>
                    <p className="text-xs text-muted-foreground">{member.email ?? member.id}</p>
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
    </div>
  )
}
