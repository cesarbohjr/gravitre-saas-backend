// @vitest-environment jsdom
import { act } from "react"
import { createRoot } from "react-dom/client"
import { SWRConfig } from "swr"
import { describe, expect, it, vi } from "vitest"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { intelligenceApi, type IntelligencePageContextResponse } from "@/lib/api"

vi.mock("@/lib/api", () => ({ intelligenceApi: { pageContext: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("intelligence snapshot tenant isolation", () => {
  it("does not display the old tenant snapshot while the new tenant loads", async () => {
    const first = { snapshot: { generatedAt: "2026-10-19T23:00:00Z" }, qualityFlags: [] } as unknown as IntelligencePageContextResponse
    let resolveSecond!: (value: IntelligencePageContextResponse) => void
    vi.mocked(intelligenceApi.pageContext)
      .mockResolvedValueOnce(first)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))
    const cache = new Map()
    let latest: ReturnType<typeof useIntelligenceSnapshot> | undefined
    function Probe({ tenant }: { tenant: string }) {
      latest = useIntelligenceSnapshot({ swrKeySuffix: tenant })
      return null
    }
    const host = document.createElement("div")
    const root = createRoot(host)
    const render = (tenant: string) => root.render(
      <SWRConfig value={{ provider: () => cache, dedupingInterval: 0 }}><Probe tenant={tenant} /></SWRConfig>,
    )
    try {
      await act(async () => render("org-a"))
      await vi.waitFor(() => expect(latest?.data).toBe(first))
      await act(async () => render("org-b"))
      expect(latest?.data).toBeUndefined()
      expect(latest?.lastKnown).toBeUndefined()
      expect(latest?.loadState).toBe("LOADING")
      const second = { ...first, qualityFlags: ["PARTIAL_SNAPSHOT"] }
      await act(async () => resolveSecond(second))
      await vi.waitFor(() => expect(latest?.data).toBe(second))
    } finally {
      act(() => root.unmount())
    }
  })
})
