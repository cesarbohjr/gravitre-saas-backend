import { afterEach, describe, expect, it, vi } from "vitest"
import { GET } from "../../app/e2e/static/[...path]/route"

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

describe("companion app static preview", () => {
  it("returns 404 when compiled out of a normal production build", async () => {
    vi.stubEnv("GRAVITRE_STATIC_PREVIEW_ENABLED", "0")
    const response = await GET(new Request("http://localhost/e2e/static/extension/manifest.json"), {
      params: Promise.resolve({ path: ["extension", "manifest.json"] }),
    })
    expect(response.status).toBe(404)
  })

  it("serves extension files in an explicitly enabled E2E build", async () => {
    vi.stubEnv("GRAVITRE_STATIC_PREVIEW_ENABLED", "1")
    vi.stubEnv("PLAYWRIGHT_E2E", "1")
    const response = await GET(new Request("http://localhost/e2e/static/extension/manifest.json"), {
      params: Promise.resolve({ path: ["extension", "manifest.json"] }),
    })
    expect(response.status).toBe(200)
    expect((await response.json()).manifest_version).toBe(3)
    expect(response.headers.get("Cache-Control")).toBe("no-store")
  })

  it("still rejects traversal out of the companion directory", async () => {
    vi.stubEnv("GRAVITRE_STATIC_PREVIEW_ENABLED", "1")
    vi.stubEnv("PLAYWRIGHT_E2E", "1")
    const response = await GET(new Request("http://localhost/e2e/static/extension/file"), {
      params: Promise.resolve({ path: ["extension", "..", "web", "package.json"] }),
    })
    expect(response.status).toBe(404)
  })
})
