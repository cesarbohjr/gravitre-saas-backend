"use client"

import { useEffect, useState, type KeyboardEvent } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Check, Copy, Download, Globe, KeyRound, Loader2, ShieldCheck, Timer, X } from "lucide-react"
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
import {
  SECURITY_KEY,
  SESSION_TIMEOUT_OPTIONS,
  SSO_CONFIG_KEY,
  SSO_SP_KEY,
  securityApi,
  securityPosture,
  ssoStage,
  validateIpRange,
  type SecurityControls,
  type SecurityControlsPatch,
  type SessionTimeout,
  type SsoStage,
} from "@/lib/settings-api/security"
import type { SSOConfiguration, SSOProviderType } from "@/types/api"
import { SetArt, SetError, SetHeader, SetIco, SetNote, SetPill, SetSkeleton, SetSwitch } from "./settings-kit"
import "./security-settings.css"

const SSO_STEPS = ["Add Gravitre to your IdP", "Paste your IdP metadata", "Test and enable"]

const PILL: Record<SsoStage, { tone: "green" | "amber" | "neutral"; label: string }> = {
  enabled: { tone: "green", label: "Enabled" },
  setup: { tone: "amber", label: "Setting up" },
  none: { tone: "neutral", label: "Not configured" },
  unavailable: { tone: "neutral", label: "Not on your plan" },
}

/** Steps done for each stage: none = 0 (step 1 current), setup = 2 (step 3 current), enabled = all. */
const STEPS_DONE: Record<SsoStage, number> = { none: 0, setup: 2, enabled: 3, unavailable: 0 }

function NotEnforced() {
  return (
    <SetNote className="security-under-note">
      Saved for this workspace. Sign in does not enforce it yet, so nobody is blocked today. It takes effect when
      enforcement ships for this workspace.
    </SetNote>
  )
}

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

/**
 * Settings > Workspace > Security (design p09): posture, single sign on
 * (/api/auth/sso/*), and the workspace access controls saved in
 * organizations.settings via /api/settings/security. Everyone can read it;
 * only owners and admins can change it (the backend enforces the same).
 */
