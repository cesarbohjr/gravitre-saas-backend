import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

/** Regression guard: billing UI must not impersonate Stripe-owned payment details. */
describe("billing payment truth", () => {
  const source = readFileSync(resolve(process.cwd(), "app/(app)/settings/billing/page.tsx"), "utf8")

  it("does not display fabricated customer card or address", () => {
    expect(source).not.toContain("•••• •••• •••• 4242")
    expect(source).not.toContain("123 Market Street")
    expect(source).not.toContain("John Doe")
  })

  it("does not collect raw card numbers or CVC in a non-Stripe form", () => {
    expect(source).not.toContain('htmlFor="cardNumber"')
    expect(source).not.toContain('htmlFor="cvc"')
    expect(source).not.toContain("formatCardNumber")
  })

  it("opens a real backend-created billing portal for card and address updates", () => {
    expect(source).toContain("billingApi.createPortalSession()")
    expect(source).toContain("window.location.assign(response.portal_url)")
    expect(source).not.toContain("// Simulate API call")
  })
})
