"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { Globe, Loader2, Lock, Shield } from "lucide-react"
import { toast } from "sonner"
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
import { ssoApi } from "@/lib/api"
import type { SSOConfiguration, SSOProviderType } from "@/types/api"

export function SecuritySettings() {
  const { data: ssoConfig, error, isLoading, mutate } = useSWR<SSOConfiguration | null>(
    "/api/auth/sso/config",
    () => ssoApi.getConfig(),
    { revalidateOnFocus: false },
  )
  const [ssoDialog, setSsoDialog] = useState(false)
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
    setProviderType(ssoConfig.provider_type)
    setEntityId(ssoConfig.saml_entity_id || "")
    setSsoUrl(ssoConfig.saml_sso_url || "")
    setOidcIssuer(ssoConfig.oidc_issuer || "")
    setOidcClientId(ssoConfig.oidc_client_id || "")
  }, [ssoConfig])

  const metadataUrl = (() => {
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").trim().replace(/\/$/, "")
    if (apiBase) return `${apiBase}/api/auth/sso/metadata`
    if (typeof window !== "undefined") return `${window.location.origin}/api/auth/sso/metadata`
    return "/api/auth/sso/metadata"
  })()

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
      await mutate()
      setSsoDialog(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save SSO configuration")
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
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to toggle SSO")
    } finally {
      setIsTogglingSso(false)
    }
  }

  const handleDeleteSso = async () => {
    if (!confirm("Delete the saved SSO configuration?")) return
    setIsDeletingSso(true)
    try {
      await ssoApi.deleteConfig()
      toast.success("SSO configuration deleted")
      await mutate()
      setSsoDialog(false)
      setEntityId("")
      setSsoUrl("")
      setCertificate("")
      setOidcIssuer("")
      setOidcClientId("")
      setOidcClientSecret("")
      setProviderType("saml")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete SSO configuration")
    } finally {
      setIsDeletingSso(false)
    }
  }

  const handleCopyMetadataUrl = async () => {
    try {
      await navigator.clipboard.writeText(metadataUrl)
      toast.success("SP metadata URL copied")
    } catch {
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
      if (!result.redirect_url) throw new Error("Missing redirect URL")
      window.location.href = result.redirect_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to initialize SSO login test")
      setIsTestingSso(false)
    }
  }

  return (
    <div className="space-y-6" aria-label="Security settings">
      {isLoading ? <p role="status" className="text-sm text-muted-foreground">Loading SSO configuration…</p> : null}
      {error ? (
        <div role="alert" className="space-y-3">
          <p className="text-sm">Could not load SSO configuration.</p>
          <Button variant="outline" className="min-h-11" onClick={() => void mutate()}>Retry SSO</Button>
        </div>
      ) : null}

      <section className="flex flex-col gap-3 border-b border-divide py-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <Lock className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">Single sign-on</p>
            <p className="text-xs text-muted-foreground">
              {ssoConfig?.provider_type
                ? `${ssoConfig.provider_type.toUpperCase()} configured ${ssoConfig.is_enabled ? "and enabled" : "but disabled"}`
                : "SAML or OIDC is not configured yet"}
            </p>
            <p className="mt-1 break-all font-mono text-[11px] text-muted-foreground">SP metadata: {metadataUrl}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="min-h-11" onClick={() => void handleCopyMetadataUrl()}>Copy metadata URL</Button>
          <Button variant="outline" className="min-h-11" onClick={() => void handleTestSsoLogin()} disabled={!ssoConfig?.is_enabled || isTestingSso}>
            {isTestingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : "Test SSO"}
          </Button>
          <Button variant="outline" className="min-h-11" onClick={() => setSsoDialog(true)}>Configure</Button>
          <Button className="min-h-11" variant={ssoConfig?.is_enabled ? "outline" : "default"} onClick={() => void handleToggleSso()} disabled={!ssoConfig || isTogglingSso}>
            {isTogglingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : ssoConfig?.is_enabled ? "Disable" : "Enable"}
          </Button>
        </div>
      </section>

      <section className="flex items-start gap-3 border-b border-divide py-3">
        <Shield className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium text-foreground">Two-factor authentication</p>
          <p className="text-xs text-muted-foreground">Organization-wide 2FA enforcement is not available from this settings surface.</p>
        </div>
      </section>

      <section className="flex items-start gap-3 border-b border-divide py-3">
        <Globe className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium text-foreground">IP allowlist</p>
          <p className="text-xs text-muted-foreground">IP restriction is not available from this settings surface.</p>
        </div>
      </section>

      <Dialog open={ssoDialog} onOpenChange={setSsoDialog}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Configure single sign-on</DialogTitle>
            <DialogDescription>Connect your identity provider. These fields save to the existing SSO configuration API.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label htmlFor="sso-provider" className="text-xs font-medium text-muted-foreground">Provider type</label>
              <select id="sso-provider" className="h-11 w-full rounded-md border border-border bg-secondary px-3 text-sm" value={providerType} onChange={(event) => setProviderType(event.target.value as SSOProviderType)}>
                <option value="saml">SAML 2.0</option>
                <option value="oidc">OpenID Connect</option>
              </select>
            </div>
            {providerType === "saml" ? (
              <>
                <div className="space-y-2">
                  <label htmlFor="sso-entity" className="text-xs font-medium text-muted-foreground">Entity ID</label>
                  <Input id="sso-entity" value={entityId} onChange={(event) => setEntityId(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="sso-url" className="text-xs font-medium text-muted-foreground">SSO URL</label>
                  <Input id="sso-url" value={ssoUrl} onChange={(event) => setSsoUrl(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="sso-cert" className="text-xs font-medium text-muted-foreground">X.509 certificate</label>
                  <textarea id="sso-cert" className="h-28 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm" value={certificate} onChange={(event) => setCertificate(event.target.value)} />
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <label htmlFor="oidc-issuer" className="text-xs font-medium text-muted-foreground">Issuer URL</label>
                  <Input id="oidc-issuer" value={oidcIssuer} onChange={(event) => setOidcIssuer(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="oidc-client" className="text-xs font-medium text-muted-foreground">Client ID</label>
                  <Input id="oidc-client" value={oidcClientId} onChange={(event) => setOidcClientId(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="oidc-secret" className="text-xs font-medium text-muted-foreground">Client secret</label>
                  <Input id="oidc-secret" type="password" value={oidcClientSecret} onChange={(event) => setOidcClientSecret(event.target.value)} className="min-h-11" />
                </div>
              </>
            )}
          </div>
          <DialogFooter className="flex-wrap gap-2">
            <Button variant="outline" className="min-h-11" onClick={() => setSsoDialog(false)}>Cancel</Button>
            <Button variant="outline" className="min-h-11" onClick={() => void handleDeleteSso()} disabled={!ssoConfig || isDeletingSso}>
              {isDeletingSso ? <Loader2 className="h-4 w-4 animate-spin" /> : "Delete"}
            </Button>
            <Button className="min-h-11" onClick={() => void handleSaveSso()} disabled={isSaving}>
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save configuration"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
