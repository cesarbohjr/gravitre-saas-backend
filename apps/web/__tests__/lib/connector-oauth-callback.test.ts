import { describe, expect, it } from "vitest"
import { PRODUCTION_APP_URL } from "@/lib/public-urls"

describe("connector oauth callback routes", () => {
  it("documents canonical HubSpot redirect paths on the app domain", () => {
    expect(`${PRODUCTION_APP_URL}/api/connectors/oauth/hubspot/callback`).toBe(
      "https://gravitre.app/api/connectors/oauth/hubspot/callback",
    )
    expect(`${PRODUCTION_APP_URL}/api/auth/callback/hubspot`).toBe(
      "https://gravitre.app/api/auth/callback/hubspot",
    )
  })
})
