"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Cookie, Settings2, X } from "lucide-react"
import {
  DENIED_CONSENT,
  GRANTED_CONSENT,
  OPEN_CONSENT_EVENT,
  type MarketingConsentState,
  persistMarketingConsent,
  readStoredMarketingConsent,
  updateGtagConsent,
} from "@/lib/marketing-consent"
import { cn } from "@/lib/utils"

type Props = {
  /** ISO country from edge geo headers; banner only auto-opens in consent regions. */
  country: string
}

type Panel = "banner" | "preferences" | null

export function MarketingConsentBanner({ country }: Props) {
  const [panel, setPanel] = useState<Panel>(null)
  const [prefs, setPrefs] = useState<MarketingConsentState>(DENIED_CONSENT)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    const stored = readStoredMarketingConsent()
    if (stored) {
      setPrefs({
        ad_storage: stored.ad_storage,
        ad_user_data: stored.ad_user_data,
        ad_personalization: stored.ad_personalization,
        analytics_storage: stored.analytics_storage,
      })
      setPanel(null)
    } else {
      // Surface the consent banner to every first-time visitor, regardless of
      // region, until they make a choice. `country` still informs default
      // behaviour downstream but no longer gates whether the banner appears.
      setPanel("banner")
    }
    setHydrated(true)
  }, [country])

  useEffect(() => {
    const open = () => {
      const stored = readStoredMarketingConsent()
      if (stored) {
        setPrefs({
          ad_storage: stored.ad_storage,
          ad_user_data: stored.ad_user_data,
          ad_personalization: stored.ad_personalization,
          analytics_storage: stored.analytics_storage,
        })
      }
      setPanel("preferences")
    }
    window.addEventListener(OPEN_CONSENT_EVENT, open)
    return () => window.removeEventListener(OPEN_CONSENT_EVENT, open)
  }, [])

  const applyConsent = useCallback((state: MarketingConsentState) => {
    persistMarketingConsent(state)
    updateGtagConsent(state)
    setPrefs(state)
    setPanel(null)
  }, [])

  const acceptAll = () => applyConsent(GRANTED_CONSENT)
  const rejectNonEssential = () => applyConsent(DENIED_CONSENT)
  const savePreferences = () =>
    applyConsent({
      analytics_storage: prefs.analytics_storage,
      ad_storage: prefs.ad_storage,
      ad_user_data: prefs.ad_storage,
      ad_personalization: prefs.ad_storage,
    })

  if (!hydrated || panel === null) return null

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-[120] p-3 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="marketing-consent-title"
    >
      <div
        className={cn(
          "mx-auto max-w-3xl overflow-hidden rounded-2xl border border-border bg-card shadow-2xl shadow-foreground/10",
          panel === "preferences" && "max-w-lg",
        )}
      >
        {panel === "banner" ? (
          <div className="p-4 sm:p-5">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted text-foreground">
                <Cookie className="h-4 w-4" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <h2 id="marketing-consent-title" className="text-sm font-semibold text-foreground">
                  Cookies & measurement
                </h2>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                  We use cookies and similar technologies for analytics and advertising measurement.
                  You can accept all, reject non-essential cookies, or manage preferences. See our{" "}
                  <Link href="/privacy" className="font-medium text-foreground underline underline-offset-2">
                    Privacy Policy
                  </Link>
                  .
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setPanel("preferences")}
                className="inline-flex h-10 items-center justify-center gap-1.5 rounded-full px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                <Settings2 className="h-3.5 w-3.5" aria-hidden />
                Manage preferences
              </button>
              <button
                type="button"
                onClick={rejectNonEssential}
                className="inline-flex h-10 items-center justify-center rounded-full border border-border px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
              >
                Reject non-essential
              </button>
              <button
                type="button"
                onClick={acceptAll}
                className="inline-flex h-10 items-center justify-center rounded-full bg-foreground px-4 text-sm font-semibold text-white transition-colors hover:bg-foreground/90"
              >
                Accept all
              </button>
            </div>
          </div>
        ) : (
          <div className="p-4 sm:p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="marketing-consent-title" className="text-sm font-semibold text-foreground">
                  Cookie preferences
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Choose which categories Gravitre may use. Essential site operation never requires
                  this consent.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPanel(null)}
                className="grid h-8 w-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Close cookie preferences"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>

            <ul className="mt-4 space-y-3">
              <PreferenceRow
                title="Analytics"
                description="Helps us understand site usage and improve the product (analytics_storage)."
                checked={prefs.analytics_storage === "granted"}
                onChange={(checked) =>
                  setPrefs((current) => ({
                    ...current,
                    analytics_storage: checked ? "granted" : "denied",
                  }))
                }
              />
              <PreferenceRow
                title="Advertising"
                description="Supports ad measurement and personalization (ad_storage, ad_user_data, ad_personalization)."
                checked={prefs.ad_storage === "granted"}
                onChange={(checked) => {
                  const value = checked ? "granted" : "denied"
                  setPrefs((current) => ({
                    ...current,
                    ad_storage: value,
                    ad_user_data: value,
                    ad_personalization: value,
                  }))
                }}
              />
            </ul>

            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={rejectNonEssential}
                className="inline-flex h-10 items-center justify-center rounded-full border border-border px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
              >
                Reject all
              </button>
              <button
                type="button"
                onClick={savePreferences}
                className="inline-flex h-10 items-center justify-center rounded-full border border-border px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
              >
                Save preferences
              </button>
              <button
                type="button"
                onClick={acceptAll}
                className="inline-flex h-10 items-center justify-center rounded-full bg-foreground px-4 text-sm font-semibold text-white transition-colors hover:bg-foreground/90"
              >
                Accept all
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function PreferenceRow({
  title,
  description,
  checked,
  onChange,
}: {
  title: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <li className="flex items-start justify-between gap-4 rounded-xl border border-border bg-muted/50/80 px-3.5 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors",
          checked ? "bg-foreground" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-card shadow transition-transform",
            checked && "translate-x-5",
          )}
        />
      </button>
    </li>
  )
}
