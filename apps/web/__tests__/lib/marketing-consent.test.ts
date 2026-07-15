import { afterEach, describe, expect, it, vi } from "vitest"

import {
  DENIED_CONSENT,
  GRANTED_CONSENT,
  isConsentBannerRegion,
  updateGtagConsent,
} from "@/lib/marketing-consent"

describe("marketing consent regions", () => {
  it("includes EEA, UK, and CH", () => {
    expect(isConsentBannerRegion("DE")).toBe(true)
    expect(isConsentBannerRegion("gb")).toBe(true)
    expect(isConsentBannerRegion("CH")).toBe(true)
  })

  it("excludes non-banner regions", () => {
    expect(isConsentBannerRegion("US")).toBe(false)
    expect(isConsentBannerRegion("")).toBe(false)
    expect(isConsentBannerRegion(null)).toBe(false)
  })

  it("exposes consent mode v2 parameter sets", () => {
    expect(DENIED_CONSENT).toMatchObject({
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
      analytics_storage: "denied",
    })
    expect(GRANTED_CONSENT).toMatchObject({
      ad_storage: "granted",
      analytics_storage: "granted",
    })
  })
})

describe("updateGtagConsent", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    // @ts-expect-error test cleanup
    delete globalThis.window
  })

  it("calls gtag('consent','update', state)", () => {
    const gtag = vi.fn()
    vi.stubGlobal("window", {
      dataLayer: [],
      gtag,
    })

    updateGtagConsent(GRANTED_CONSENT)

    expect(gtag).toHaveBeenCalledWith("consent", "update", GRANTED_CONSENT)
  })

  it("installs a gtag stub that pushes Arguments, not a plain array", () => {
    const dataLayer: unknown[] = []
    vi.stubGlobal("window", { dataLayer })

    updateGtagConsent(DENIED_CONSENT)

    expect(typeof window.gtag).toBe("function")
    expect(dataLayer).toHaveLength(1)
    const entry = dataLayer[0] as IArguments
    expect(entry[0]).toBe("consent")
    expect(entry[1]).toBe("update")
    expect(entry[2]).toEqual(DENIED_CONSENT)
  })
})
