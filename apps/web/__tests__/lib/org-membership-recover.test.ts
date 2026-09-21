/** @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from "vitest"

const ORG_STORAGE_KEY = "gravitre:selectedOrg"

describe("recoverSelectedOrgAfterMembershipDenied", () => {
  beforeEach(() => {
    vi.resetModules()
    window.localStorage.clear()
  })

  it("clears stale selected org and resolves a membership org", async () => {
    window.localStorage.setItem(
      ORG_STORAGE_KEY,
      JSON.stringify({ id: "org-stale", name: "Stale Workspace" }),
    )

    vi.doMock("@/lib/api", () => ({
      organizationsApi: {
        list: vi.fn().mockResolvedValue({
          organizations: [{ id: "org-real", name: "Cesar Workspace" }],
        }),
      },
      authApi: {
        me: vi.fn(),
      },
    }))

    const { getSelectedOrgFromStorage, recoverSelectedOrgAfterMembershipDenied } =
      await import("@/lib/org-context")

    const next = await recoverSelectedOrgAfterMembershipDenied()
    expect(next).toBe("org-real")
    expect(getSelectedOrgFromStorage()?.id).toBe("org-real")
  })
})
