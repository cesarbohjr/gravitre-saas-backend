"use client"

/**
 * Enterprise > White label (design p18), wired to enterprise.branding
 * (GET/PUT /api/enterprise/branding): brand name (the notification email
 * sender name), custom domain with DNS verification, accent colour (the same
 * primaryColor the General page's accent writes), logo URL and the "Powered by"
 * footer. The live preview also pushes to EnterpriseBrandingProvider.
 */
import { useEffect, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Check, Copy, RotateCw, ShieldCheck } from "lucide-react"
import { enterpriseApi } from "@/lib/api"
import { useEnterpriseBranding } from "@/lib/enterprise-branding-context"
import type { EnterpriseBranding, EnterpriseDomainInstructions, EnterpriseDomainVerifyResult } from "@/types/api"
import { HEX_RE, isValidDomain } from "@/lib/settings-api/enterprise"
import { ACCENT_SWATCHES } from "./organization-settings"
import { SetError, SetNote, SetPill, SetSkeleton, SetSwitch } from "./settings-kit"

const FALLBACK_ACCENT = ACCENT_SWATCHES[0]?.hex ?? "#2E9E5B"

function readableOn(hex: string): string {
  const v = hex.replace("#", "")
  const full = v.length === 3 ? v.split("").map((c) => c + c).join("") : v
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b) > 0.5 ? "#141513" : "#ffffff"
}

function CopyCode({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <span style={{ display: "flex", gap: 6, alignItems: "center", minWidth: 0 }}>
      <code style={{ flex: 1 }}>{value}</code>
      <button
        type="button"
        className="gs-iconbtn"
        aria-label={`Copy ${label}`}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value)
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1500)
          } catch {
            toast.error("Could not copy")
          }
        }}
      >
        {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
      </button>
    </span>
  )
}

