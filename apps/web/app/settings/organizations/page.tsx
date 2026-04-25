"use client"

import { useState } from "react"
import Link from "next/link"
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
import { Icon } from "@/lib/icons"

// TODO: Replace with backend endpoint
const organizations = [
  {
    id: "acme-corp",
    name: "Acme Corp",
    slug: "acme-corp",
    logo: null,
    role: "Owner",
    plan: "Business",
    members: 12,
    agents: 8,
    workflows: 47,
    createdAt: "Jan 2024",
    current: true,
  },
  {
    id: "initech",
    name: "Initech",
    slug: "initech",
    logo: null,
    role: "Admin",
    plan: "Team",
    members: 5,
    agents: 3,
    workflows: 12,
    createdAt: "Mar 2024",
    current: false,
  },
  {
    id: "personal",
    name: "Personal Workspace",
    slug: "john-doe",
    logo: null,
    role: "Owner",
    plan: "Free",
    members: 1,
    agents: 1,
    workflows: 3,
    createdAt: "Dec 2023",
    current: false,
  },
]

export default function ManageOrganizationsPage() {
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [newOrgName, setNewOrgName] = useState("")
  const [newOrgSlug, setNewOrgSlug] = useState("")

  const handleNameChange = (name: string) => {
    setNewOrgName(name)
    setNewOrgSlug(name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
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
                  <Button onClick={() => setShowCreateDialog(false)}>
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
        <div className="space-y-4">
          {organizations.map((org, index) => (
            <Card 
              key={org.id} 
              className={`relative overflow-hidden transition-all hover:shadow-md ${
                org.current ? "ring-2 ring-primary/20 bg-primary/[0.02]" : ""
              }`}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {org.current && (
                <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-primary via-primary to-transparent" />
              )}
              
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    {/* Org Avatar */}
                    <div className="relative">
                      <div className={`h-14 w-14 rounded-xl flex items-center justify-center text-lg font-semibold ${
                        org.current 
                          ? "bg-primary/10 text-primary" 
                          : "bg-secondary text-muted-foreground"
                      }`}>
                        {org.name.charAt(0)}
                      </div>
                      {org.current && (
                        <div className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-emerald-500 flex items-center justify-center ring-2 ring-background">
                          <Icon name="check" size="xs" className="text-white" />
                        </div>
                      )}
                    </div>
                    
                    {/* Org Info */}
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-semibold text-foreground">{org.name}</h3>
                        {org.current && (
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
                          <span>{org.members} members</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                          <Icon name="agents" size="sm" />
                          <span>{org.agents} agents</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                          <Icon name="automations" size="sm" />
                          <span>{org.workflows} workflows</span>
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
                        {org.plan}
                      </Badge>
                      <p className="text-xs text-muted-foreground">{org.role}</p>
                    </div>
                    
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <Icon name="more" size="sm" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        {!org.current && (
                          <DropdownMenuItem className="gap-2 cursor-pointer">
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
                        <DropdownMenuItem className="gap-2 cursor-pointer">
                          <Icon name="users" size="sm" />
                          Manage members
                        </DropdownMenuItem>
                        <DropdownMenuItem className="gap-2 cursor-pointer">
                          <Icon name="billing" size="sm" />
                          Billing & plan
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        {org.role === "Owner" && (
                          <>
                            <DropdownMenuItem className="gap-2 cursor-pointer">
                              <Icon name="share" size="sm" />
                              Transfer ownership
                            </DropdownMenuItem>
                            <DropdownMenuItem className="gap-2 cursor-pointer text-destructive focus:text-destructive">
                              <Icon name="trash" size="sm" />
                              Delete organization
                            </DropdownMenuItem>
                          </>
                        )}
                        {org.role !== "Owner" && (
                          <DropdownMenuItem className="gap-2 cursor-pointer text-destructive focus:text-destructive">
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
    </div>
  )
}
