import { describe, expect, it } from "vitest"

import {
  applyTagGatewayGeoHeaders,
  buildTagGatewayUpstreamUrl,
} from "@/lib/marketing-gtg-proxy"

describe("buildTagGatewayUpstreamUrl", () => {
  it("preserves the /gtg prefix and healthy subpath", () => {
    const url = buildTagGatewayUpstreamUrl("", ["healthy"])
    expect(url.toString()).toBe("https://gtm-p9txqf82.fps.goog/gtg/healthy")
  })

  it("forwards validate_geo on the measurement root", () => {
    const url = buildTagGatewayUpstreamUrl("?validate_geo=healthy", null)
    expect(url.origin).toBe("https://gtm-p9txqf82.fps.goog")
    expect(url.pathname).toBe("/gtg/")
    expect(url.searchParams.get("validate_geo")).toBe("healthy")
  })

  it("forwards id for the GTM loader", () => {
    const url = buildTagGatewayUpstreamUrl("?id=GTM-P9TXQF82", [])
    expect(url.searchParams.get("id")).toBe("GTM-P9TXQF82")
  })
})

describe("applyTagGatewayGeoHeaders", () => {
  it("maps Vercel geo headers to X-Forwarded-*", () => {
    const inbound = new Headers({
      "x-vercel-ip-country": "us",
      "x-vercel-ip-country-region": "ca",
      "x-vercel-ip-city": "Los Angeles",
      "x-vercel-ip-latitude": "34.05",
      "x-vercel-ip-longitude": "-118.24",
    })
    const outbound = new Headers()
    applyTagGatewayGeoHeaders(inbound, outbound)
    expect(outbound.get("X-Forwarded-Country")).toBe("US")
    expect(outbound.get("X-Forwarded-Region")).toBe("CA")
    expect(outbound.get("X-Forwarded-CountryRegion")).toBe("US-CA")
    expect(outbound.get("X-Forwarded-Geolocation")).toBe(
      "latlong=34.05,-118.24;city=Los Angeles"
    )
  })
})
