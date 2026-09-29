import { describe, expect, it } from "vitest"
import { ADMIN_SIDEBAR_NAV } from "@/components/gravitre/sidebar-nav-config"
import { ADMIN_APP_NAV_ITEMS } from "../../../../e2e/helpers/app-navigation-items"

describe("e2e sidebar crawler items", () => {
  it("match the admin sidebar config exactly", () => {
    const sidebar = ADMIN_SIDEBAR_NAV.flatMap((group) => group.items.map((item) => `${item.name} ${item.href}`))
    const crawler = ADMIN_APP_NAV_ITEMS.map((item) => `${item.name} ${item.href}`)
    expect(crawler).toEqual(sidebar)
  })
})
