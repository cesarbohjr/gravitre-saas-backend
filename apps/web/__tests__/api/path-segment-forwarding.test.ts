import { afterEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

/**
 * Decoded path segments were placed into backend URLs unencoded, so a "..%2F"
 * segment could reach other FastAPI paths. The OAuth callback now accepts only
 * slug provider names and the training proxy encodes each segment.
 */

const fetchMock = vi.fn(async () => new Response(null, { status: 302, headers: { location: "https://gravitre.app/connectors?oauth=success" } }))

afterEach(() => {
  fetchMock.mockClear()
  vi.unstubAllGlobals()
})

describe("connector OAuth callback", () => {
  it("refuses a provider that is not a slug, without calling the backend", async () => {
    vi.stubGlobal("fetch", fetchMock)
    const { completeConnectorOAuthCallback } = await import("@/lib/connector-oauth-callback")
    const res = await completeConnectorOAuthCallback(
      new NextRequest("https://gravitre.app/api/connectors/oauth/x/callback?code=1"),
      "../../admin/mcp/servers",
    )
    expect(fetchMock).not.toHaveBeenCalled()
    expect(res.headers.get("location")).toContain("oauth=error")
  })

  it("forwards a slug provider", async () => {
    vi.stubGlobal("fetch", fetchMock)
    const { completeConnectorOAuthCallback } = await import("@/lib/connector-oauth-callback")
    await completeConnectorOAuthCallback(
      new NextRequest("https://gravitre.app/api/connectors/oauth/hubspot/callback?code=1&state=s"),
      "hubspot",
    )
    const url = String((fetchMock.mock.calls[0] as unknown[])[0])
    expect(url).toMatch(/\/api\/connectors\/oauth\/hubspot\/callback\?/)
  })
})
