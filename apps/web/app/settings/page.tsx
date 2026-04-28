"use client"

import { useEffect, useState, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import useSWR from "swr"
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
  Plus,
  Trash2,
  DollarSign,
} from "lucide-react"
import { ModelSelector } from "@/components/gravitre/model-selector"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { settingsApi } from "@/lib/api"
import type { ApiKey, BillingUsageResponse, LiteSeatDepartment, MesonAddon, User } from "@/types/api"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

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
  { id: "lite-seats", title: "Lite Seats", description: "Allocate Gravitre Lite seats by department", icon: Users },
  { id: "meson-addons", title: "Meson Addons", description: "Enable premium AI addon capabilities", icon: Sparkles },
  { id: "billing-usage", title: "Billing Usage", description: "Review outputs and overage usage", icon: DollarSign },
  { id: "webhooks", title: "Webhooks", description: "Configure outbound webhooks", icon: Webhook },
]

function OrganizationSettings({
  orgData,
  onUpdate,
  isAdmin,
}: {
  orgData?: Record<string, unknown>
  onUpdate: () => Promise<void>
  isAdmin: boolean
}) {
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [uploadDialog, setUploadDialog] = useState(false)
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [domain, setDomain] = useState("")

  useEffect(() => {
    if (!orgData) return
    setName(String(orgData.name ?? ""))
    setSlug(String(orgData.slug ?? ""))
    setDomain(String(orgData.primaryDomain ?? orgData.primary_domain ?? ""))
  }, [orgData])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await settingsApi.updateOrg({
        name,
        slug,
        primaryDomain: domain,
      })
      toast.success("Organization settings saved")
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await onUpdate()
    } catch (err) {
      console.error("[v0] Failed to save org settings:", err)
      toast.error("Failed to save settings")
    } finally {
      setIsSaving(false)
    }
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
              src="/logo-white.svg"
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
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={!isAdmin}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Organization Slug
        </label>
        <input
          type="text"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          disabled={!isAdmin}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Primary Domain
        </label>
        <input
          type="text"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          disabled={!isAdmin}
          className="mt-2 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-1 focus:ring-ring"
        />
      </div>
      <Button size="sm" className="gap-2" onClick={handleSave} disabled={isSaving || !isAdmin}>
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

function ApiKeysSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, mutate } = useSWR(isAdmin ? "/api/settings/api-keys" : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const [showKeyId, setShowKeyId] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [rotatingKeyId, setRotatingKeyId] = useState<string | null>(null)

  const apiKeys = (data as { apiKeys?: ApiKey[] } | undefined)?.apiKeys ?? []

  const handleCopy = (key: ApiKey) => {
    const value = key.key || key.key_prefix
    navigator.clipboard.writeText(value)
    setCopiedId(key.id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleCreateKey = async () => {
    setIsCreating(true)
    try {
      await settingsApi.createApiKey("Production Key")
      toast.success("API key created - copy it now, it won't be shown again")
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to create API key:", err)
      toast.error("Failed to create API key")
    } finally {
      setIsCreating(false)
    }
  }

  const handleRotateKey = async (keyId: string) => {
    if (!confirm("Rotating this key will invalidate the old key immediately. Continue?")) return
    setRotatingKeyId(keyId)
    try {
      await settingsApi.rotateApiKey(keyId)
      toast.success("API key rotated")
      await mutate()
    } catch (err) {
      console.error("[v0] Failed to rotate API key:", err)
      toast.error("Failed to rotate key")
    } finally {
      setRotatingKeyId(null)
    }
  }

  return (
    <div className="space-y-6">
      {apiKeys.map((apiKey) => (
        <div key={apiKey.id} className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm font-medium text-foreground">{apiKey.name}</p>
              <p className="text-xs text-muted-foreground">
                Created {apiKey.created_at ? new Date(apiKey.created_at).toLocaleDateString() : "recently"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setShowKeyId(showKeyId === apiKey.id ? null : apiKey.id)}
              >
                {showKeyId === apiKey.id ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleCopy(apiKey)}>
                {copiedId === apiKey.id ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <code className="block w-full text-xs font-mono text-muted-foreground bg-secondary rounded px-3 py-2">
            {showKeyId === apiKey.id ? apiKey.key_prefix : `${apiKey.key_prefix}••••••••`}
          </code>
        </div>
      ))}
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          disabled={!isAdmin || apiKeys.length === 0 || Boolean(rotatingKeyId)}
          onClick={() => apiKeys[0] && handleRotateKey(apiKeys[0].id)}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", rotatingKeyId && "animate-spin")} />
          Rotate Key
        </Button>
        <Button size="sm" className="gap-2" disabled={!isAdmin || isCreating} onClick={handleCreateKey}>
          {isCreating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Key className="h-3.5 w-3.5" />}
          Create New Key
        </Button>
        {!isAdmin && (
          <span className="text-xs text-muted-foreground">Admin/Owner required</span>
        )}
      </div>
    </div>
  )
}

function NotificationSettings() {
  const [slackDialog, setSlackDialog] = useState(false)
  const [emailEnabled, setEmailEnabled] = useState(true)
  const [recipients, setRecipients] = useState("ops@acme.com, alerts@acme.com")
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await settingsApi.update({
        notifications: {
          emailEnabled,
          recipients,
        },
      })
      setSaved(true)
      toast.success("Notification settings saved")
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      console.error("[v0] Failed to save notifications:", err)
      toast.error("Failed to save notification settings")
    } finally {
      setIsSaving(false)
    }
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
          onChange={(e) => setRecipients(e.target.value)}
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

function TeamSettings({
  members,
  onUpdate,
  isAdmin,
}: {
  members: User[]
  onUpdate: () => Promise<void>
  isAdmin: boolean
}) {
  const [inviteDialog, setInviteDialog] = useState(false)
  const [editDialog, setEditDialog] = useState<{name: string; email: string; role: string} | null>(null)
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [isInviting, setIsInviting] = useState(false)
  const [isRemoving, setIsRemoving] = useState<string | null>(null)

  const handleInvite = async () => {
    if (!isAdmin) return
    setIsInviting(true)
    try {
      await settingsApi.inviteMember(inviteEmail, inviteRole)
      toast.success(`Invitation sent to ${inviteEmail}`)
      setInviteEmail("")
      setInviteDialog(false)
      await onUpdate()
    } catch (err) {
      console.error("[v0] Failed to invite member:", err)
      toast.error("Failed to send invitation")
    } finally {
      setIsInviting(false)
    }
  }

  const handleRemoveMember = async (userId: string, userName: string) => {
    if (!isAdmin) return
    if (!confirm(`Remove ${userName} from the organization?`)) return
    setIsRemoving(userId)
    try {
      await settingsApi.removeMember(userId)
      toast.success(`${userName} removed`)
      await onUpdate()
    } catch (err) {
      console.error("[v0] Failed to remove member:", err)
      toast.error("Failed to remove member")
    } finally {
      setIsRemoving(null)
      setEditDialog(null)
    }
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
              <tr key={member.id ?? member.email} className="border-b border-border last:border-0">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                      {(member.full_name ?? member.email ?? "U")
                        .split(" ")
                        .map((s) => s[0])
                        .join("")
                        .toUpperCase()
                        .slice(0, 2)}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{member.full_name ?? member.email}</p>
                      <p className="text-xs text-muted-foreground">{member.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                    member.role === "admin" || member.role === "owner" ? "bg-info/10 text-info" : "bg-muted text-muted-foreground"
                  }`}>
                    {member.role ?? "member"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => setEditDialog({ name: member.full_name ?? "", email: member.email, role: member.role ?? "member" })}
                    disabled={!isAdmin}
                  >
                    Edit
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Button size="sm" className="gap-2" onClick={() => setInviteDialog(true)} disabled={!isAdmin}>
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
                <option value="member">Member</option>
                <option value="admin">Admin</option>
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
                disabled={!isAdmin}
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="destructive"
              size="sm"
              disabled={!isAdmin || !editDialog || !members.find((m) => m.email === editDialog.email)}
              onClick={() => {
                const member = members.find((m) => m.email === editDialog?.email)
                if (member?.id) {
                  void handleRemoveMember(member.id, member.full_name ?? member.email)
                }
              }}
            >
              {isRemoving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
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
  const [webhooks, setWebhooks] = useState([
    { url: "https://api.slack.com/hooks/xxx", events: ["workflow.completed", "approval.pending"], status: "active" },
    { url: "https://hooks.zapier.com/xxx", events: ["run.failed"], status: "active" },
  ])
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
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [workspaceModel, setWorkspaceModel] = useState("auto")
  const [operatorModel, setOperatorModel] = useState("auto")
  const [agentDefaultModel, setAgentDefaultModel] = useState("balanced")
  const [fallbackModel, setFallbackModel] = useState("fast")

  const handleSave = async () => {
    setIsSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setIsSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
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

function LiteSeatsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, mutate } = useSWR(isAdmin ? "/api/settings/lite-seats" : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const summary = (data as { summary?: { included: number; allocated: number; used: number } } | undefined)?.summary
  const departments = ((data as { departments?: LiteSeatDepartment[] } | undefined)?.departments ?? []) as LiteSeatDepartment[]
  const [newDeptName, setNewDeptName] = useState("")
  const [newDeptSeats, setNewDeptSeats] = useState(0)
  const [isSaving, setIsSaving] = useState(false)

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

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-secondary/30 p-4">
        <p className="text-sm font-medium text-foreground">Gravitre Lite Seats</p>
        <p className="text-xs text-muted-foreground mt-1">
          Included: {summary?.included ?? 0} | Allocated: {summary?.allocated ?? 0} | Used: {summary?.used ?? 0}
        </p>
      </div>

      <div className="space-y-3">
        {departments.map((department) => (
          <div key={department.id} className="rounded-lg border border-border bg-card p-4">
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
          </div>
        ))}
      </div>

      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <p className="text-sm font-medium text-foreground">Add Department</p>
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
          Add Department
        </Button>
      </div>
    </div>
  )
}

function MesonAddonsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, mutate } = useSWR(isAdmin ? "/api/settings/meson-addons" : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const addons = ((data as { addons?: MesonAddon[] } | undefined)?.addons ?? []) as MesonAddon[]
  const monthlyTotal = Number((data as { monthly_total_usd?: number } | undefined)?.monthly_total_usd ?? 0)
  const [isSaving, setIsSaving] = useState(false)

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

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border bg-secondary/30 p-4">
        <p className="text-sm font-medium text-foreground">Monthly addon total</p>
        <p className="text-lg font-semibold text-foreground mt-1">${monthlyTotal.toFixed(2)}</p>
      </div>
      <div className="space-y-3">
        {addons.map((addon) => (
          <div key={addon.code} className="rounded-lg border border-border bg-card p-4">
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
    </div>
  )
}

function BillingUsageSettings() {
  const { data, isLoading, mutate } = useSWR("/api/settings/billing-usage", apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 30000,
  })
  const usage = (data ?? {}) as BillingUsageResponse
  const totals = usage.totals ?? { outputs: 0, workflow_runs: 0, api_calls: 0, ai_tokens: 0 }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div>
          <p className="text-sm font-medium text-foreground">Outputs this cycle</p>
          <p className="text-xs text-muted-foreground mt-1">
            Included: {usage.included_outputs ?? "Unlimited"} | Overage: {usage.overage_outputs ?? 0}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => mutate()}>
          Refresh
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase">Outputs</p>
          <p className="text-xl font-semibold mt-1">{totals.outputs.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase">Workflow Runs</p>
          <p className="text-xl font-semibold mt-1">{totals.workflow_runs.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase">API Calls</p>
          <p className="text-xl font-semibold mt-1">{totals.api_calls.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase">AI Tokens</p>
          <p className="text-xl font-semibold mt-1">{totals.ai_tokens.toLocaleString()}</p>
        </div>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs text-muted-foreground uppercase">Estimated overage charge</p>
        <p className="text-2xl font-semibold mt-1">${Number(usage.overage_cost_usd ?? 0).toFixed(2)}</p>
        {isLoading && <p className="text-xs text-muted-foreground mt-2">Loading usage...</p>}
      </div>
    </div>
  )
}

function SettingsContent() {
  const searchParams = useSearchParams()
  const { user, loading: authLoading } = useAuth()
  const initialSection = searchParams.get('section') || "organization"
  const [activeSection, setActiveSection] = useState(initialSection)
  const isAdmin = user?.role === "admin" || user?.role === "owner"

  const { data: orgData, mutate: mutateOrg } = useSWR(
    user ? "/api/settings/organization" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const { data: teamData, mutate: mutateTeam } = useSWR(
    user ? "/api/settings/team" : null,
    apiFetcher,
    { revalidateOnFocus: false }
  )

  const organization = (orgData as { organization?: Record<string, unknown> } | undefined)?.organization
  const team = ((teamData as { team?: User[] } | undefined)?.team ?? []) as User[]
  const adminOnlySections = new Set([
    "organization",
    "ai-models",
    "security",
    "api-keys",
    "team",
    "webhooks",
    "lite-seats",
    "meson-addons",
    "billing-usage",
  ])

  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const renderContent = () => {
    if (adminOnlySections.has(activeSection) && !isAdmin) {
      return (
        <div className="rounded-lg border border-border bg-secondary/30 p-4 text-sm text-muted-foreground">
          Admin or owner permission is required to manage this section.
        </div>
      )
    }

    switch (activeSection) {
      case "organization":
        return (
          <OrganizationSettings
            orgData={organization}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateOrg()
            }}
          />
        )
      case "ai-models": return <AIModelsSettings />
      case "security": return <SecuritySettings />
      case "api-keys": return <ApiKeysSettings isAdmin={isAdmin} />
      case "notifications": return <NotificationSettings />
      case "team":
        return (
          <TeamSettings
            members={team}
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
      case "billing-usage":
        return <BillingUsageSettings />
      case "webhooks": return <WebhooksSettings />
      default:
        return (
          <OrganizationSettings
            orgData={organization}
            isAdmin={isAdmin}
            onUpdate={async () => {
              await mutateOrg()
            }}
          />
        )
    }
  }

  return (
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
