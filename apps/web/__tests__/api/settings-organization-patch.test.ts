import { beforeEach, describe, expect, it, vi } from "vitest"
import { NextRequest } from "next/server"

/**
 * PATCH /api/settings/organization sent primary_domain, which is not a column of
 * organizations, so every save failed; and it wrote null for every field the
 * caller left out, so a partial save erased the name or logo.
 */

const update = vi.fn()

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseRouteClient: () => ({
    from: () => ({
      update: (patch: unknown) => {
        update(patch)
        const chain = {
          eq: () => chain,
          select: () => chain,
          single: async () => ({ data: { id: "org-1", name: "Acme" }, error: null }),
        }
        return chain
      },
    }),
  }),
  resolveOrgId: async () => "org-1",
}))

function patch(body: unknown) {
  return new NextRequest("https://gravitre.app/api/settings/organization", {
    method: "PATCH",
    headers: { authorization: "Bearer jwt", "content-type": "application/json" },
    body: JSON.stringify(body),
  })
}

describe("PATCH /api/settings/organization", () => {
  beforeEach(() => update.mockReset())

  it("sends only the fields provided and never primary_domain", async () => {
    const { PATCH } = await import("@/app/api/settings/organization/route")
    const res = await PATCH(patch({ name: "Acme", primaryDomain: "acme.com" }))
    expect(res.status).toBe(200)
    expect(update).toHaveBeenCalledWith({ name: "Acme" })
  })

  it("does not null the name when only the logo changes", async () => {
    const { PATCH } = await import("@/app/api/settings/organization/route")
    await PATCH(patch({ logoUrl: "https://cdn.example/logo.png" }))
    expect(update).toHaveBeenCalledWith({ logo_url: "https://cdn.example/logo.png" })
  })

  it("rejects an empty update", async () => {
    const { PATCH } = await import("@/app/api/settings/organization/route")
    const res = await PATCH(patch({ primaryDomain: "acme.com" }))
    expect(res.status).toBe(400)
    expect(update).not.toHaveBeenCalled()
  })
})
