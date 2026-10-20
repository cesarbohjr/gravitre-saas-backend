"use client"

import { useState } from "react"

const SSO_STEPS = [
  "Add Gravitre to your IdP",
  "Paste your IdP metadata",
  "Test and enable",
]

export function TrustSafetySecurity() {
  const [tfa, setTfa] = useState(true)
  const [ip, setIp] = useState(false)
  const [ips, setIps] = useState<string[]>([])
  const [ipDraft, setIpDraft] = useState("")
  const [timeout, setTimeout_] = useState("8h")
  const [ssoStep, setSsoStep] = useState(0)
  const [copied, setCopied] = useState(false)

  // Compute security score
  const score = [tfa, ip, ssoStep >= SSO_STEPS.length, timeout !== "never"].filter(Boolean).length
  const secBars = [
    { label: "Two-factor auth", on: tfa },
    { label: "IP allowlist", on: ip },
    { label: "SSO", on: ssoStep >= SSO_STEPS.length },
    { label: "Session timeout", on: timeout !== "never" },
  ]

  const scoreLabel = score === 4 ? "Excellent" : score === 3 ? "Good" : score === 2 ? "Fair" : "Weak"
  const scoreColor = score === 4 ? "#0B8A5C" : score === 3 ? "#19C37D" : score === 2 ? "#D08A00" : "#8A2530"

  const addIp = () => {
    const v = ipDraft.trim()
    if (v && !ips.includes(v)) setIps([...ips, v])
    setIpDraft("")
  }

  const copyMeta = () => {
    const meta = `https://gravitre.io/sso/metadata`
    navigator.clipboard.writeText(meta).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const ssoNext = () => {
    if (ssoStep < SSO_STEPS.length) setSsoStep(ssoStep + 1)
  }

  return (
    <div className="gv-rise" style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Hero ── */}
      <div className="gv-card gv-hero" style={{ padding: 28, display: "flex", gap: 24, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ flex: "1 1 280px" }}>
          <div className="gv-eyebrow" style={{ fontSize: 11, fontFamily: "'Geist Mono',monospace", letterSpacing: ".12em", textTransform: "uppercase", color: "#6A6B64", marginBottom: 6 }}>Security score</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 48, fontWeight: 700, letterSpacing: "-0.03em", color: scoreColor, lineHeight: 1 }}>{score}</span>
            <span style={{ fontSize: 22, color: "#6A6B64", fontWeight: 400 }}>/4</span>
            <span style={{ fontSize: 15, fontWeight: 600, color: scoreColor, marginLeft: 4 }}>{scoreLabel}</span>
          </div>
          <p style={{ margin: "10px 0 0", fontSize: 14, color: "#55564F", lineHeight: 1.5, maxWidth: 340 }}>
            Enable all four controls to reach Excellent status and unlock enterprise compliance reports.
          </p>
        </div>
        <div style={{ flex: "1 1 240px", display: "flex", flexDirection: "column", gap: 10 }}>
          {secBars.map((b) => (
            <div key={b.label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="gv-bar" style={{
                flex: 1, height: 8, borderRadius: 999,
                background: b.on ? "#0B8A5C" : "#E4E4DF",
                transition: "background .3s",
              }} />
              <span style={{ fontSize: 12, color: b.on ? "#0B8A5C" : "#8A8B85", fontWeight: b.on ? 600 : 400, minWidth: 120, textAlign: "left" }}>
                {b.label}
              </span>
              <span style={{ fontSize: 12, color: b.on ? "#0B8A5C" : "#8A8B85" }}>{b.on ? "✓" : "—"}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Controls card ── */}
      <div className="gv-card" style={{ overflow: "hidden" }}>

        {/* Two-factor auth */}
        <div className="gv-sec">
          <div className="gv-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="4.5" y="10" width="15" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#141513" }}>Two-factor authentication</div>
            <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Require all members to verify via authenticator app or SMS when signing in.</div>
          </div>
          <button
            type="button"
            className={`gv-sw${tfa ? " on" : ""}`}
            aria-pressed={tfa}
            aria-label="Toggle two-factor authentication"
            onClick={() => setTfa(!tfa)}
          />
        </div>

        {/* IP allowlist */}
        <div className="gv-sec">
          <div className="gv-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 3a12 12 0 0 1 0 18M12 3a12 12 0 0 0 0 18M3 12h18" /></svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#141513" }}>IP allowlist</div>
            <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Restrict access to specific IP ranges. Blocks all other addresses.</div>
          </div>
          <button
            type="button"
            className={`gv-sw${ip ? " on" : ""}`}
            aria-pressed={ip}
            aria-label="Toggle IP allowlist"
            onClick={() => setIp(!ip)}
          />
        </div>
        {ip && (
          <div className="gv-sub" style={{ margin: "0 20px 20px", marginLeft: 72 }}>
            <div style={{ display: "flex", gap: 8, width: "100%", maxWidth: 480 }}>
              <label className="gv-input" style={{ flex: 1 }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 3a12 12 0 0 1 0 18" /></svg>
                <input
                  type="text"
                  placeholder="192.168.1.0/24"
                  value={ipDraft}
                  onChange={e => setIpDraft(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") addIp() }}
                  aria-label="IP range"
                />
              </label>
              <button type="button" className="gv-btn line sm" onClick={addIp}>Add</button>
            </div>
            {ips.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, width: "100%" }}>
                {ips.map((r) => (
                  <span key={r} className="gv-chip on" style={{ gap: 8 }}>
                    {r}
                    <button
                      type="button"
                      style={{ border: 0, background: "none", cursor: "pointer", padding: 0, color: "inherit", lineHeight: 1, fontSize: 14 }}
                      aria-label={`Remove ${r}`}
                      onClick={() => setIps(ips.filter(x => x !== r))}
                    >×</button>
                  </span>
                ))}
              </div>
            )}
            {ips.length === 0 && (
              <p style={{ fontSize: 13, color: "#8A8B85", margin: "6px 0 0" }}>No IP ranges added yet. Add a CIDR range above.</p>
            )}
          </div>
        )}

        {/* Session timeout */}
        <div className="gv-sec">
          <div className="gv-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 3" /></svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#141513" }}>Session timeout</div>
            <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Automatically sign out inactive members after the selected period.</div>
          </div>
          <select
            className="gv-select sm"
            value={timeout}
            onChange={e => setTimeout_(e.target.value)}
            aria-label="Session timeout duration"
          >
            <option value="1h">1 hour</option>
            <option value="4h">4 hours</option>
            <option value="8h">8 hours</option>
            <option value="24h">24 hours</option>
            <option value="never">Never</option>
          </select>
        </div>

      </div>

      {/* ── SSO card ── */}
      <div className="gv-card" style={{ overflow: "hidden" }}>
        <div style={{ padding: "20px 20px 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div className="gv-ico" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c1-3.5 3.5-5.5 6.5-5.5s5.5 2 6.5 5.5" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c1.8.8 3 2.6 3.5 5.2" /></svg>
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#141513" }}>Single sign-on (SAML 2.0)</div>
              <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Connect your identity provider so members sign in with company credentials.</div>
            </div>
            {ssoStep >= SSO_STEPS.length && (
              <span className="gv-pill" style={{ marginLeft: "auto", background: "#EAF7F0", color: "#0B8A5C" }}>Enabled</span>
            )}
          </div>
        </div>

        {ssoStep < SSO_STEPS.length ? (
          <div style={{ padding: 20 }}>
            {/* Step indicator */}
            <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
              {SSO_STEPS.map((s, i) => (
                <div key={s} style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{
                    height: 4, borderRadius: 999,
                    background: i <= ssoStep ? "#0B8A5C" : "#E4E4DF",
                    transition: "background .3s",
                  }} />
                  <span style={{ fontSize: 12, color: i <= ssoStep ? "#0B8A5C" : "#8A8B85", fontWeight: i === ssoStep ? 600 : 400 }}>{s}</span>
                </div>
              ))}
            </div>

            {ssoStep === 0 && (
              <div className="gv-note" style={{ marginBottom: 16 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flex: "0 0 auto", marginTop: 2 }}><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8h.01" /></svg>
                <span>In your identity provider (Okta, Azure AD, Google Workspace, etc.), create a new SAML 2.0 app and add Gravitre as the service provider.</span>
              </div>
            )}
            {ssoStep === 1 && (
              <div style={{ marginBottom: 16, display: "flex", flexDirection: "column", gap: 8 }}>
                <div className="gv-note">
                  <span style={{ fontSize: 13, fontFamily: "'Geist Mono',monospace", color: "#141513", flex: 1, wordBreak: "break-all" }}>
                    https://gravitre.io/sso/metadata
                  </span>
                  <button type="button" className="gv-btn line sm" onClick={copyMeta} style={{ flexShrink: 0 }}>
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
                <p style={{ fontSize: 13, color: "#6A6B64", margin: 0 }}>Paste your IdP&apos;s XML metadata URL below:</p>
                <input type="url" className="gv-select" placeholder="https://yourcompany.okta.com/app/metadata.xml" style={{ width: "100%", maxWidth: 440 }} />
              </div>
            )}
            {ssoStep === 2 && (
              <div className="gv-note" style={{ marginBottom: 16 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ flex: "0 0 auto", marginTop: 2 }}><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
                <span>Configuration looks correct. Click &quot;Enable SSO&quot; to activate single sign-on for your workspace. Members will be redirected to your IdP on next login.</span>
              </div>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              {ssoStep > 0 && (
                <button type="button" className="gv-btn line sm" onClick={() => setSsoStep(ssoStep - 1)}>Back</button>
              )}
              <button type="button" className="gv-btn green sm" onClick={ssoNext}>
                {ssoStep === SSO_STEPS.length - 1 ? "Enable SSO" : "Next"}
              </button>
            </div>
          </div>
        ) : (
          <div className="gv-sec" style={{ borderTop: "1px solid #EFEFEA", margin: "0 20px", padding: "16px 0 20px" }}>
            <div className="gv-ico" aria-hidden="true" style={{ background: "#EAF7F0" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#141513" }}>SSO is active</div>
              <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Members sign in via your identity provider. Direct login is disabled.</div>
            </div>
            <button type="button" className="gv-btn danger sm" onClick={() => setSsoStep(0)}>Disable</button>
          </div>
        )}
      </div>
    </div>
  )
}
