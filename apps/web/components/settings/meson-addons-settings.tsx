"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Check, Info, Lock, Users } from "lucide-react"
import { toast } from "sonner"
import { apiFetch, fetcher as apiFetcher } from "@/lib/fetcher"
import { settingsApi } from "@/lib/api"
import { SETTINGS_TIER_SCOPE } from "@/lib/settings-sections"
import type { MesonAddon } from "@/types/api"
import "@/components/workspace/workspace.css"
import "./meson-addons.css"

type VoiceState = {
  enabled?: boolean
  plan_included?: boolean
  note?: string
  billing_href?: string
} | null

type MesonAddonsPayload = {
  addons?: MesonAddon[]
  monthly_total_usd?: number
  voice?: VoiceState
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })

function formatMonthly(value: unknown): string | null {
  const amount = Number(value)
  if (!Number.isFinite(amount) || amount < 0) return null
  return `${usd.format(amount)}/mo`
}

function StatePill({ on }: { on: boolean | null }) {
  if (on === null) return <span className="gv-pill neutral">Not reported</span>
  return on ? (
    <span className="gv-pill brand">
      <span className="gv-ping" style={{ width: 7, height: 7, background: "var(--gv-accent)" }} aria-hidden />
      On
    </span>
  ) : (
    <span className="gv-pill neutral">Off</span>
  )
}

/**
 * Settings > Meson Addons. Voice is plan-included (org toggle via
 * PATCH /api/settings/voice-access); "Available to add" lists only the
 * Stripe-wired, non-archived addons GET /api/settings/meson-addons returns.
 * Anyone can read the state; only owners and admins can change it.
 */
