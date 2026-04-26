"use client"

import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import Image from "next/image"
import { AppShell } from "@/components/gravitre/app-shell"
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
import { 
  Shield,
  Key,
  Bell,
  Users,
  Building2,
  Globe,
  Lock,
  Mail,
  Webhook,
  Save,
  Eye,
  EyeOff,
  Copy,
  Check,
  RefreshCw,
  Upload,
  Loader2,
  X,
  Brain,
  Sparkles,
  Info,
  AlertCircle
} from "lucide-react"
import { ModelSelector } from "@/components/gravitre/model-selector"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { EmptyState } from "@/components/gravitre/empty-state"
import { toast } from "sonner"

interface SettingSection {
  id: string
  title: string
  description: string
  icon: typeof Shield
}

const sections: SettingSection[] = [
  { id: "organization", title: "Organization", description: "Manage organization details and branding", icon: Building2 },
  { id: "ai-models", title: "AI Models", description: "Configure default models and AI behavior", icon: Brain },
  { id: "security", title: "Security", description: "Authentication, SSO, and access controls", icon: Shield },
  { id: "api-keys", title: "API Keys", description: "Manage API keys for integrations", icon: Key },
  { id: "notifications", title: "Notifications", description: "Configure alerts and notification channels", icon: Bell },
  { id: "team", title: "Team Members", description: "Invite and manage team access", icon: Users },
  { id: "webhooks", title: "Webhooks", description: "Configure outbound webhooks", icon: Webhook },
]

