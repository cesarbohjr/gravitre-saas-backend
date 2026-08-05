"use client"

import React, { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import Image from "next/image"
import { AppShell } from "@/components/gravitre/app-shell"
import { AdaptiveDataView } from "@/components/gravitre/adaptive-data-view"
import { ModelSelector } from "@/components/gravitre/model-selector"
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
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { settingsApi, ssoApi } from "@/lib/api"
import { MemoryEntityEmbeddingsSettings } from "@/components/settings/memory-entity-embeddings-settings"
import type { ApiKey, BillingUsageResponse, LiteSeatDepartment, MesonAddon, SSOConfiguration, SSOProviderType, User } from "@/types/api"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { SettingsShell, canAccessSettingsSection } from "@/components/settings/settings-shell"
import { settingsHrefForSection, type SettingsSectionId } from "@/lib/settings-sections"
import { useOrgAdmin } from "@/lib/use-org-admin"

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
    const timer = setTimeout(() => {
      setName(String(orgData.name ?? ""))
      setSlug(String(orgData.slug ?? ""))
      setDomain(String(orgData.primaryDomain ?? orgData.primary_domain ?? ""))
    }, 0)
    return () => clearTimeout(timer)
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
  const { user } = useAuth()
  const { data: ssoConfig, mutate: mutateSso } = useSWR<SSOConfiguration | null>(
    user ? "/api/auth/sso/config" : null,
    () => ssoApi.getConfig(),
    { revalidateOnFocus: false }
  )

  const [ssoDialog, setSsoDialog] = useState(false)
  const [twoFaDialog, setTwoFaDialog] = useState(false)
  const [ipDialog, setIpDialog] = useState(false)
  const [twoFaEnabled, setTwoFaEnabled] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [providerType, setProviderType] = useState<SSOProviderType>("saml")
  const [entityId, setEntityId] = useState("")
  const [ssoUrl, setSsoUrl] = useState("")
  const [certificate, setCertificate] = useState("")
  const [oidcIssuer, setOidcIssuer] = useState("")
  const [oidcClientId, setOidcClientId] = useState("")
  const [oidcClientSecret, setOidcClientSecret] = useState("")
  const [isTogglingSso, setIsTogglingSso] = useState(false)
  const [isDeletingSso, setIsDeletingSso] = useState(false)
  const [isTestingSso, setIsTestingSso] = useState(false)

  useEffect(() => {
    if (!ssoConfig) return
    const timer = setTimeout(() => {
      setProviderType(ssoConfig.provider_type)
      setEntityId(ssoConfig.saml_entity_id || "")
      setSsoUrl(ssoConfig.saml_sso_url || "")
      setOidcIssuer(ssoConfig.oidc_issuer || "")
      setOidcClientId(ssoConfig.oidc_client_id || "")
    }, 0)
    return () => clearTimeout(timer)
  }, [ssoConfig])

  const handleEnableTwoFa = async () => {
    setIsSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    setTwoFaEnabled(true)
    setIsSaving(false)
    setTwoFaDialog(false)
  }

  const handleSaveSso = async () => {
    setIsSaving(true)
    try {
      await ssoApi.saveConfig({
        provider_type: providerType,
        saml_entity_id: providerType === "saml" ? entityId : undefined,
        saml_sso_url: providerType === "saml" ? ssoUrl : undefined,
        saml_certificate: providerType === "saml" ? certificate : undefined,
        oidc_issuer: providerType === "oidc" ? oidcIssuer : undefined,
        oidc_client_id: providerType === "oidc" ? oidcClientId : undefined,
        oidc_client_secret: providerType === "oidc" ? oidcClientSecret : undefined,
      })
      toast.success("SSO configuration saved")
      await mutateSso()
      setSsoDialog(false)
    } catch (err) {
      console.error("[v0] SSO save failed:", err)
      toast.error("Failed to save SSO configuration")
    } finally {
      setIsSaving(false)
    }
  }

  const handleToggleSso = async () => {
    setIsTogglingSso(true)
    try {
      if (ssoConfig?.is_enabled) {
        await ssoApi.disable()
        toast.success("SSO disabled")
      } else {
        await ssoApi.enable()
        toast.success("SSO enabled")
      }
      await mutateSso()
    } catch (err) {
      console.error("[v0] SSO toggle failed:", err)
      toast.error("Failed to toggle SSO")
    } finally {
      setIsTogglingSso(false)
    }
  }

  const handleDeleteSso = async () => {
    setIsDeletingSso(true)
    try {
      await ssoApi.deleteConfig()
      toast.success("SSO configuration deleted")
      await mutateSso()
      setSsoDialog(false)
      setEntityId("")
      setSsoUrl("")
      setCertificate("")
      setOidcIssuer("")
      setOidcClientId("")
      setOidcClientSecret("")
      setProviderType("saml")
    } catch (err) {
      console.error("[v0] SSO delete failed:", err)
      toast.error("Failed to delete SSO configuration")
    } finally {
      setIsDeletingSso(false)
    }
  }

  const getMetadataUrl = () => {
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/$/, "")
    if (apiBase) return `${apiBase}/api/auth/sso/metadata`
    if (typeof window !== "undefined") return `${window.location.origin}/api/auth/sso/metadata`
    return "/api/auth/sso/metadata"
  }

  const handleCopyMetadataUrl = async () => {
    try {
      await navigator.clipboard.writeText(getMetadataUrl())
      toast.success("SP metadata URL copied")
    } catch (err) {
      console.error("[v0] Failed to copy metadata URL:", err)
      toast.error("Failed to copy metadata URL")
    }
  }

  const handleTestSsoLogin = async () => {
    if (!ssoConfig?.is_enabled) {
      toast.error("Enable SSO before testing")
      return
    }
    setIsTestingSso(true)
    try {
      const result = await ssoApi.initLogin()
      if (!result.redirect_url) {
        throw new Error("Missing redirect URL")
      }
      window.location.href = result.redirect_url
    } catch (err) {
      console.error("[v0] SSO test init failed:", err)
      toast.error("Failed to initialize SSO login test")
      setIsTestingSso(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between rounded-lg border border-border bg-secondary/30 p-4">
        <div className="flex items-center gap-3">
          <Lock className="h-5 w-5 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium text-foreground">Single Sign-On (SSO)</p>
            <p className="text-xs text-muted-foreground">
              {ssoConfig
                ? `${ssoConfig.provider_type.toUpperCase()} configured ${ssoConfig.is_enabled ? "and enabled" : "but disabled"}`
                : "Enable SAML or OIDC authentication"}
            </p>
            <p className="text-[11px] text-muted-foreground mt-1">
              SP metadata: <span className="font-mono">{getMetadataUrl()}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCopyMetadataUrl} disabled={!ssoConfig}>
            Copy Metadata URL
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleTestSsoLogin}
            disabled={!ssoConfig?.is_enabled || isTestingSso}
          >
            {isTestingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : "Test SSO"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setSsoDialog(true)}>
            Configure
          </Button>
          <Button
            size="sm"
            variant={ssoConfig?.is_enabled ? "outline" : "default"}
            onClick={handleToggleSso}
            disabled={!ssoConfig || isTogglingSso}
          >
            {isTogglingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : ssoConfig?.is_enabled ? "Disable" : "Enable"}
          </Button>
        </div>
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
              <select
                className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm text-foreground"
                value={providerType}
                onChange={(event) => setProviderType(event.target.value as SSOProviderType)}
              >
                <option value="saml">SAML 2.0</option>
                <option value="oidc">OpenID Connect</option>
              </select>
            </div>
            {providerType === "saml" ? (
              <>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">Entity ID</label>
                  <Input
                    placeholder="https://your-idp.com/entity"
                    className="bg-secondary border-border"
                    value={entityId}
                    onChange={(event) => setEntityId(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">SSO URL</label>
                  <Input
                    placeholder="https://your-idp.com/sso"
                    className="bg-secondary border-border"
                    value={ssoUrl}
                    onChange={(event) => setSsoUrl(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">X.509 Certificate</label>
                  <textarea
                    className="w-full h-28 rounded-md border border-border bg-secondary px-3 py-2 text-sm text-foreground resize-none"
                    placeholder="-----BEGIN CERTIFICATE-----"
                    value={certificate}
                    onChange={(event) => setCertificate(event.target.value)}
                  />
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">Issuer URL</label>
                  <Input
                    placeholder="https://your-idp.com"
                    className="bg-secondary border-border"
                    value={oidcIssuer}
                    onChange={(event) => setOidcIssuer(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">Client ID</label>
                  <Input
                    placeholder="OIDC client id"
                    className="bg-secondary border-border"
                    value={oidcClientId}
                    onChange={(event) => setOidcClientId(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground uppercase">Client Secret</label>
                  <Input
                    type="password"
                    placeholder="OIDC client secret"
                    className="bg-secondary border-border"
                    value={oidcClientSecret}
                    onChange={(event) => setOidcClientSecret(event.target.value)}
                  />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSsoDialog(false)}>Cancel</Button>
            <Button variant="outline" onClick={handleDeleteSso} disabled={!ssoConfig || isDeletingSso}>
              {isDeletingSso ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Delete
            </Button>
            <Button onClick={handleSaveSso} disabled={isSaving}>
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Save Configuration
            </Button>
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

type TeamEditMember = {
  id?: string
  name: string
  email: string
  role: string
  avatarUrl?: string | null
  jobTitle?: string | null
  department?: string | null
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
  const [editDialog, setEditDialog] = useState<TeamEditMember | null>(null)
  const [editRole, setEditRole] = useState("member")
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [isInviting, setIsInviting] = useState(false)
  const [isRemoving, setIsRemoving] = useState<string | null>(null)
  const [isSavingRole, setIsSavingRole] = useState(false)

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

  const openEditDialog = (member: User) => {
    const role = member.role ?? "member"
    setEditRole(role)
    setEditDialog({
      id: member.id,
      name: member.full_name ?? member.email,
      email: member.email,
      role,
      avatarUrl: member.avatar_url,
      jobTitle: member.job_title,
      department: member.department,
    })
  }

  const handleSaveRole = async () => {
    if (!isAdmin || !editDialog) return
    setIsSavingRole(true)
    try {
      await settingsApi.updateMember({
        id: editDialog.id,
        email: editDialog.email,
        role: editRole,
      })
      toast.success("Member role updated")
      setEditDialog(null)
      await onUpdate()
    } catch (err) {
      console.error("[v0] Failed to update member role:", err)
      toast.error("Failed to update member role")
    } finally {
      setIsSavingRole(false)
    }
  }

  return (
    <div className="space-y-6">
      <AdaptiveDataView className="rounded-lg border border-border overflow-hidden">
        <table className="w-full min-w-[480px]">
          <thead>
            <tr className="border-b border-border bg-secondary/30">
              <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">Member</th>
              <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">Role</th>
              <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const titleLine = [member.job_title, member.department].filter(Boolean).join(" · ")
              return (
              <tr key={member.id ?? member.email} className="border-b border-border last:border-0">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <UserAccountAvatar
                      name={member.full_name}
                      email={member.email}
                      avatarUrl={member.avatar_url}
                      size="sm"
                    />
                    <div>
                      <p className="text-sm font-medium text-foreground">{member.full_name ?? member.email}</p>
                      <p className="text-xs text-muted-foreground">{member.email}</p>
                      {titleLine ? (
                        <p className="text-[11px] text-muted-foreground/80">{titleLine}</p>
                      ) : null}
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
                    onClick={() => openEditDialog(member)}
                    disabled={!isAdmin}
                  >
                    Edit
                  </Button>
                </td>
              </tr>
              )
            })}
          </tbody>
        </table>
      </AdaptiveDataView>
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
            <DialogDescription>
              Update role or remove {editDialog?.name || "this member"} from the team. Title and
              department come from their profile.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-secondary/30">
              <UserAccountAvatar
                name={editDialog?.name}
                email={editDialog?.email}
                avatarUrl={editDialog?.avatarUrl}
                size="md"
              />
              <div className="min-w-0">
                <p className="font-medium text-foreground truncate">{editDialog?.name || "Team member"}</p>
                <p className="text-xs text-muted-foreground truncate">{editDialog?.email}</p>
                {[editDialog?.jobTitle, editDialog?.department].filter(Boolean).length > 0 ? (
                  <p className="mt-0.5 text-[11px] text-muted-foreground/90">
                    {[editDialog?.jobTitle, editDialog?.department].filter(Boolean).join(" · ")}
                  </p>
                ) : (
                  <p className="mt-0.5 text-[11px] text-muted-foreground/70">
                    No title or department on profile yet
                  </p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground uppercase">Role</label>
              <select
                value={editRole}
                onChange={(event) => setEditRole(event.target.value)}
                className="w-full h-9 rounded-md border border-border bg-secondary px-3 text-sm text-foreground"
                disabled={!isAdmin || isSavingRole}
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
              disabled={!isAdmin || !editDialog || !members.find((m) => m.email === editDialog.email) || isSavingRole}
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
            <Button variant="outline" onClick={() => setEditDialog(null)} disabled={isSavingRole}>
              Cancel
            </Button>
            <Button onClick={() => void handleSaveRole()} disabled={!isAdmin || isSavingRole}>
              {isSavingRole ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

type OrgWebhook = {
  id: string
  url: string
  events: string[]
  status: string
}

function WebhooksSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<{ webhooks?: OrgWebhook[] }>(
    "/api/settings/webhooks",
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const [addDialog, setAddDialog] = useState(false)
  const [newUrl, setNewUrl] = useState("")
  const [selectedEvents, setSelectedEvents] = useState<string[]>([])
  const [isAdding, setIsAdding] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const webhooks = data?.webhooks ?? []

  const availableEvents = [
    "workflow.completed",
    "workflow.failed",
    "run.started",
    "run.failed",
    "run.completed",
    "approval.pending",
    "approval.completed",
    "approval.requested",
  ]

  const handleAddWebhook = async () => {
    setIsAdding(true)
    try {
      await settingsApi.createWebhook({ url: newUrl.trim(), events: selectedEvents, status: "active" })
      toast.success("Webhook added")
      setNewUrl("")
      setSelectedEvents([])
      setAddDialog(false)
      await mutate()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to add webhook"
      toast.error(message)
    } finally {
      setIsAdding(false)
    }
  }

  const handleDeleteWebhook = async (id: string) => {
    if (!confirm("Remove this webhook?")) return
    setDeletingId(id)
    try {
      await settingsApi.deleteWebhook(id)
      toast.success("Webhook removed")
      await mutate()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to remove webhook"
      toast.error(message)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading webhooks…
        </div>
      ) : error ? (
        <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">
          Could not load webhooks. Refresh and try again.
        </div>
      ) : webhooks.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card/50 p-8 text-center">
          <Webhook className="mx-auto mb-3 h-8 w-8 text-muted-foreground/60" />
          <p className="text-sm font-medium text-foreground">No webhooks configured yet</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Add an outbound endpoint to receive workflow and approval events for this organization.
          </p>
        </div>
      ) : (
        webhooks.map((webhook) => (
          <div key={webhook.id} className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-start justify-between mb-2">
              <code className="text-xs font-mono text-foreground break-all">{webhook.url}</code>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-success/10 text-success">
                  {webhook.status || "active"}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0"
                  disabled={!isAdmin || deletingId === webhook.id}
                  onClick={() => handleDeleteWebhook(webhook.id)}
                >
                  {deletingId === webhook.id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <X className="h-3 w-3" />
                  )}
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {(webhook.events || []).map((event) => (
                <span key={event} className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                  {event}
                </span>
              ))}
            </div>
          </div>
        ))
      )}
      <Button size="sm" className="gap-2" disabled={!isAdmin} onClick={() => setAddDialog(true)}>
        <Webhook className="h-3.5 w-3.5" />
        Add Webhook
      </Button>

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
                          setSelectedEvents(selectedEvents.filter((name) => name !== event))
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

function AIModelsSettings({ isAdmin }: { isAdmin: boolean }) {
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
              {/* Two peer rows telling apart task types, so the categorical
                  --chart-* ramp rather than health tones (emerald here did not
                  mean "good"). */}
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-chart-4/10 text-chart-4">
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
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-chart-1/10 text-chart-1">
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

      <MemoryEntityEmbeddingsSettings isAdmin={isAdmin} />

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
  const [memberEmailByDept, setMemberEmailByDept] = useState<Record<string, string>>({})
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

  const handleInviteMember = async (departmentId: string) => {
    const email = (memberEmailByDept[departmentId] || "").trim()
    if (!email) {
      toast.error("Enter a member email")
      return
    }
    setIsSaving(true)
    try {
      await settingsApi.addDepartmentMember({ department_id: departmentId, user_email: email })
      toast.success("Lite seat assigned")
      setMemberEmailByDept((prev) => ({ ...prev, [departmentId]: "" }))
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to assign member")
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
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
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
              <Button
                size="sm"
                variant="secondary"
                disabled={!isAdmin || isSaving}
                onClick={() => handleInviteMember(department.id)}
              >
                Assign seat
              </Button>
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

function SoftUsageMeter({
  label,
  used,
  included,
  unit,
  hint,
  note,
}: {
  label: string
  used: number
  included?: number | null
  unit?: string
  hint?: string
  note?: string
}) {
  const hasLimit = typeof included === "number" && included > 0
  const pct = hasLimit ? Math.min(100, (used / included) * 100) : 0

  return (
    <div className="flex flex-col rounded-2xl border border-border/70 bg-card/80 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {hasLimit ? (
          <span className="text-xs tabular-nums text-muted-foreground">{Math.round(pct)}%</span>
        ) : null}
      </div>
      <div className="mb-3 flex items-baseline gap-1.5">
        <p className="text-2xl font-semibold tracking-tight tabular-nums text-foreground">
          {used.toLocaleString()}
        </p>
        {hasLimit ? (
          <p className="text-sm tabular-nums text-muted-foreground">
            / {included.toLocaleString()}
            {unit ? ` ${unit}` : ""}
          </p>
        ) : unit ? (
          <p className="text-sm text-muted-foreground">{unit}</p>
        ) : null}
      </div>
      {hasLimit ? (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted/80">
          <div
            className={cn("h-full rounded-full", pct >= 90 ? "bg-warning" : "bg-primary/70")}
            style={{ width: `${pct}%` }}
          />
        </div>
      ) : null}
      {note ? <p className="mt-2 text-[11px] font-medium text-warning">{note}</p> : null}
      {hint ? <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function BillingUsageSettings() {
  const { data, isLoading, mutate } = useSWR("/api/settings/billing-usage", apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 30000,
  })
  const usage = (data ?? {}) as BillingUsageResponse
  const totals = usage.totals ?? { outputs: 0, workflow_runs: 0, api_calls: 0, ai_tokens: 0, research_lookups: 0 }
  const showResearch = Boolean(usage.research_lookups_billing_visible)
  const researchUsed = totals.research_lookups ?? 0
  const researchIncluded = usage.included_research_lookups ?? 0
  const researchOverage = usage.overage_research_lookups ?? 0
  const outputOverageUsd = Number(usage.overage_cost_usd ?? 0)
  const researchOverageUsd = Number(usage.overage_research_cost_usd ?? 0)
  const totalEstimatedOverage = outputOverageUsd + (showResearch ? researchOverageUsd : 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Usage for the current billing cycle</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => mutate()}>
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <SoftUsageMeter
          label="Outputs"
          used={totals.outputs}
          included={usage.included_outputs}
          unit="outputs"
          note={
            usage.overage_outputs
              ? `${usage.overage_outputs} overage`
              : undefined
          }
        />
        <SoftUsageMeter label="Workflow Runs" used={totals.workflow_runs} unit="runs" />
        <SoftUsageMeter label="API Calls" used={totals.api_calls} unit="calls" />
        <SoftUsageMeter
          label="AI Credits"
          used={totals.ai_tokens}
          included={usage.ai_credits_included}
          unit="credits"
          hint="LLM tokens only — separate from Research Lookups"
        />
        {showResearch ? (
          <SoftUsageMeter
            label="Research Lookups"
            used={researchUsed}
            included={researchIncluded}
            unit="lookups"
            hint="Live internet research — billed separately from AI credits"
            note={
              researchOverage
                ? `${researchOverage} overage @ $${(usage.research_lookup_overage_rate_usd ?? 0.35).toFixed(2)}/lookup`
                : undefined
            }
          />
        ) : null}
      </div>

      <div className="rounded-2xl border border-border/70 bg-card/80 p-4">
        <p className="text-sm font-medium text-foreground">Estimated overage</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">${totalEstimatedOverage.toFixed(2)}</p>
        {showResearch && researchOverageUsd > 0 ? (
          <p className="mt-1 text-[11px] text-muted-foreground">
            Includes ${researchOverageUsd.toFixed(2)} research lookup overage
          </p>
        ) : null}
        {isLoading ? <p className="mt-2 text-xs text-muted-foreground">Loading usage…</p> : null}
      </div>
    </div>
  )
}

function SettingsContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const sectionParam = (searchParams.get("section") || "organization") as SettingsSectionId
  const [activeSection, setActiveSection] = useState<SettingsSectionId>(sectionParam)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const section = searchParams.get("section")
    if (section === "enterprise") {
      router.replace("/settings/enterprise")
      return
    }
    if (section === "federation") {
      router.replace("/settings/federation")
      return
    }
    if (section === "environments") {
      router.replace("/environments")
      return
    }
    if (section === "profile") {
      router.replace("/settings/profile")
      return
    }
    if (section === "organizations") {
      router.replace("/settings/organizations")
      return
    }
    if (section === "billing") {
      router.replace("/settings/billing")
      return
    }
    if (section === "approvals") {
      router.replace("/settings/approvals")
      return
    }
    if (section === "permissions") {
      router.replace("/settings/team/permissions")
      return
    }
    if (section === "audit") {
      router.replace("/audit")
      return
    }
    if (section) {
      setActiveSection(section as SettingsSectionId)
    }
  }, [searchParams, router])

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
  if (authLoading || adminLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const renderContent = () => {
    if (!canAccessSettingsSection(activeSection, isAdmin)) {
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
      case "ai-models": return <AIModelsSettings isAdmin={isAdmin} />
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
      case "webhooks": return <WebhooksSettings isAdmin={isAdmin} />
      case "billing":
      case "approvals":
      case "permissions":
      case "audit":
      case "enterprise":
      case "federation":
      case "environments":
      case "profile":
      case "organizations":
        return (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Opening…
          </div>
        )
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

  const handleSectionChange = (section: SettingsSectionId) => {
    const href = settingsHrefForSection(section)
    if (href.startsWith("/settings?") || href === "/settings") {
      setActiveSection(section)
      router.push(href)
      return
    }
    router.push(href)
  }

  return (
    <SettingsShell
      activeSection={activeSection}
      onSectionChange={handleSectionChange}
      isAdmin={isAdmin}
      mobileMenuOpen={mobileMenuOpen}
      onMobileMenuOpenChange={setMobileMenuOpen}
    >
      {renderContent()}
    </SettingsShell>
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
