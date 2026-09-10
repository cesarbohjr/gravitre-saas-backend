import { beforeEach, describe, expect, it, vi } from "vitest"

/**
 * /api/ai/route-intent was an unauthenticated LLM proxy.
 *
 * Unlike its sibling assistant routes it does not forward to FastAPI -- it calls
 * generateText() in Next -- so nothing was checking a session. A live probe of
 * production returned 400 "Missing prompt" to an anonymous request, proving the
 * handler ran and would have billed a completion for any caller on the internet.
 *
 * These tests pin the order: no session means no model call, and the rejection has
 * to happen before the body is read, so a malformed or oversized payload cannot be
 * used to reach the model either.
 */

const getUser = vi.fn()
const generateText = vi.fn()

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseRouteClient: () => ({ auth: { getUser } }),
}))

vi.mock("ai", () => ({
  generateText: (...args: unknown[]) => generateText(...args),
  Output: { object: () => ({}) },
}))

function request(body: unknown): Request {
  return new Request("https://gravitre.app/api/ai/route-intent", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  })
}

describe("POST /api/ai/route-intent authentication", () => {
  beforeEach(() => {
    getUser.mockReset()
    generateText.mockReset()
    generateText.mockResolvedValue({
      experimental_output: { mode: "chat", confidence: 0.9, reason: "ok" },
    })
  })

  it("rejects an anonymous request with 401", async () => {
    getUser.mockResolvedValue({ data: { user: null } })
    const { POST } = await import("@/app/api/ai/route-intent/route")

    const res = await POST(request({ prompt: "find my marketing agent" }) as never)

    expect(res.status).toBe(401)
    await expect(res.json()).resolves.toEqual({ error: "Unauthorized" })
  })

  it("never reaches the model without a session", async () => {
    // The cost half of the bug: a 401 that still billed a completion would be no fix.
    getUser.mockResolvedValue({ data: { user: null } })
    const { POST } = await import("@/app/api/ai/route-intent/route")

    await POST(request({ prompt: "find my marketing agent" }) as never)

    expect(generateText).not.toHaveBeenCalled()
  })

  it("checks the session before parsing the body", async () => {
    // Production answered 400 "Missing prompt" anonymously, which is how we know
    // body validation ran first. An empty prompt must now read as 401, not 400.
    getUser.mockResolvedValue({ data: { user: null } })
    const { POST } = await import("@/app/api/ai/route-intent/route")

    const res = await POST(request({}) as never)

    expect(res.status).toBe(401)
    expect(generateText).not.toHaveBeenCalled()
  })

  it("still serves an authenticated caller", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } })
    const { POST } = await import("@/app/api/ai/route-intent/route")

    const res = await POST(request({ prompt: "find my marketing agent" }) as never)

    expect(res.status).toBe(200)
    expect(generateText).toHaveBeenCalledTimes(1)
  })

  it("still rejects an authenticated caller with no prompt", async () => {
    getUser.mockResolvedValue({ data: { user: { id: "user-1" } } })
    const { POST } = await import("@/app/api/ai/route-intent/route")

    const res = await POST(request({}) as never)

    expect(res.status).toBe(400)
    expect(generateText).not.toHaveBeenCalled()
  })
})