function OrganizationSettings() {
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [uploadDialog, setUploadDialog] = useState(false)
  const { data, error, isLoading, mutate } = useSWR<{ organization: Record<string, unknown> | null }>(
    "/api/settings/organization",
    fetcher
  )
  const organization = data?.organization ?? null

  const handleSave = async () => {
    setIsSaving(true)
    await fetch("/api/settings/organization", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: organization?.name ?? null,
        slug: organization?.slug ?? null,
        primaryDomain: organization?.primaryDomain ?? null,
        logoUrl: organization?.logoUrl ?? null,
      }),
    }).catch(() => null)
    await mutate()
    setIsSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading data"
        description="Failed to load data"
        variant="error"
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Logo Section */}
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Organization Logo
        </label>
        <div className="mt-2 flex items-center gap-4">
          <div className="flex h-16 w-32 items-center justify-center rounded-lg border border-border bg-secondary p-2">
            <Image
              src={String(organization?.logoUrl ?? "/logo-white.svg")}
              alt="Organization Logo"
              width={100}
              height={40}
              className="h-auto w-auto max-h-12"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Button variant="outline" size="sm" className="gap-2" onClick={() => setUploadDialog(true)}>
              <Upload className="h-3.5 w-3.5" />
              Upload Logo
            </Button>
            <p className="text-xs text-muted-foreground">
              PNG, SVG or JPG (max 2MB)
            </p>
          </div>
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Organization Name
        </label>
        <input
          type="text"
          defaultValue={String(organization?.name ?? "")}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Organization Slug
        </label>
        <input
          type="text"
          defaultValue={String(organization?.slug ?? "")}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Primary Domain
        </label>
        <input
          type="text"
          defaultValue={String(organization?.primaryDomain ?? "")}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <Button size="sm" className="gap-2" onClick={handleSave} disabled={isSaving}>
        {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
        {saved ? "Saved!" : "Save Changes"}
      </Button>

      {/* Upload Dialog */}
      <Dialog open={uploadDialog} onOpenChange={setUploadDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Upload Organization Logo</DialogTitle>
            <DialogDescription>Choose an image file to use as your organization logo.</DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="border-2 border-dashed border-border rounded-lg p-8 text-center">
              <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground mb-2">Drag and drop your logo here, or click to browse</p>
              <Button variant="outline" size="sm">Choose File</Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadDialog(false)}>Cancel</Button>
            <Button onClick={() => setUploadDialog(false)}>Upload</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function SecuritySettings() {
  const [ssoDialog, setSsoDialog] = useState(false)
  const [twoFaDialog, setTwoFaDialog] = useState(false)
  const [ipDialog, setIpDialog] = useState(false)
  const [twoFaEnabled, setTwoFaEnabled] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const handleEnableTwoFa = async () => {
    setIsSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setTwoFaEnabled(true)
    setIsSaving(false)
    setTwoFaDialog(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div className="flex items-center gap-3">
          <Lock className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Single Sign-On (SSO)</p>
            <p className="text-xs text-muted-foreground">Enable SAML or OIDC authentication</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setSsoDialog(true)}>Configure</Button>
      </div>
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div className="flex items-center gap-3">
          <Shield className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Two-Factor Authentication</p>
            <p className="text-xs text-muted-foreground">Require 2FA for all team members</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setTwoFaDialog(true)}>
          {twoFaEnabled ? "Enabled" : "Enable"}
        </Button>
      </div>
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div className="flex items-center gap-3">
          <Globe className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">IP Allowlist</p>
            <p className="text-xs text-muted-foreground">Restrict access to specific IP ranges</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setIpDialog(true)}>Configure</Button>
      </div>

      {/* SSO Dialog */}
      <Dialog open={ssoDialog} onOpenChange={setSsoDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Configure Single Sign-On</DialogTitle>
            <DialogDescription>Connect your identity provider for seamless authentication.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Provider Type</label>
              <select className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm text-foreground">
                <option>SAML 2.0</option>
                <option>OpenID Connect</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Entity ID</label>
              <Input placeholder="https://your-idp.com/entity" className="bg-secondary border-border" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">SSO URL</label>
              <Input placeholder="https://your-idp.com/sso" className="bg-secondary border-border" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSsoDialog(false)}>Cancel</Button>
            <Button onClick={() => setSsoDialog(false)}>Save Configuration</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 2FA Dialog */}
      <Dialog open={twoFaDialog} onOpenChange={setTwoFaDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Enable Two-Factor Authentication</DialogTitle>
            <DialogDescription>
              {twoFaEnabled 
                ? "2FA is currently enabled for all team members."
                : "All team members will be required to set up 2FA on their next login."}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {!twoFaEnabled && (
              <p className="text-sm text-muted-foreground">
                This will require all team members to authenticate using a time-based one-time password (TOTP) app like Google Authenticator or Authy.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTwoFaDialog(false)}>Cancel</Button>
            {!twoFaEnabled && (
              <Button onClick={handleEnableTwoFa} disabled={isSaving}>
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Enable 2FA
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* IP Allowlist Dialog */}
      <Dialog open={ipDialog} onOpenChange={setIpDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Configure IP Allowlist</DialogTitle>
            <DialogDescription>Only allow access from specific IP addresses or ranges.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">IP Addresses (one per line)</label>
              <textarea 
                className="w-full h-32 rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground resize-none"
                placeholder="192.168.1.0/24&#10;10.0.0.0/8&#10;203.0.113.50"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIpDialog(false)}>Cancel</Button>
            <Button onClick={() => setIpDialog(false)}>Save Allowlist</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ApiKeysSettings() {
  const [showKey, setShowKey] = useState(false)
  const [copied, setCopied] = useState(false)
  const { data, error, isLoading } = useSWR<{ apiKeys: Array<Record<string, unknown>> }>(
    "/api/settings/api-keys",
    fetcher
  )
  const apiKeys = data?.apiKeys ?? []
  const activeKey = apiKeys[0]
  const keyPrefix = String(activeKey?.keyPrefix ?? "gv_live_sk")
  const maskedKey = `${keyPrefix}_••••••••••••`
  const visibleKey = `${keyPrefix}_redacted`

  const handleCopy = () => {
    navigator.clipboard.writeText(visibleKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading data"
        description="Failed to load data"
        variant="error"
      />
    )
  }

  if (!apiKeys.length) {
    return (
      <EmptyState
        icon={Key}
        title="No API keys yet"
        description="Create your first API key to get started."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-medium text-foreground">Production API Key</p>
            <p className="text-xs text-muted-foreground">Created Jan 15, 2024</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setShowKey(!showKey)}>
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        <code className="block w-full text-xs font-mono text-muted-foreground bg-secondary rounded px-3 py-2">
          {showKey ? visibleKey : maskedKey}
        </code>
      </div>
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" className="gap-2">
          <RefreshCw className="h-3.5 w-3.5" />
          Rotate Key
        </Button>
        <Button size="sm" className="gap-2">
          <Key className="h-3.5 w-3.5" />
          Create New Key
        </Button>
      </div>
    </div>
  )
}

function NotificationSettings() {
  const [slackDialog, setSlackDialog] = useState(false)
  const { data, error, isLoading, mutate } = useSWR<{ notifications: { emailEnabled?: boolean; slackEnabled?: boolean; recipients?: string[] } }>(
    "/api/settings/notifications",
    fetcher
  )
  const [emailEnabled, setEmailEnabled] = useState(false)
  const [recipients, setRecipients] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    await fetch("/api/settings/notifications", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        emailEnabled,
        slackEnabled: Boolean(data?.notifications?.slackEnabled),
        recipients: recipients
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
      }),
    }).catch(() => null)
    await mutate()
    setIsSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  useEffect(() => {
    const incomingRecipients = data?.notifications?.recipients ?? []
    setEmailEnabled(Boolean(data?.notifications?.emailEnabled))
    setRecipients(incomingRecipients.join(", "))
  }, [data?.notifications?.emailEnabled, data?.notifications?.recipients])

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading data"
        description="Failed to load data"
        variant="error"
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div className="flex items-center gap-3">
          <Mail className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Email Notifications</p>
            <p className="text-xs text-muted-foreground">Receive alerts via email</p>
          </div>
        </div>
        <input 
          type="checkbox" 
          checked={emailEnabled} 
          onChange={(e) => setEmailEnabled(e.target.checked)}
          className="h-4 w-4 rounded border-border" 
        />
      </div>
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div className="flex items-center gap-3">
          <Bell className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Slack Notifications</p>
            <p className="text-xs text-muted-foreground">Send alerts to Slack channel</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => setSlackDialog(true)}>Configure</Button>
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Alert Recipients
        </label>
        <input
          type="text"
          value={recipients}
          onChange={(event) => setRecipients(event.target.value)}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <Button size="sm" className="gap-2" onClick={handleSave} disabled={isSaving}>
        {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
        {saved ? "Saved!" : "Save Changes"}
      </Button>

      {/* Slack Dialog */}
      <Dialog open={slackDialog} onOpenChange={setSlackDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Configure Slack Notifications</DialogTitle>
            <DialogDescription>Connect your Slack workspace to receive alerts.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Webhook URL</label>
              <Input placeholder="https://hooks.slack.com/services/..." className="bg-secondary border-border" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Channel</label>
              <Input placeholder="#alerts" className="bg-secondary border-border" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Alert Types</label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" defaultChecked className="rounded" /> Workflow failures
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" defaultChecked className="rounded" /> Approval requests
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" className="rounded" /> Successful completions
                </label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSlackDialog(false)}>Cancel</Button>
            <Button onClick={() => setSlackDialog(false)}>Save Configuration</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function TeamSettings() {
  const [inviteDialog, setInviteDialog] = useState(false)
  const [editDialog, setEditDialog] = useState<{name: string; email: string; role: string} | null>(null)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("Member")
  const [isInviting, setIsInviting] = useState(false)
  const { data, error, isLoading } = useSWR<{ team: Array<Record<string, unknown>> }>(
    "/api/settings/team",
    fetcher
  )
  const [members, setMembers] = useState<Array<{ name: string; email: string; role: string; avatar: string }>>([])

  useEffect(() => {
    const mapped = (data?.team ?? []).map((member) => {
      const name = String(member.name ?? member.email ?? "Team Member")
      return {
        name,
        email: String(member.email ?? ""),
        role: String(member.role ?? "Member"),
        avatar: name
          .split(" ")
          .map((part) => part[0])
          .join("")
          .toUpperCase()
          .slice(0, 2),
      }
    })
    setMembers(mapped)
  }, [data?.team])

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading data"
        description="Failed to load data"
        variant="error"
      />
    )
  }

  if (!members.length) {
    return (
      <EmptyState
        icon={Users}
        title="No team members yet"
        description="Invite a teammate to collaborate."
      />
    )
  }

  const handleInvite = async () => {
    setIsInviting(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    const name = inviteEmail.split("@")[0].split(".").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(" ")
    setMembers([...members, {
      name,
      email: inviteEmail,
      role: inviteRole,
      avatar: name.split(" ").map(s => s[0]).join("").toUpperCase().slice(0, 2)
    }])
    setIsInviting(false)
    setInviteEmail("")
    setInviteDialog(false)
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-secondary/30">
              <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">Member</th>
              <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">Role</th>
              <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.email} className="border-b border-border last:border-0">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                      {member.avatar}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{member.name}</p>
                      <p className="text-xs text-muted-foreground">{member.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                    member.role === "Admin" ? "bg-info/10 text-info" : "bg-muted text-muted-foreground"
                  }`}>
                    {member.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEditDialog(member)}>
                    Edit
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Button size="sm" className="gap-2" onClick={() => setInviteDialog(true)}>
        <Users className="h-3.5 w-3.5" />
        Invite Member
      </Button>

      {/* Invite Dialog */}
      <Dialog open={inviteDialog} onOpenChange={setInviteDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>Send an invitation to join your organization.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Email Address</label>
              <Input 
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com" 
                className="bg-secondary border-border" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Role</label>
              <select 
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm text-foreground"
              >
                <option value="Member">Member</option>
                <option value="Admin">Admin</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteDialog(false)}>Cancel</Button>
            <Button onClick={handleInvite} disabled={isInviting || !inviteEmail}>
              {isInviting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Send Invite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Member Dialog */}
      <Dialog open={!!editDialog} onOpenChange={() => setEditDialog(null)}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Edit Team Member</DialogTitle>
            <DialogDescription>Update role or remove {editDialog?.name} from the team.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-sm font-medium text-muted-foreground">
                {editDialog?.name.split(" ").map(s => s[0]).join("").toUpperCase().slice(0, 2)}
              </div>
              <div>
                <p className="font-medium text-foreground">{editDialog?.name}</p>
                <p className="text-xs text-muted-foreground">{editDialog?.email}</p>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Role</label>
              <select 
                defaultValue={editDialog?.role}
                className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm text-foreground"
              >
                <option value="Member">Member</option>
                <option value="Admin">Admin</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="destructive" size="sm" onClick={() => {
              setMembers(members.filter(m => m.email !== editDialog?.email))
              setEditDialog(null)
            }}>
              Remove from Team
            </Button>
            <Button variant="outline" onClick={() => setEditDialog(null)}>Cancel</Button>
            <Button onClick={() => setEditDialog(null)}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function WebhooksSettings() {
  const [addDialog, setAddDialog] = useState(false)
  const [newUrl, setNewUrl] = useState("")
  const [selectedEvents, setSelectedEvents] = useState<string[]>([])
  const { data, error, isLoading } = useSWR<{ webhooks: Array<Record<string, unknown>> }>(
    "/api/settings/webhooks",
    fetcher
  )
  const [webhooks, setWebhooks] = useState<Array<{ url: string; events: string[]; status: string }>>([])
  const [isAdding, setIsAdding] = useState(false)

  const availableEvents = [
    "workflow.completed",
    "workflow.failed",
    "run.started",
    "run.failed",
    "approval.pending",
    "approval.completed",
  ]

  const handleAddWebhook = async () => {
    setIsAdding(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setWebhooks([...webhooks, { url: newUrl, events: selectedEvents, status: "active" }])
    setIsAdding(false)
    setNewUrl("")
    setSelectedEvents([])
    setAddDialog(false)
  }

  useEffect(() => {
    const mapped = (data?.webhooks ?? []).map((hook) => ({
      url: String(hook.url ?? ""),
      events: Array.isArray(hook.events) ? hook.events.map((event) => String(event)) : [],
      status: String(hook.status ?? "active"),
    }))
    setWebhooks(mapped)
  }, [data?.webhooks])

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading data"
        description="Failed to load data"
        variant="error"
      />
    )
  }

  const handleDeleteWebhook = (index: number) => {
    setWebhooks(webhooks.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-6">
      {webhooks.map((webhook, i) => (
        <div key={i} className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-start justify-between mb-2">
            <code className="text-xs font-mono text-foreground">{webhook.url}</code>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-success/10 text-success">
                {webhook.status}
              </span>
              <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleDeleteWebhook(i)}>
                <X className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {webhook.events.map((event) => (
              <span key={event} className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                {event}
              </span>
            ))}
          </div>
        </div>
      ))}
      <Button size="sm" className="gap-2" onClick={() => setAddDialog(true)}>
        <Webhook className="h-3.5 w-3.5" />
        Add Webhook
      </Button>

      {/* Add Webhook Dialog */}
      <Dialog open={addDialog} onOpenChange={setAddDialog}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Add Webhook</DialogTitle>
            <DialogDescription>Configure a new outbound webhook endpoint.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Webhook URL</label>
              <Input 
                type="url"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://your-server.com/webhook" 
                className="bg-secondary border-border" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Events to Subscribe</label>
              <div className="space-y-2">
                {availableEvents.map((event) => (
                  <label key={event} className="flex items-center gap-2 text-sm">
                    <input 
                      type="checkbox" 
                      checked={selectedEvents.includes(event)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedEvents([...selectedEvents, event])
                        } else {
                          setSelectedEvents(selectedEvents.filter(e => e !== event))
                        }
                      }}
                      className="rounded" 
                    /> 
                    {event}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialog(false)}>Cancel</Button>
            <Button onClick={handleAddWebhook} disabled={isAdding || !newUrl || selectedEvents.length === 0}>
              {isAdding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Add Webhook
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function AIModelsSettings() {
  const { data, error, isLoading, mutate } = useSWR<{ modelSettings: Record<string, unknown> | null }>(
    "/api/settings/models",
    fetcher
  )
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [workspaceModel, setWorkspaceModel] = useState("auto")
  const [operatorModel, setOperatorModel] = useState("auto")
  const [agentDefaultModel, setAgentDefaultModel] = useState("balanced")
  const [fallbackModel, setFallbackModel] = useState("fast")

  const handleSave = async () => {
    setIsSaving(true)
    await fetch("/api/settings/models", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspaceModel,
        operatorModel,
        agentDefaultModel,
        fallbackModel,
      }),
    }).catch(() => null)
    await mutate()
    setIsSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  useEffect(() => {
    const settings = data?.modelSettings ?? null
    if (!settings) return
    setWorkspaceModel(String(settings.workspaceModel ?? "auto"))
    setOperatorModel(String(settings.operatorModel ?? "auto"))
    setAgentDefaultModel(String(settings.agentDefaultModel ?? "balanced"))
    setFallbackModel(String(settings.fallbackModel ?? "fast"))
  }, [data?.modelSettings])

  useEffect(() => {
    if (error) {
      toast.error("Failed to load data")
    }
  }, [error])

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Error loading data"
        description="Failed to load data"
        variant="error"
      />
    )
  }

  return (
    <div className="space-y-8">
      {/* Workspace Default */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-foreground">Workspace Default Model</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            The default model used across your workspace when no override is specified
          </p>
        </div>
        <ModelSelector
          value={workspaceModel}
          onChange={setWorkspaceModel}
          showAdvanced
        />
        <div className="flex items-start gap-2 p-3 rounded-lg bg-info/5 border border-info/20">
          <Sparkles className="h-4 w-4 text-info shrink-0 mt-0.5" />
          <div className="text-xs text-muted-foreground">
            <span className="text-info font-medium">Auto-select</span> analyzes each task and picks the best model automatically. Recommended for most workspaces.
          </div>
        </div>
      </div>

      {/* Use Case Defaults */}
      <div className="space-y-4 pt-6 border-t border-border">
        <div>
          <h3 className="text-sm font-medium text-foreground">Default by Use Case</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Set preferred models for specific types of AI tasks
          </p>
        </div>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/10 text-violet-500">
                <Brain className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">AI Operator</p>
                <p className="text-xs text-muted-foreground">Analysis, debugging, recommendations</p>
              </div>
            </div>
            <ModelSelector
              value={operatorModel}
              onChange={setOperatorModel}
              size="sm"
            />
          </div>

          <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500">
                <Users className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">Agent Default</p>
                <p className="text-xs text-muted-foreground">New agents inherit this model</p>
              </div>
            </div>
            <ModelSelector
              value={agentDefaultModel}
              onChange={setAgentDefaultModel}
              size="sm"
            />
          </div>
        </div>
      </div>

      {/* Fallback Model */}
      <div className="space-y-4 pt-6 border-t border-border">
        <div>
          <h3 className="text-sm font-medium text-foreground">Fallback Model</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Used when the primary model is unavailable or rate-limited
          </p>
        </div>
        <ModelSelector
          value={fallbackModel}
          onChange={setFallbackModel}
        />
      </div>

      {/* Model Policies */}
      <div className="space-y-4 pt-6 border-t border-border">
        <div>
          <h3 className="text-sm font-medium text-foreground">Model Policies</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Control how models can be used in your workspace
          </p>
        </div>
        
        <div className="space-y-3">
          <label className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/30 cursor-pointer hover:bg-secondary/50 transition-colors">
            <div className="flex items-center gap-3">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">Allow model overrides</p>
                <p className="text-xs text-muted-foreground">Users can override defaults per task</p>
              </div>
            </div>
            <input type="checkbox" defaultChecked className="rounded border-border" />
          </label>

          <label className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/30 cursor-pointer hover:bg-secondary/50 transition-colors">
            <div className="flex items-center gap-3">
              <Info className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">Show model in activity logs</p>
                <p className="text-xs text-muted-foreground">Log which model was used for each task</p>
              </div>
            </div>
            <input type="checkbox" defaultChecked className="rounded border-border" />
          </label>
        </div>
      </div>

      <Button size="sm" className="gap-2" onClick={handleSave} disabled={isSaving}>
        {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : saved ? <Check className="h-3.5 w-3.5" /> : <Save className="h-3.5 w-3.5" />}
        {saved ? "Saved!" : "Save Changes"}
      </Button>
    </div>
  )
}

function SettingsPageContent() {
  const searchParams = useSearchParams()
  const initialSection = searchParams.get('section') || "organization"
  const [activeSection, setActiveSection] = useState(initialSection)

  const renderContent = () => {
    switch (activeSection) {
      case "organization": return <OrganizationSettings />
      case "ai-models": return <AIModelsSettings />
      case "security": return <SecuritySettings />
      case "api-keys": return <ApiKeysSettings />
      case "notifications": return <NotificationSettings />
      case "team": return <TeamSettings />
      case "webhooks": return <WebhooksSettings />
      default: return <OrganizationSettings />
    }
  }

  return (
    <AppShell title="Settings">
      <div className="flex h-full">
        {/* Sidebar */}
        <div className="w-64 border-r border-border p-4">
          <nav className="space-y-1">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`w-full flex items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors ${
                  activeSection === section.id
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                <section.icon className="h-4 w-4 shrink-0" />
                <span>{section.title}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 p-6">
          <div className="max-w-2xl">
            <h1 className="text-xl font-semibold text-foreground mb-1">
              {sections.find((s) => s.id === activeSection)?.title}
            </h1>
            <p className="text-sm text-muted-foreground mb-6">
              {sections.find((s) => s.id === activeSection)?.description}
            </p>
            {renderContent()}
          </div>
        </div>
      </div>
    </AppShell>
  )
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <SettingsPageContent />
    </Suspense>
  )
}
