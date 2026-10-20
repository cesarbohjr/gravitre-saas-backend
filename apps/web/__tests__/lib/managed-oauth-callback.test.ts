import { expect, it } from "vitest"
import { GET } from "@/app/api/connectors/oauth/callback/route"

it("relays success and denial query parameters unchanged to a fixed destination", () => {
  for (const query of ["?code=a%2Bb&state=s%26x&state=second", "?error=access_denied&state=abc"]) {
    const response = GET(new Request(`https://gravitre.app/api/connectors/oauth/callback${query}`))
    expect(response.status).toBe(308)
    expect(response.headers.get("location")).toBe(`https://api.nango.dev/oauth/callback${query}`)
    expect(response.headers.get("cache-control")).toBe("no-store")
    expect(response.headers.get("referrer-policy")).toBe("no-referrer")
  }
})

it("cannot be turned into an open redirect", () => {
  const response = GET(new Request("https://gravitre.app/api/connectors/oauth/callback?redirect_uri=https://attacker.com"))
  expect(new URL(response.headers.get("location")!).origin).toBe("https://api.nango.dev")
})
