import { describe, expect, it } from "vitest"

import {
  DENIED_CONSENT,
  GRANTED_CONSENT,
  isConsentBannerRegion,
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
