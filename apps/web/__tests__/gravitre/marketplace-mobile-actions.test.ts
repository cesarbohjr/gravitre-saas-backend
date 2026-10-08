import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const slugPage = readFileSync(
  resolve(__dirname, "../../app/(app)/marketplace/assets/[slug]/page.tsx"),
  "utf8",
)

describe("marketplace pack detail mobile actions", () => {
  it("keeps uninstall available on the mobile action bar for authorized users", () => {
    expect(slugPage).toContain("marketplace-mobile-actions")
    expect(slugPage).toContain("handleUninstall")
    expect(slugPage).toContain("More asset actions")
    expect(slugPage).toContain("Uninstall")
  })

  it("sits above MobileBottomNav instead of covering it", () => {
    expect(slugPage).toContain("bottom-[calc(3.5rem+env(safe-area-inset-bottom))]")
    expect(slugPage).toContain("pb-[calc(12rem+env(safe-area-inset-bottom))]")
    expect(slugPage).not.toMatch(/marketplace-mobile-actions[\s\S]{0,200}bottom-0/)
  })
})
