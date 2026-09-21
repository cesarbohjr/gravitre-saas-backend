import { describe, expect, it } from "vitest"
import { NextRequest } from "next/server"

/**
 * Confirmed 2026-09-21: magic-link hash tokens on a protected redirect were lost
 * when /auth/callback issued a 302 to /auth/callback/complete (fragments are not
 * forwarded). The route must return an HTML handoff that keeps location.hash.
 */
describe("auth callback hash handoff", () => {
  it("returns HTML that preserves location.hash instead of a 302", async () => {
    const { GET } = await import("@/app/auth/callback/route")
    const req = new NextRequest("https://gravitre.app/auth/callback?next=/ai")
    const res = await GET(req)
    expect(res.status).toBe(200)
    expect(res.headers.get("content-type") || "").toContain("text/html")
    const body = await res.text()
    expect(body).toContain("location.hash")
    expect(body).toContain("/auth/callback/complete")
    expect(body).toContain("next=%2Fai")
    expect(res.headers.get("location")).toBeNull()
  })
})