export function MesonAddonsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<MesonAddonsPayload>(
    "/api/settings/meson-addons",
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const [saving, setSaving] = useState<string | null>(null)
  const [justChanged, setJustChanged] = useState<string | null>(null)

  const addons = Array.isArray(data?.addons) ? data.addons : []
  const voice = data?.voice ?? null
  const voiceOn: boolean | null =
    voice && typeof voice.enabled === "boolean" ? voice.enabled : null
  const monthlyTotal = formatMonthly(data?.monthly_total_usd)
  const scope = SETTINGS_TIER_SCOPE.organization

  const handleVoiceToggle = async () => {
    if (!isAdmin || voiceOn === null || saving) return
    setSaving("voice")
    setJustChanged(null)
    try {
      const res = await apiFetch("/api/settings/voice-access", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ enabled: !voiceOn }),
      })
      if (!res.ok) throw new Error("voice toggle failed")
      toast.success(`Voice ${voiceOn ? "turned off" : "turned on"} for this organization`)
      setJustChanged("voice")
      await mutate()
    } catch {
      toast.error("Could not update voice access")
    } finally {
      setSaving(null)
    }
  }

  const handleAddonToggle = async (addon: MesonAddon) => {
    if (!isAdmin || saving) return
    setSaving(addon.code)
    setJustChanged(null)
    try {
      await settingsApi.toggleMesonAddon(addon.code, !addon.enabled)
      toast.success(`${addon.name} ${addon.enabled ? "turned off" : "turned on"}`)
      setJustChanged(addon.code)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update addon")
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="gv-ws ma-root" data-testid="meson-addons-settings">
      <div className="ma-inner">
        <nav aria-label="Breadcrumb" className="ma-crumbs">
          <Link href="/settings">Settings</Link>
          <span aria-hidden>/</span>
          <span>Organization</span>
        </nav>

        <section className="gv-card gv-rise ma-header">
          <div className="ma-header-copy">
            <h1>Meson Addons</h1>
            <p>Premium AI capabilities for your workspace. Turn them on or off for everyone at once.</p>
            <div className="ma-scope">
              <Users className="h-[18px] w-[18px]" aria-hidden />
              <span>
                <strong>{scope.label}.</strong> {scope.detail}
              </span>
            </div>
          </div>
          <div className="ma-header-art">
            {/* eslint-disable-next-line @next/next/no-img-element -- static decorative SVG */}
            <img
              src="/illustrations/header-empty-desk.svg"
              alt=""
              aria-hidden
              width={640}
              height={220}
              data-illustration="header-empty-desk"
            />
          </div>
        </section>

        {error && !data ? (
          <div className="gv-card ma-alert" role="alert" style={{ marginTop: 28 }}>
            <span>Could not load Meson addons.</span>
            <button type="button" className="gv-btn outline sm" onClick={() => void mutate()}>
              Retry Meson addons
            </button>
          </div>
        ) : null}

        <h2 className="ma-h2">Included in your plan</h2>
        {isLoading && !data ? (
          <article className="gv-card ma-addon" aria-busy="true">
            <div className="gv-skel" style={{ width: "30%" }} />
            <div className="gv-skel" style={{ width: "80%", marginTop: 14 }} />
          </article>
        ) : (
          <article className="gv-card ma-addon" aria-labelledby="ma-voice-title">
            <div className="ma-addon-row">
              <div className="ma-addon-main">
                <div className="ma-addon-title">
                  <h3 id="ma-voice-title">Internal voice</h3>
                  <span className="gv-pill neutral">Staff chat</span>
                  <StatePill on={voiceOn} />
                </div>
                <p className="ma-addon-desc">
                  Lets staff talk to your org AI in Gravitre chat, by voice or text. On by default.
                </p>
              </div>
              {voiceOn !== null ? (
                <button
                  type="button"
                  className="gv-switch"
                  role="switch"
                  aria-checked={voiceOn}
                  aria-labelledby="ma-voice-title"
                  disabled={!isAdmin || saving !== null}
                  onClick={() => void handleVoiceToggle()}
                >
                  <span className="k" />
                </button>
              ) : null}
            </div>
            <div className="ma-foot">
              <Info className="h-4 w-4" aria-hidden />
              <span>
                Not outbound phone calls. Calls to customers run through the Twilio and Vapi
                connectors. <Link href="/connectors">Open Connectors →</Link>
              </span>
            </div>
            {!isAdmin ? (
              <div className="ma-perm">
                <Lock className="h-3.5 w-3.5" aria-hidden />
                Only owners and admins can change this.
              </div>
            ) : null}
            {voiceOn === null && data ? (
              <div className="ma-perm">Voice settings are not available for this workspace yet.</div>
            ) : null}
            {justChanged === "voice" ? (
              <div className="gv-rise ma-saved" role="status">
                <Check className="h-3.5 w-3.5" strokeWidth={2.4} aria-hidden />
                Saved for everyone in this workspace
              </div>
            ) : null}
          </article>
        )}

        <h2 className="ma-h2">Available to add</h2>
        {isLoading && !data ? (
          <div className="gv-card ma-addon" aria-busy="true">
            <div className="gv-skel" style={{ width: "40%" }} />
          </div>
        ) : addons.length > 0 ? (
          <div>
            {monthlyTotal ? (
              <div className="ma-total">
                <span>Enabled addons total</span>
                <strong>{monthlyTotal}</strong>
              </div>
            ) : null}
            {addons.map((addon) => {
              const titleId = `ma-addon-${addon.code}`
              const price = formatMonthly(addon.monthly_price_usd)
              return (
                <article key={addon.code} className="gv-card ma-addon" aria-labelledby={titleId}>
                  <div className="ma-addon-row">
                    <div className="ma-addon-main">
                      <div className="ma-addon-title">
                        <h3 id={titleId}>{addon.name}</h3>
                        <StatePill on={Boolean(addon.enabled)} />
                      </div>
                      {addon.description ? <p className="ma-addon-desc">{addon.description}</p> : null}
                    </div>
                    <div className="ma-addon-side">
                      <button
                        type="button"
                        className="gv-switch"
                        role="switch"
                        aria-checked={Boolean(addon.enabled)}
                        aria-labelledby={titleId}
                        disabled={!isAdmin || saving !== null}
                        onClick={() => void handleAddonToggle(addon)}
                      >
                        <span className="k" />
                      </button>
                      <span className="ma-price">{price ?? "Price not reported"}</span>
                    </div>
                  </div>
                  {justChanged === addon.code ? (
                    <div className="gv-rise ma-saved" role="status">
                      <Check className="h-3.5 w-3.5" strokeWidth={2.4} aria-hidden />
                      Saved. Billing &amp; Plan shows the updated total.
                    </div>
                  ) : null}
                </article>
              )
            })}
            {!isAdmin ? (
              <div className="ma-perm">
                <Lock className="h-3.5 w-3.5" aria-hidden />
                Only owners and admins can turn addons on or off.
              </div>
            ) : null}
          </div>
        ) : data ? (
          <div className="gv-card ma-empty">
            {/* eslint-disable-next-line @next/next/no-img-element -- static decorative SVG */}
            <img
              src="/illustrations/moment-no-addons.svg"
              alt=""
              aria-hidden
              width={320}
              height={190}
              data-illustration="moment-no-addons"
            />
            <div className="ma-empty-title">No paid addons to add right now</div>
            <div className="ma-empty-copy">
              Voice is already part of your plan. New addons will show up here with their price
              before you turn them on.
            </div>
            <Link className="gv-btn outline" href="/settings/billing">
              View Billing &amp; Plan
            </Link>
          </div>
        ) : null}
      </div>
    </div>
  )
}