export function EnterpriseWhiteLabel({ isAdmin }: { isAdmin: boolean }) {
  const { setPreview, refresh } = useEnterpriseBranding()
  const { data, error, isLoading, mutate } = useSWR<EnterpriseBranding>("enterprise-branding-tab", () => enterpriseApi.getBranding(), {
    revalidateOnFocus: false,
  })

  const [brandName, setBrandName] = useState("")
  const [domain, setDomain] = useState("")
  const [accent, setAccent] = useState(FALLBACK_ACCENT)
  const [logoUrl, setLogoUrl] = useState("")
  const [hidePoweredBy, setHidePoweredBy] = useState(false)
  const [seed, setSeed] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [instructions, setInstructions] = useState<EnterpriseDomainInstructions | null>(null)
  const [loadingDns, setLoadingDns] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<EnterpriseDomainVerifyResult | null>(null)

  const nextSeed = data
    ? `${data.emailFromName ?? ""}|${data.customDomain ?? ""}|${data.primaryColor ?? ""}|${data.logoUrl ?? ""}|${data.hidePoweredBy}`
    : null
  if (nextSeed && nextSeed !== seed) {
    setSeed(nextSeed)
    setBrandName(data?.emailFromName ?? "")
    setDomain(data?.customDomain ?? "")
    setAccent(data?.primaryColor && HEX_RE.test(data.primaryColor) ? data.primaryColor.toUpperCase() : FALLBACK_ACCENT)
    setLogoUrl(data?.logoUrl ?? "")
    setHidePoweredBy(Boolean(data?.hidePoweredBy))
  }

  const colorValid = HEX_RE.test(accent)
  const domainValid = isValidDomain(domain)
  const logoValid = !logoUrl.trim() || /^https:\/\//i.test(logoUrl.trim())
  const verified = Boolean(data?.customDomainVerified)

  useEffect(() => {
    setPreview({
      logoUrl: logoValid ? logoUrl.trim() || null : null,
      primaryColor: colorValid ? accent : null,
      hidePoweredBy,
    })
    return () => setPreview(null)
  }, [logoUrl, logoValid, accent, colorValid, hidePoweredBy, setPreview])

  const dirty =
    data != null &&
    (brandName.trim() !== (data.emailFromName ?? "") ||
      domain.trim() !== (data.customDomain ?? "") ||
      accent.toUpperCase() !== (data.primaryColor ?? "").toUpperCase() ||
      logoUrl.trim() !== (data.logoUrl ?? "") ||
      hidePoweredBy !== Boolean(data.hidePoweredBy))

  const save = async () => {
    if (!isAdmin) return
    if (!colorValid || !domainValid || !logoValid) {
      toast.error("Fix the highlighted fields first")
      return
    }
    setSaving(true)
    try {
      const updated = await enterpriseApi.updateBranding({
        emailFromName: brandName.trim() || null,
        customDomain: domain.trim().toLowerCase() || null,
        primaryColor: accent.toUpperCase(),
        logoUrl: logoUrl.trim() || null,
        hidePoweredBy,
      })
      await mutate(updated, { revalidate: false })
      refresh()
      toast.success("White label saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save white label")
    } finally {
      setSaving(false)
    }
  }

  const loadDns = async () => {
    if (!isAdmin || !domain.trim() || !domainValid) return
    setLoadingDns(true)
    setVerifyResult(null)
    try {
      await enterpriseApi.updateBranding({ customDomain: domain.trim().toLowerCase() })
      setInstructions(await enterpriseApi.getDomainInstructions())
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not load DNS records")
    } finally {
      setLoadingDns(false)
    }
  }

  const verify = async () => {
    setVerifying(true)
    try {
      const result = await enterpriseApi.verifyDomain()
      setVerifyResult(result)
      if (result.verified) {
        toast.success("Domain verified")
        await mutate()
        refresh()
      } else {
        toast.error("Not verified yet. Check your DNS records.")
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verification failed")
    } finally {
      setVerifying(false)
    }
  }

  if (error && !data) {
    return (
      <section className="gs-card">
        <SetError message="White label settings did not load." onRetry={() => void mutate()} />
      </section>
    )
  }
  if (isLoading || !data) {
    return (
      <section className="gs-card">
        <SetSkeleton rows={4} label="Loading white label" />
      </section>
    )
  }

  const swatches = ACCENT_SWATCHES.some((s) => s.hex.toUpperCase() === accent.toUpperCase())
    ? ACCENT_SWATCHES
    : [...ACCENT_SWATCHES, ...(colorValid ? [{ name: "Custom", hex: accent.toUpperCase() }] : [])]
  const failedChecks = verifyResult && !verifyResult.verified ? (["cname", "txt"] as const).filter((k) => verifyResult.checks[k] && !verifyResult.checks[k]?.ok) : []

  return (
    <>
      <section className="gs-card" style={{ padding: 20 }}>
        <div className="gs-grid-fields" style={{ gap: 16 }}>
          <label className="gs-field">
            Brand name
            <input
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Your company"
              maxLength={80}
              disabled={!isAdmin}
            />
            <span className="hint">Shown as the sender name on notification emails.</span>
          </label>
          <label className="gs-field">
            Custom domain
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="ai.yourcompany.com"
              disabled={!isAdmin || verified}
              aria-invalid={!domainValid}
              inputMode="url"
              autoCapitalize="none"
            />
            {!domainValid ? (
              <span className="ent-field-err">Enter a host name like ai.yourcompany.com</span>
            ) : verified ? (
              <span className="hint" style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                <ShieldCheck size={13} aria-hidden /> Verified
              </span>
            ) : null}
          </label>
          <div className="gs-field">
            <span id="ent-accent-label">Accent color</span>
            <div className="ent-swatches" role="group" aria-labelledby="ent-accent-label">
              {swatches.map((swatch) => (
                <button
                  key={swatch.hex}
                  type="button"
                  className="ent-swatch"
                  aria-label={`Color ${swatch.name}`}
                  aria-pressed={accent.toUpperCase() === swatch.hex.toUpperCase()}
                  disabled={!isAdmin}
                  style={{ background: swatch.hex }}
                  onClick={() => setAccent(swatch.hex.toUpperCase())}
                />
              ))}
            </div>
            <div className="ent-hex">
              <input
                aria-label="Accent hex code"
                value={accent}
                onChange={(e) => setAccent(e.target.value.toUpperCase())}
                disabled={!isAdmin}
                aria-invalid={!colorValid}
                style={{ maxWidth: 130 }}
              />
            </div>
            {!colorValid ? <span className="ent-field-err">Enter a hex color like #2E9E5B</span> : null}
          </div>
          <div className="gs-field">
            Preview
            <div className="ent-preview" aria-label="Branding preview">
              <span className="chip" style={{ background: colorValid ? accent : FALLBACK_ACCENT }}>
                {logoUrl.trim() && logoValid ? (
                  // eslint-disable-next-line @next/next/no-img-element -- admin supplied logo URL preview
                  <img src={logoUrl.trim()} alt="" />
                ) : null}
              </span>
              <span className="name">{brandName.trim() || "Your workspace"}</span>
              <span
                className="btn"
                style={{ background: colorValid ? accent : FALLBACK_ACCENT, color: readableOn(colorValid ? accent : FALLBACK_ACCENT) }}
              >
                Button
              </span>
            </div>
            <span className="hint">Preview shows unsaved changes. Save to apply them for everyone.</span>
          </div>
          <label className="gs-field">
            Logo URL
            <input
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://cdn.yourcompany.com/logo.svg"
              disabled={!isAdmin}
              aria-invalid={!logoValid}
              inputMode="url"
            />
            {!logoValid ? <span className="ent-field-err">Use an https link to a hosted image</span> : null}
          </label>
          <div className="gs-field">
            Powered by footer
            <span style={{ display: "flex", gap: 10, alignItems: "center", minHeight: 44 }}>
              <SetSwitch
                checked={hidePoweredBy}
                onChange={setHidePoweredBy}
                label="Hide Powered by Gravitre"
                disabled={!isAdmin}
              />
              <span style={{ color: "var(--gs-ink-2)" }}>Hide &ldquo;Powered by Gravitre&rdquo;</span>
            </span>
          </div>
        </div>
        {isAdmin ? (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
            <button
              type="button"
              className="gs-btn dark sm"
              disabled={saving || !dirty || !colorValid || !domainValid || !logoValid}
              onClick={() => void save()}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        ) : null}
      </section>

      {data.customDomain && !verified ? (
        <section className="gs-card ent-card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <h3>Verify {data.customDomain}</h3>
            <SetPill tone="amber">Not verified</SetPill>
          </div>
          <p className="ent-card-sub">Add the DNS records at your DNS provider, then verify. Changes can take a few minutes.</p>
          <div className="ent-actions">
            <button type="button" className="gs-btn line sm" disabled={!isAdmin || loadingDns || !domainValid} onClick={() => void loadDns()}>
              {loadingDns ? "Loading…" : "Get DNS records"}
            </button>
            {instructions ? (
              <button type="button" className="gs-btn dark sm" disabled={!isAdmin || verifying} onClick={() => void verify()}>
                <RotateCw size={14} className={verifying ? "animate-spin" : undefined} aria-hidden />
                {verifying ? "Verifying…" : "Verify domain"}
              </button>
            ) : null}
          </div>
          {instructions?.records?.length ? (
            <div className="ent-dns" style={{ marginTop: 12 }}>
              {instructions.records.map((record, i) => (
                <div key={`${record.type}-${i}`} className="ent-dns-row">
                  <SetPill>{record.type}</SetPill>
                  <span>Host</span>
                  <CopyCode value={record.host} label="host" />
                  <span>Value</span>
                  <CopyCode value={record.value} label="value" />
                </div>
              ))}
            </div>
          ) : null}
          {failedChecks.length > 0 ? (
            <div style={{ marginTop: 12 }}>
            <SetNote tone="red">
              {failedChecks.map((key) => {
                const check = verifyResult?.checks[key]
                return (
                  <div key={key}>
                    <b>{key.toUpperCase()}:</b>{" "}
                    {check?.message ||
                      `Expected ${check?.expected ?? "a record"}${check?.found ? `, found ${check.found}` : ", none found"}`}
                  </div>
                )
              })}
            </SetNote>
            </div>
          ) : null}
        </section>
      ) : null}

      {!isAdmin ? <SetNote>Only workspace admins can change white label settings.</SetNote> : null}
    </>
  )
}
