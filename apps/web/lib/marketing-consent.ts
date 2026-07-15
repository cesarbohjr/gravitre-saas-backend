/**
 * Marketing-site Google Consent Mode (Advanced) helpers.
 * @see https://developers.google.com/tag-platform/security/guides/consent?consentmode=advanced
 */

export const MARKETING_CONSENT_STORAGE_KEY = "gravitre_marketing_consent_v1"

/** Regions where the consent banner is shown (EEA + UK + CH). ISO 3166-1 alpha-2. */
export const CONSENT_BANNER_REGIONS = [
  "AT",
  "BE",
  "BG",
  "HR",
  "CY",
  "CZ",
  "DK",
  "EE",
  "FI",
  "FR",
  "DE",
  "GR",
  "HU",
  "IS",
  "IE",
  "IT",
  "LV",
  "LI",
  "LT",
  "LU",
  "MT",
  "NL",
  "NO",
  "PL",
  "PT",
  "RO",
  "SK",
  "SI",
  "ES",
  "SE",
  "GB",
  "CH",
] as const

export type ConsentRegion = (typeof CONSENT_BANNER_REGIONS)[number]

export type ConsentValue = "granted" | "denied"

/** Consent Mode v2 parameters required for EEA traffic. */
export type MarketingConsentState = {
  ad_storage: ConsentValue
  ad_user_data: ConsentValue
  ad_personalization: ConsentValue
  analytics_storage: ConsentValue
}

export type StoredMarketingConsent = MarketingConsentState & {
  decidedAt: string
}

export const DENIED_CONSENT: MarketingConsentState = {
  ad_storage: "denied",
  ad_user_data: "denied",
  ad_personalization: "denied",
  analytics_storage: "denied",
}

export const GRANTED_CONSENT: MarketingConsentState = {
  ad_storage: "granted",
  ad_user_data: "granted",
  ad_personalization: "granted",
  analytics_storage: "granted",
}

export const OPEN_CONSENT_EVENT = "gravitre:open-consent"

export function isConsentBannerRegion(country: string | null | undefined): boolean {
  if (!country) return false
  return (CONSENT_BANNER_REGIONS as readonly string[]).includes(country.toUpperCase())
}

export function openMarketingConsentSettings(): void {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(OPEN_CONSENT_EVENT))
}

export function readStoredMarketingConsent(): StoredMarketingConsent | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(MARKETING_CONSENT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredMarketingConsent>
    if (
      !isConsentValue(parsed.ad_storage) ||
      !isConsentValue(parsed.ad_user_data) ||
      !isConsentValue(parsed.ad_personalization) ||
      !isConsentValue(parsed.analytics_storage)
    ) {
      return null
    }
    return {
      ad_storage: parsed.ad_storage,
      ad_user_data: parsed.ad_user_data,
      ad_personalization: parsed.ad_personalization,
      analytics_storage: parsed.analytics_storage,
      decidedAt: typeof parsed.decidedAt === "string" ? parsed.decidedAt : new Date().toISOString(),
    }
  } catch {
    return null
  }
}

export function persistMarketingConsent(state: MarketingConsentState): StoredMarketingConsent {
  const stored: StoredMarketingConsent = {
    ...state,
    decidedAt: new Date().toISOString(),
  }
  try {
    window.localStorage.setItem(MARKETING_CONSENT_STORAGE_KEY, JSON.stringify(stored))
  } catch {
    // Ignore quota / private mode failures; consent update still applies for this page.
  }
  return stored
}

export function updateGtagConsent(state: MarketingConsentState): void {
  if (typeof window === "undefined") return
  window.dataLayer = window.dataLayer || []
  // gtag must push the Arguments object — pushing a plain array is ignored by Consent Mode.
  if (typeof window.gtag !== "function") {
    // Match Google's stub: push the Arguments object (not a plain array).
    window.gtag = function gtag() {
      // eslint-disable-next-line prefer-rest-params
      window.dataLayer!.push(arguments)
    }
  }
  window.gtag("consent", "update", state)
}

function isConsentValue(value: unknown): value is ConsentValue {
  return value === "granted" || value === "denied"
}

declare global {
  interface Window {
    dataLayer?: unknown[]
    gtag?: (...args: unknown[]) => void
  }
}
