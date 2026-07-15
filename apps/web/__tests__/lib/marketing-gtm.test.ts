import { describe, expect, it } from "vitest"

import {
  MARKETING_GTG_FPS_HOST,
  MARKETING_GTG_PATH,
  MARKETING_GTM_ID,
  MARKETING_GTM_NOSCRIPT_SRC,
  MARKETING_GTM_SCRIPT_SRC,
} from "@/lib/marketing-gtm"

describe("marketing GTM Tag Gateway config", () => {
  it("uses the marketing container id", () => {
    expect(MARKETING_GTM_ID).toBe("GTM-P9TXQF82")
  })

  it("points the live snippet at Google-hosted GTM", () => {
    expect(MARKETING_GTM_SCRIPT_SRC).toBe(
      "https://www.googletagmanager.com/gtm.js?id=GTM-P9TXQF82"
    )
    expect(MARKETING_GTM_NOSCRIPT_SRC).toBe(
      "https://www.googletagmanager.com/ns.html?id=GTM-P9TXQF82"
    )
  })

  it("reserves /gtg so it does not collide with /metrics", () => {
    expect(MARKETING_GTG_PATH).toBe("/gtg")
    expect(MARKETING_GTG_PATH).not.toBe("/metrics")
  })

  it("derives the lowercase FPS host from the container id", () => {
    expect(MARKETING_GTG_FPS_HOST).toBe("gtm-p9txqf82.fps.goog")
  })
})
