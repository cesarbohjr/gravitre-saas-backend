// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"
import { VendorTile } from "@/components/connectors/redesign/art"
import { providerLogoSrc, resolveProvider } from "@/lib/provider-registry"

function render(node: React.ReactElement) {
  const container = document.createElement("div")
  container.innerHTML = renderToStaticMarkup(node)
  return { container, unmount: () => undefined }
}

describe("connector logos", () => {
  it("shows the official mark on the Connectors tiles, not initials", () => {
    for (const vendor of ["hubspot", "google_search_console", "pipedrive", "apollo", "canva", "microsoft365", "zendesk", "gmail", "google_analytics"]) {
      const { container, unmount } = render(<VendorTile vendor={vendor} />)
      const tile = container.firstElementChild as HTMLElement
      expect(tile.className).toContain("brand")
      expect(tile.querySelector("img")?.getAttribute("src")).toBe(resolveProvider(vendor)?.src)
      expect(tile.textContent).toBe("")
      unmount()
    }
  })

  it("keeps the two-letter tile only where the registry has no licensed mark", () => {
    const { container } = render(<VendorTile vendor="fred" base="cno-tile" />)
    const tile = container.firstElementChild as HTMLElement
    expect(tile.className).toContain("mono")
    expect(tile.querySelector("img")).toBeNull()
    expect(tile.textContent).toHaveLength(2)
  })

  it("resolves the connector types the API reports", () => {
    expect(resolveProvider("search_console")?.id).toBe("google_search_console")
    expect(resolveProvider("zendesk_support")?.id).toBe("zendesk")
    expect(resolveProvider("m365")?.id).toBe("microsoft365")
    expect(providerLogoSrc("slack")).toBe(resolveProvider("slack")?.src)
    expect(providerLogoSrc("fred")).toBeUndefined()
  })
})
