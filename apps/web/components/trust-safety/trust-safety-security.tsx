"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "./overlays/toast"
import { ssoApi } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
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
} from "@/lib/settings-api/security"
import type { SSOConfiguration } from "@/types/api"
import { enterpriseApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { RESIDENCY_KEY, type ResidencyOverview } from "@/lib/settings-api/enterprise"
import type { EnterpriseSiemConfig } from "@/types/api"
import { Hero, Icon, Note, Pill, Switch, TONE } from "./ts-ui"
import { SsoDialog } from "./sso-dialog"
import { TrustSafetyResidency } from "./trust-safety-residency"
import { siemForwarding, TrustSafetySiem } from "./trust-safety-siem"

const SSO_STEPS = ["Add Gravitre to your IdP", "Paste your IdP metadata", "Test and enable"]

/**
 * Workspace security controls from /api/settings/security and SSO status from
 * /api/auth/sso/config. The page reads the score for the tab badge.
 */
export function useSecurityState() {
  const { isAdmin } = useOrgAdmin()
  // Residency and SIEM are admin-only endpoints.
  const residency = useSWR<ResidencyOverview>(isAdmin ? RESIDENCY_KEY : null, fetcher, { revalidateOnFocus: false })
  const siem = useSWR<EnterpriseSiemConfig>(isAdmin ? "enterprise-siem" : null, () => enterpriseApi.getSiem(), { revalidateOnFocus: false })
  const sso = useSWR<SSOConfiguration | null>(SSO_CONFIG_KEY, () => ssoApi.getConfig(), { revalidateOnFocus: false })
  const sec = useSWR(SECURITY_KEY, () => securityApi.get(), { revalidateOnFocus: false })
  const sp = useSWR(SSO_SP_KEY, () => securityApi.serviceProvider(), { revalidateOnFocus: false })
  const stage = ssoStage(sso.data, sso.error)
  const controls = sec.data?.security ?? null
  const posture = securityPosture({ ssoEnabled: stage === "enabled", controls })
  return { sso, sec, sp, residency, siem, stage, controls, score: posture.score, advice: posture.advice }
}

export type SecurityState = ReturnType<typeof useSecurityState>

export function TrustSafetySecurity({ state }: { state: SecurityState }) {
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const { sso, sec, sp, residency, siem, stage, controls, score, advice } = state
  const [busy, setBusy] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [ipDraft, setIpDraft] = useState("")
  const [copied, setCopied] = useState(false)

  const save = async (key: string, patch: SecurityControlsPatch, optimistic: SecurityControls) => {
    if (!isAdmin || !sec.data) return false
    setBusy(key)
    const previous = sec.data
    await sec.mutate({ security: optimistic }, { revalidate: false })
    try {
      await sec.mutate(await securityApi.update(patch), { revalidate: false })
      return true
    } catch (err) {
      await sec.mutate(previous, { revalidate: false })
      toast.error(err instanceof Error ? err.message : "Could not save the security setting")
      return false
    } finally {
      setBusy(null)
    }
  }

  const tfa = Boolean(controls?.requireTwoFactor)
  const ip = Boolean(controls?.ipAllowlist.enabled)
  const ranges = controls?.ipAllowlist.ranges ?? []
  const timeout: SessionTimeout = controls?.sessionTimeout ?? "never"
  const locked = !isAdmin || !controls

  const toggleTfa = () => controls && void save("tfa", { requireTwoFactor: !tfa }, { ...controls, requireTwoFactor: !tfa })
  const toggleIp = () => controls && void save("ip", { ipAllowlist: { enabled: !ip } }, { ...controls, ipAllowlist: { ...controls.ipAllowlist, enabled: !ip } })
  const setTimeoutValue = (next: SessionTimeout) => controls && void save("timeout", { sessionTimeout: next }, { ...controls, sessionTimeout: next })
  const addRange = async () => {
    if (!controls) return
    const check = validateIpRange(ipDraft)
    if (!check.ok) {
      toast.error(check.error)
      return
    }
    if (ranges.includes(check.value)) {
      toast.error(`${check.value} is already on the list.`)
      return
    }
    const next = [...ranges, check.value]
    if (await save("ip-ranges", { ipAllowlist: { ranges: next } }, { ...controls, ipAllowlist: { ...controls.ipAllowlist, ranges: next } })) setIpDraft("")
  }
  const removeRange = (range: string) => {
    if (!controls) return
    const next = ranges.filter((r) => r !== range)
    void save("ip-ranges", { ipAllowlist: { ranges: next } }, { ...controls, ipAllowlist: { ...controls.ipAllowlist, ranges: next } })
  }

  const ssoPill =
    stage === "enabled"
      ? { ...TONE.ok, label: "Enabled" }
      : stage === "setup"
        ? { ...TONE.warn, label: "Setting up" }
        : stage === "unavailable"
          ? { ...TONE.mute, label: "Not on this plan" }
          : { ...TONE.mute, label: "Not set up" }
  const ssoStep = stage === "enabled" ? 3 : stage === "setup" ? 2 : 0
  const metadataUrl = sp.data?.metadata_url ?? null

  const testSso = async () => {
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

  const enableSso = async () => {
    setBusy("sso-enable")
    try {
      await ssoApi.enable()
      await sso.mutate()
      toast.success("Single sign on is on", {
        description: "Sign in through your IdP once to check it works.",
        action: { label: "Test sign in", onClick: () => void testSso() },
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not enable single sign on")
    } finally {
      setBusy(null)
    }
  }

  const ssoAction = (cls: string) =>
    stage === "unavailable" ? (
      <Link href="/settings/billing" className={cls}>See plans</Link>
    ) : !isAdmin || sso.error ? null : stage === "setup" ? (
      <button type="button" className={cls} disabled={busy != null} onClick={() => void enableSso()}>Test and enable</button>
    ) : (
      <button type="button" className={cls} disabled={sso.isLoading} onClick={() => setDialogOpen(true)}>{stage === "enabled" ? "Manage" : "Configure"}</button>
    )

  const copyMeta = async () => {
    if (!metadataUrl) return
    try {
      await navigator.clipboard.writeText(metadataUrl)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error("Could not copy the metadata URL")
    }
  }

  const next =
    score >= 4 || !isAdmin || !controls
      ? null
      : !tfa
        ? <button type="button" className="ts-btn dark sm" disabled={busy != null} onClick={toggleTfa}>Turn on two factor</button>
        : stage !== "enabled"
          ? ssoAction("ts-btn dark sm")
          : !ip
            ? <button type="button" className="ts-btn dark sm" disabled={busy != null} onClick={toggleIp}>Turn on IP allowlist</button>
            : <button type="button" className="ts-btn dark sm" disabled={busy != null} onClick={() => setTimeoutValue("24h")}>Set a session timeout</button>

  const currentRegion = residency.data?.regions.find((r) => r.current)?.label ?? null
  const forwarding = siemForwarding(siem.data)

  return (
    <>
      <Hero
        art={isAdmin || adminLoading ? "security" : "access"}
        eyebrow="Security · posture"
        big={controls ? score : "–"}
        unit="of 4 controls on"
        bars={[0, 1, 2, 3].map((i) => i < score)}
        advice={controls ? advice : sec.error ? "Security settings could not be loaded." : "Loading security settings."}
        actions={next}
        tiles={[
          { value: tfa ? "Required" : "Off", label: "Two factor", tone: tfa ? "good" : undefined },
          { value: ssoPill.label, label: "Single sign on", tone: stage === "enabled" ? "good" : undefined },
          { value: currentRegion ?? "–", label: "Data region" },
          { value: !isAdmin || !siem.data ? "–" : forwarding ? "On" : "Off", label: "SIEM export", tone: forwarding ? "good" : undefined },
        ]}
      />
      <div className="ts-sechead">
        <span className="ts-eyebrow">Sign in and access</span>
        <span style={{ fontSize: 13, color: "#55564F" }}>How people prove who they are and where they can sign in from</span>
      </div>
      <section className="ts-card" style={{ overflow: "hidden" }}>
        <div className="ts-sec">
          <span className="ts-ico"><Icon name="key" /></span>
          <div style={{ flex: "1 1 260px", minWidth: 0 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ fontWeight: 600 }}>Single sign on</span>
              <Pill bg={ssoPill.bg} fg={ssoPill.fg} dot={ssoPill.dot}>{ssoPill.label}</Pill>
            </div>
            <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>SAML or OIDC through your identity provider</div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="ts-btn line sm" disabled={!metadataUrl} onClick={() => void copyMeta()}>
              <Icon name="copy" size={15} />
              {copied ? "Copied" : "Copy metadata URL"}
            </button>
            {stage === "setup" && isAdmin ? <button type="button" className="ts-btn line sm" onClick={() => setDialogOpen(true)}>Edit setup</button> : null}
            {ssoAction("ts-btn dark sm")}
          </div>
          <div className="ts-sub" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
            {SSO_STEPS.map((label, i) => {
              const done = i < ssoStep
              const cur = i === ssoStep && stage !== "enabled"
              return (
                <div key={label} style={{ display: "flex", gap: 10, alignItems: "center", border: `1px solid ${cur ? "#CFCFC8" : "#EFEFEA"}`, background: cur ? "#FFFFFF" : "#F7F7F4", borderRadius: 10, padding: "10px 12px", fontSize: 13 }}>
                  <span style={{ width: 22, height: 22, borderRadius: "50%", background: done ? "#0B8A5C" : cur ? "#141513" : "#8A8B85", color: "#FFFFFF", display: "grid", placeItems: "center", fontSize: 11, fontWeight: 700, flex: "0 0 auto" }}>
                    {done ? "✓" : i + 1}
                  </span>
                  {label}
                </div>
              )
            })}
          </div>
          <div className="ts-sub ts-mono" style={{ fontSize: 12, color: "#55564F", overflowWrap: "anywhere" }}>
            SP metadata: {metadataUrl ?? "https://gravitre.app/api/auth/sso/metadata"}
          </div>
        </div>
        <div className="ts-sec">
          <span className="ts-ico"><Icon name="shieldCheck" /></span>
          <div style={{ flex: "1 1 260px", minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>Require two factor authentication</div>
            <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>Everyone confirms sign in with an authenticator app</div>
          </div>
          <Switch on={tfa} label="Require two factor authentication" disabled={locked || busy != null} onToggle={toggleTfa} />
        </div>
        <div className="ts-sec">
          <span className="ts-ico"><Icon name="globe" /></span>
          <div style={{ flex: "1 1 260px", minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>IP allowlist</div>
            <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>Only allow sign in from these networks</div>
          </div>
          <Switch on={ip} label="IP allowlist" disabled={locked || busy != null} onToggle={toggleIp} />
          {ip ? (
            <div className="ts-sub">
              {ranges.map((r) => (
                <span key={r} className="ts-chip ts-mono" style={{ cursor: "default" }}>
                  {r}
                  {!locked ? (
                    <button type="button" aria-label={`Remove ${r}`} onClick={() => removeRange(r)} style={{ border: 0, background: "transparent", cursor: "pointer", padding: 0, color: "#8A8B85", display: "inline-flex" }}>
                      <Icon name="x" size={12} width={2.2} />
                    </button>
                  ) : null}
                </span>
              ))}
              {!locked ? (
                <>
                  <label className="ts-input" style={{ flex: "0 1 240px", minHeight: 36 }}>
                    <input
                      aria-label="Add IP range"
                      placeholder="Add a range, e.g. 10.0.0.0/24"
                      value={ipDraft}
                      onChange={(e) => setIpDraft(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") void addRange() }}
                    />
                  </label>
                  <button type="button" className="ts-btn line sm" disabled={busy != null} onClick={() => void addRange()}>Add</button>
                </>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="ts-sec">
          <span className="ts-ico"><Icon name="clock" /></span>
          <div style={{ flex: "1 1 260px", minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>Session timeout</div>
            <div style={{ fontSize: 13, color: "#55564F", marginTop: 2 }}>Sign people out after a period of inactivity</div>
          </div>
          <select className="ts-select sm" aria-label="Session timeout" value={timeout} disabled={locked || busy != null} onChange={(e) => setTimeoutValue(e.target.value as SessionTimeout)}>
            {SESSION_TIMEOUT_OPTIONS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
      </section>
      {controls && ((tfa && !controls.enforced.requireTwoFactor) || (ip && !controls.enforced.ipAllowlist) || (timeout !== "never" && !controls.enforced.sessionTimeout)) ? (
        <Note>Saved for this workspace. Sign in does not enforce these controls yet, so nobody is blocked today.</Note>
      ) : null}
      {isAdmin ? (
        <>
          <TrustSafetyResidency residency={residency} />
          <TrustSafetySiem siem={siem} />
        </>
      ) : null}
      <SsoDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        config={sso.data ?? null}
        serviceProvider={sp.data ?? null}
        onChanged={async () => { await sso.mutate() }}
        onTest={() => void testSso()}
        testing={busy === "sso-test"}
      />
    </>
  )
}
