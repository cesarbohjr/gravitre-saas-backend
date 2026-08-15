import { existsSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

const WEB_ROOT = join(process.cwd())

/** Billing mutations must proxy through Next.js BFF — direct FastAPI calls 404 when API_BASE is empty. */
const REQUIRED_BILLING_POST_ROUTES = [
  "app/api/billing/cancel/route.ts",
  "app/api/billing/reactivate/route.ts",
  "app/api/billing/portal/route.ts",
] as const

describe("billing BFF proxy routes", () => {
  it("includes cancel, reactivate, and portal POST handlers", () => {
    for (const routePath of REQUIRED_BILLING_POST_ROUTES) {
      expect(existsSync(join(WEB_ROOT, routePath))).toBe(true)
    }
  })

  it("exports shared authenticated billing POST proxy helper", () => {
    expect(existsSync(join(WEB_ROOT, "lib/billing-route-proxy.ts"))).toBe(true)
  })
})