export function SecuritySettings({ isAdmin = false }: { isAdmin?: boolean }) {
  const sso = useSWR<SSOConfiguration | null>(SSO_CONFIG_KEY, () => ssoApi.getConfig(), { revalidateOnFocus: false })
  const sp = useSWR(SSO_SP_KEY, () => securityApi.serviceProvider(), { revalidateOnFocus: false })
  const sec = useSWR(SECURITY_KEY, () => securityApi.get(), { revalidateOnFocus: false })

  const stage = ssoStage(sso.data, sso.error)
  const ssoConfig = sso.data ?? null
  const controls = sec.data?.security ?? null
  const posture = securityPosture({ ssoEnabled: stage === "enabled", controls })
  const postureReady = !sec.isLoading && !sso.isLoading && Boolean(controls)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [announce, setAnnounce] = useState("")

  // ------------------------------------------------------------ SSO actions
  const metadataUrl = sp.data?.metadata_url ?? null

  const handleCopyMetadata = async () => {
    if (!metadataUrl) return
    if (await copyText(metadataUrl, "Metadata URL")) {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleTest = async () => {
    setBusy("sso-test")
    try {
      const result = await ssoApi.initLogin()
      if (!result.redirect_url) throw new Error("Missing redirect URL")
      window.location.href = result.redirect_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start the test sign in")
      setBusy(null)
    }
  }

  const handleEnable = async () => {
    setBusy("sso-enable")
    try {
      await ssoApi.enable()
      await sso.mutate()
      setAnnounce("Single sign on enabled")
      toast.success("Single sign on is on", {
        description: "Sign in through your IdP once to check it works.",
        action: { label: "Test sign in", onClick: () => void handleTest() },
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not enable single sign on")
    } finally {
      setBusy((current) => (current === "sso-enable" ? null : current))
    }
  }

  const ssoCta = () => {
    if (stage === "unavailable") {
      return (
        <Link href="/settings/billing" className="gs-btn dark sm">
          See plans
        </Link>
      )
    }
    if (!isAdmin || sso.error) return null
    if (stage === "setup") {
      return (
        <>
          <button type="button" className="gs-btn line sm" onClick={() => setDialogOpen(true)}>
            Edit setup
          </button>
          <button type="button" className="gs-btn dark sm" disabled={busy === "sso-enable"} onClick={() => void handleEnable()}>
            {busy === "sso-enable" ? <Loader2 size={15} className="animate-spin motion-reduce:animate-none" aria-hidden /> : null}
            Test and enable
          </button>
        </>
      )
    }
    return (
      <button type="button" className="gs-btn dark sm" disabled={sso.isLoading} onClick={() => setDialogOpen(true)}>
        {stage === "enabled" ? "Manage" : "Configure"}
      </button>
    )
  }

  // ------------------------------------------------------- control actions
  const save = async (key: string, patch: SecurityControlsPatch, optimistic: SecurityControls) => {
    if (!isAdmin || !sec.data) return false
    setBusy(key)
    const previous = sec.data
    await sec.mutate({ security: optimistic }, { revalidate: false })
    try {
      const result = await securityApi.update(patch)
      await sec.mutate(result, { revalidate: false })
      setAnnounce("Saved")
      return true
    } catch (err) {
      await sec.mutate(previous, { revalidate: false })
      toast.error(err instanceof Error ? err.message : "Could not save the security setting")
      return false
    } finally {
      setBusy(null)
    }
  }

  const [ipDraft, setIpDraft] = useState("")
  const [ipError, setIpError] = useState<string | null>(null)

  const addRange = async () => {
    if (!controls) return
    const check = validateIpRange(ipDraft)
    if (!check.ok) {
      setIpError(check.error)
      return
    }
    if (controls.ipAllowlist.ranges.includes(check.value)) {
      setIpError(`${check.value} is already on the list.`)
      return
    }
    setIpError(null)
    const ranges = [...controls.ipAllowlist.ranges, check.value]
    const ok = await save("ip-ranges", { ipAllowlist: { ranges } }, { ...controls, ipAllowlist: { ...controls.ipAllowlist, ranges } })
    if (ok) setIpDraft("")
  }

  const removeRange = (range: string) => {
    if (!controls) return
    const ranges = controls.ipAllowlist.ranges.filter((item) => item !== range)
    void save("ip-ranges", { ipAllowlist: { ranges } }, { ...controls, ipAllowlist: { ...controls.ipAllowlist, ranges } })
  }

  const onIpKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault()
      void addRange()
    }
  }

  const steps = STEPS_DONE[stage]

  return (
    <>
      <SetHeader
        crumb="Settings / Workspace"
        title="Security"
        description="Sign in, single sign on, access controls, where your data is stored and SIEM export."
      />
      <p className="sr-only" role="status" aria-live="polite">
        {announce}
      </p>

      <section className="gs-card round security-posture" aria-label="Security posture">
        <SetArt name="settings-security" ratio="320 / 190" />
        <div className="security-posture-body">
          <div className="gs-eyebrow">Security posture</div>
          {postureReady ? (
            <>
              <div className="security-score">
                <b>{posture.score}</b>
                <span>of 4 controls on</span>
              </div>
              <div className="security-bars" aria-hidden>
                {[0, 1, 2, 3].map((i) => (
                  <span
                    key={`${i}-${posture.score}`}
                    className={`gs-grow-x${i < posture.score ? " on" : ""}`}
                    style={{ animationDelay: `${i * 90}ms` }}
                  />
                ))}
              </div>
              <p className="security-advice">{posture.advice}</p>
            </>
          ) : sec.error ? (
            <p className="security-advice">The posture shows once the security settings load.</p>
          ) : (
            <SetSkeleton rows={2} label="Loading security posture" />
          )}
        </div>
      </section>

      {!isAdmin ? (
        <SetNote>Only owners and admins can change security settings. You can see what is set.</SetNote>
      ) : null}

      <section className="gs-card clip" aria-label="Access controls">
        <div className="gs-row-sec">
          <SetIco icon={KeyRound} />
          <div className="gs-what">
            <div className="security-title">
              <b>Single sign on</b>
              {sso.isLoading ? null : (
                <SetPill tone={PILL[stage].tone} dot>
                  {sso.error && stage !== "unavailable" ? "Unknown" : PILL[stage].label}
                </SetPill>
              )}
            </div>
            <span>SAML or OIDC through your identity provider</span>
          </div>
          <div className="security-actions">
            {stage !== "unavailable" ? (
              <button type="button" className="gs-btn line sm" disabled={!metadataUrl} onClick={() => void handleCopyMetadata()}>
                {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
                {copied ? "Copied" : "Copy metadata URL"}
              </button>
            ) : null}
            {ssoCta()}
          </div>
          <div className="gs-under">
            {sso.isLoading ? (
              <SetSkeleton rows={1} label="Loading single sign on" />
            ) : stage === "unavailable" ? (
              <p className="security-hint">Single sign on is part of the Command plan. Upgrade to connect your identity provider.</p>
            ) : sso.error ? (
              <SetError message="Could not load single sign on." onRetry={() => void sso.mutate()} />
            ) : (
              <>
                <ol className="security-steps" aria-label="Single sign on setup">
                  {SSO_STEPS.map((label, i) => {
                    const done = i < steps
                    const current = i === steps && stage !== "enabled"
                    return (
                      <li
                        key={label}
                        className={`security-step${done ? " done" : ""}${current ? " current" : ""}`}
                        aria-current={current ? "step" : undefined}
                      >
                        <span className="n" aria-hidden>
                          {done ? <Check size={12} /> : i + 1}
                        </span>
                        {label}
                        {done ? <span className="sr-only"> (done)</span> : null}
                      </li>
                    )
                  })}
                </ol>
                {ssoConfig ? (
                  <p className="security-hint">
                    {ssoConfig.provider_type === "oidc" ? "OpenID Connect" : "SAML 2.0"}
                    {ssoConfig.provider_type === "oidc" && ssoConfig.oidc_issuer ? ` · ${ssoConfig.oidc_issuer}` : ""}
                    {ssoConfig.provider_type !== "oidc" && ssoConfig.saml_entity_id ? ` · ${ssoConfig.saml_entity_id}` : ""}
                  </p>
                ) : null}
                <div className="gs-mono security-meta">
                  {metadataUrl ? `SP metadata: ${metadataUrl}` : sp.error ? "Could not load the SP metadata URL." : "Loading the SP metadata URL"}
                </div>
                {!isAdmin && stage !== "enabled" ? (
                  <p className="security-hint">An owner or admin can set up single sign on.</p>
                ) : null}
              </>
            )}
          </div>
        </div>

        {sec.isLoading && !controls ? (
          <div className="gs-row-sec">
            <SetSkeleton rows={3} label="Loading security controls" />
          </div>
        ) : !controls ? (
          <div className="gs-row-sec">
            <SetError message="Could not load the security controls." onRetry={() => void sec.mutate()} />
          </div>
        ) : (
          <>
            <div className="gs-row-sec">
              <SetIco icon={ShieldCheck} />
              <div className="gs-what">
                <b>Require two factor authentication</b>
                <span>Everyone confirms sign in with an authenticator app</span>
              </div>
              <SetSwitch
                label="Require two factor authentication"
                checked={controls.requireTwoFactor}
                disabled={!isAdmin || busy === "tfa"}
                onChange={(next) => void save("tfa", { requireTwoFactor: next }, { ...controls, requireTwoFactor: next })}
              />
              {controls.requireTwoFactor && !controls.enforced.requireTwoFactor ? (
                <div className="gs-under">
                  <NotEnforced />
                </div>
              ) : null}
            </div>

            <div className="gs-row-sec">
              <SetIco icon={Globe} />
              <div className="gs-what">
                <b>IP allowlist</b>
                <span>Only allow sign in from these networks</span>
              </div>
              <SetSwitch
                label="IP allowlist"
                checked={controls.ipAllowlist.enabled}
                disabled={!isAdmin || busy === "ip"}
                onChange={(next) =>
                  void save("ip", { ipAllowlist: { enabled: next } }, { ...controls, ipAllowlist: { ...controls.ipAllowlist, enabled: next } })
                }
              />
              {controls.ipAllowlist.enabled ? (
                <div className="gs-under">
                  <div className="security-ranges">
                    {controls.ipAllowlist.ranges.map((range) => (
                      <span key={range} className="gs-chip gs-mono">
                        {range}
                        {isAdmin ? (
                          <button
                            type="button"
                            aria-label={`Remove ${range}`}
                            disabled={busy === "ip-ranges"}
                            onClick={() => removeRange(range)}
                          >
                            <X size={13} aria-hidden />
                          </button>
                        ) : null}
                      </span>
                    ))}
                    {isAdmin ? (
                      <>
                        <label className="gs-input">
                          <input
                            aria-label="Add IP range"
                            aria-invalid={ipError ? true : undefined}
                            aria-describedby={ipError ? "security-ip-error" : undefined}
                            placeholder="Add a range, e.g. 10.0.0.0/24"
                            value={ipDraft}
                            onChange={(event) => {
                              setIpDraft(event.target.value)
                              setIpError(null)
                            }}
                            onKeyDown={onIpKey}
                          />
                        </label>
                        <button
                          type="button"
                          className="gs-btn line sm"
                          disabled={!ipDraft.trim() || busy === "ip-ranges"}
                          onClick={() => void addRange()}
                        >
                          Add
                        </button>
                      </>
                    ) : null}
                  </div>
                  {ipError ? (
                    <p id="security-ip-error" role="alert" className="security-error">
                      {ipError}
                    </p>
                  ) : null}
                  {controls.ipAllowlist.ranges.length === 0 ? (
                    <p className="security-hint">No ranges yet. Add the networks people sign in from.</p>
                  ) : null}
                  {!controls.enforced.ipAllowlist ? <NotEnforced /> : null}
                </div>
              ) : null}
            </div>

            <div className="gs-row-sec">
              <SetIco icon={Timer} />
              <div className="gs-what">
                <b>Session timeout</b>
                <span>Sign people out after a period of inactivity</span>
              </div>
              <select
                className="gs-select"
                aria-label="Session timeout"
                value={controls.sessionTimeout}
                disabled={!isAdmin || busy === "timeout"}
                onChange={(event) => {
                  const next = event.target.value as SessionTimeout
                  void save("timeout", { sessionTimeout: next }, { ...controls, sessionTimeout: next })
                }}
              >
                {SESSION_TIMEOUT_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              {controls.sessionTimeout !== "never" && !controls.enforced.sessionTimeout ? (
                <div className="gs-under">
                  <NotEnforced />
                </div>
              ) : null}
            </div>
          </>
        )}
      </section>

      <SsoDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        config={ssoConfig}
        serviceProvider={sp.data ?? null}
        onChanged={async (message) => {
          await sso.mutate()
          setAnnounce(message)
        }}
        onTest={() => void handleTest()}
        testing={busy === "sso-test"}
      />
    </>
  )
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

/** The existing SSO setup: provider, IdP details, save, enable/disable, test and delete. */
function SsoDialog({
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
