"use client"

import { useEffect, useState } from "react"
import { Copy, Download, Loader2 } from "lucide-react"
import { toast } from "@/components/agents/overlays/toast"
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
import { securityApi } from "@/lib/settings-api/security"
import type { SSOConfiguration, SSOProviderType } from "@/types/api"

async function copyText(value: string, what: string) {
  try {
    await navigator.clipboard.writeText(value)
    toast.success(`${what} copied`)
    return true
  } catch {
    toast.error(`Could not copy the ${what.toLowerCase()}`)
    return false
  }
}

function CopyRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all rounded bg-secondary px-3 py-2 text-xs">{value ?? "Loading"}</code>
        <Button
          variant="outline"
          className="min-h-11"
          aria-label={`Copy ${label}`}
          disabled={!value}
          onClick={() => value && void copyText(value, label)}
        >
          <Copy className="h-4 w-4" aria-hidden />
        </Button>
      </div>
    </div>
  )
}

/** The single sign on setup: provider, IdP details, save, enable/disable, test and delete. */
export function SsoDialog({
  open,
  onOpenChange,
  config,
  serviceProvider,
  onChanged,
  onTest,
  testing,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  config: SSOConfiguration | null
  serviceProvider: { metadata_url: string; entity_id: string; acs_url: string } | null
  onChanged: (message: string) => Promise<void>
  onTest: () => void
  testing: boolean
}) {
  const [providerType, setProviderType] = useState<SSOProviderType>("saml")
  const [entityId, setEntityId] = useState("")
  const [ssoUrl, setSsoUrl] = useState("")
  const [certificate, setCertificate] = useState("")
  const [oidcIssuer, setOidcIssuer] = useState("")
  const [oidcClientId, setOidcClientId] = useState("")
  const [oidcClientSecret, setOidcClientSecret] = useState("")
  const [busy, setBusy] = useState<"save" | "toggle" | "delete" | "download" | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!open) return
    setProviderType(config?.provider_type ?? "saml")
    setEntityId(config?.saml_entity_id || "")
    setSsoUrl(config?.saml_sso_url || "")
    setOidcIssuer(config?.oidc_issuer || "")
    setOidcClientId(config?.oidc_client_id || "")
    setCertificate("")
    setOidcClientSecret("")
    setConfirmDelete(false)
  }, [open, config])

  const handleSave = async () => {
    setBusy("save")
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
      toast.success("Single sign on details saved")
      await onChanged("Single sign on details saved")
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the single sign on details")
    } finally {
      setBusy(null)
    }
  }

  const handleToggle = async () => {
    setBusy("toggle")
    try {
      if (config?.is_enabled) {
        await ssoApi.disable()
        toast.success("Single sign on disabled")
        await onChanged("Single sign on disabled")
      } else {
        await ssoApi.enable()
        toast.success("Single sign on enabled")
        await onChanged("Single sign on enabled")
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not change single sign on")
    } finally {
      setBusy(null)
    }
  }

  const handleDelete = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    setBusy("delete")
    try {
      await ssoApi.deleteConfig()
      toast.success("Single sign on configuration deleted")
      await onChanged("Single sign on configuration deleted")
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete the single sign on configuration")
    } finally {
      setBusy(null)
      setConfirmDelete(false)
    }
  }

  const handleDownload = async () => {
    setBusy("download")
    try {
      const blob = await securityApi.downloadMetadata()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = "gravitre-sp-metadata.xml"
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not download the metadata")
    } finally {
      setBusy(null)
    }
  }

  const spin = <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden />

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Single sign on</DialogTitle>
          <DialogDescription>Connect your identity provider in three steps.</DialogDescription>
        </DialogHeader>
        <div className="space-y-5 py-2">
          <section className="space-y-3" aria-label="Add Gravitre to your IdP">
            <p className="text-sm font-medium">1. Add Gravitre to your IdP</p>
            <CopyRow label="Entity ID" value={serviceProvider?.entity_id ?? null} />
            <CopyRow label="Reply URL (ACS) or redirect URI" value={serviceProvider?.acs_url ?? null} />
            <CopyRow label="Metadata URL" value={serviceProvider?.metadata_url ?? null} />
            {config?.provider_type === "saml" ? (
              <Button variant="outline" className="min-h-11 gap-2" disabled={busy === "download"} onClick={() => void handleDownload()}>
                {busy === "download" ? spin : <Download className="h-4 w-4" aria-hidden />}
                Download metadata XML
              </Button>
            ) : (
              <p className="text-xs text-muted-foreground">
                The metadata file can be downloaded once SAML details are saved below. The metadata URL needs a signed in
                admin, so paste the entity ID and reply URL into your IdP.
              </p>
            )}
          </section>

          <section className="space-y-3" aria-label="Paste your IdP metadata">
            <p className="text-sm font-medium">2. Paste your IdP details</p>
            <div className="space-y-2">
              <label htmlFor="sso-provider" className="text-xs font-medium text-muted-foreground">
                Provider type
              </label>
              <select
                id="sso-provider"
                className="h-11 w-full rounded-md border border-border bg-secondary px-3 text-sm"
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
                  <label htmlFor="sso-entity" className="text-xs font-medium text-muted-foreground">
                    IdP entity ID
                  </label>
                  <Input id="sso-entity" value={entityId} onChange={(event) => setEntityId(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="sso-url" className="text-xs font-medium text-muted-foreground">
                    IdP sign in URL
                  </label>
                  <Input id="sso-url" value={ssoUrl} onChange={(event) => setSsoUrl(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="sso-cert" className="text-xs font-medium text-muted-foreground">
                    X.509 certificate{config?.provider_type === "saml" ? " (paste again to save changes)" : ""}
                  </label>
                  <textarea
                    id="sso-cert"
                    className="h-28 w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm"
                    value={certificate}
                    onChange={(event) => setCertificate(event.target.value)}
                  />
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <label htmlFor="oidc-issuer" className="text-xs font-medium text-muted-foreground">
                    Issuer URL
                  </label>
                  <Input id="oidc-issuer" value={oidcIssuer} onChange={(event) => setOidcIssuer(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="oidc-client" className="text-xs font-medium text-muted-foreground">
                    Client ID
                  </label>
                  <Input id="oidc-client" value={oidcClientId} onChange={(event) => setOidcClientId(event.target.value)} className="min-h-11" />
                </div>
                <div className="space-y-2">
                  <label htmlFor="oidc-secret" className="text-xs font-medium text-muted-foreground">
                    Client secret
                  </label>
                  <Input
                    id="oidc-secret"
                    type="password"
                    value={oidcClientSecret}
                    onChange={(event) => setOidcClientSecret(event.target.value)}
                    className="min-h-11"
                  />
                </div>
              </>
            )}
            <Button className="min-h-11" onClick={() => void handleSave()} disabled={busy === "save"}>
              {busy === "save" ? spin : "Save details"}
            </Button>
          </section>

          {config ? (
            <section className="space-y-3" aria-label="Test and enable">
              <p className="text-sm font-medium">3. Test and enable</p>
              <p className="text-xs text-muted-foreground">
                {config.is_enabled
                  ? "Single sign on is on. Test sign in sends you through your IdP and back."
                  : "Enable single sign on, then test sign in through your IdP."}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  className="min-h-11"
                  variant={config.is_enabled ? "outline" : "default"}
                  onClick={() => void handleToggle()}
                  disabled={busy === "toggle"}
                >
                  {busy === "toggle" ? spin : config.is_enabled ? "Disable" : "Enable"}
                </Button>
                <Button variant="outline" className="min-h-11" onClick={onTest} disabled={!config.is_enabled || testing}>
                  {testing ? spin : "Test sign in"}
                </Button>
              </div>
            </section>
          ) : null}
        </div>
        <DialogFooter className="flex-wrap gap-2">
          <Button variant="outline" className="min-h-11" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {config ? (
            <Button variant="outline" className="min-h-11 text-destructive" onClick={() => void handleDelete()} disabled={busy === "delete"}>
              {busy === "delete" ? spin : confirmDelete ? "Confirm delete" : "Delete configuration"}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
