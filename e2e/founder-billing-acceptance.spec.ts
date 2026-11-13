import { test, expect, type Page } from "@playwright/test"
import { execFileSync } from "node:child_process"
import fs from "node:fs"
import { loadBillingFixtures, loginWithPassword, setSelectedOrg } from "./helpers/auth"

const evidence: Record<string, unknown> = {}
async function api(page: Page, url: string, body?: object) {
  return page.evaluate(async ({ url, body }) => {
    if (!window.__gravitreApiFetch) throw new Error("Authenticated E2E helper required")
    const response = await window.__gravitreApiFetch(url, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {})
    return { status: response.status, body: await response.json() }
  }, { url, body })
}
function stripeProof(session?: string) {
  return JSON.parse(execFileSync(process.env.PYTHON || "python", ["scripts/verify-billing-sandbox-payment.py", ...(session ? ["--session", session] : [])], { encoding: "utf8" }))
}

test.afterAll(() => {
  fs.mkdirSync("test-results", { recursive: true })
  const summaryPath = "test-results/billing-acceptance-summary.json"
  const previous = fs.existsSync(summaryPath) ? JSON.parse(fs.readFileSync(summaryPath, "utf8")) : {}
  fs.writeFileSync(summaryPath, JSON.stringify({ ...previous, ...evidence }, null, 2))
})

test("signed-in organization owner cannot access founder data or write offers", async ({ page }) => {
  const fixtures = loadBillingFixtures()
  await loginWithPassword(page, fixtures.activeTrial.email, fixtures.activeTrial.password)
  await setSelectedOrg(page, fixtures.activeTrial.orgId)
  await page.goto("/admin/commercial")
  await expect(page.getByRole("heading", { name: "Platform admin access required", exact: true })).toBeVisible()
  for (const path of ["commercial-accounts", "billing-safety"]) {
    const response = await api(page, `/api/billing/admin/${path}`)
    expect(response.status).toBe(403)
  }
  expect((await api(page, "/api/billing/admin/promotional-offers", { org_id: fixtures.activeTrial.orgId, offer_type: "trial", trial_days: 30, max_promotion_value_cents: 7000 })).status).toBe(403)
  evidence.nonFounder = "403 read and write denial with genuine Supabase sign-in"
})

async function issueCappedTrial(page: Page) {
  const fixtures = loadBillingFixtures()
  if (!fixtures.founder || !fixtures.founderTrialCustomer) throw new Error("Isolated founder fixtures required")
  await loginWithPassword(page, fixtures.founder.email, fixtures.founder.password)
  await setSelectedOrg(page, fixtures.founder.orgId)
  await page.goto("/admin/commercial")
  await expect(page.getByRole("heading", { name: "Commercial accounts", exact: true })).toBeVisible()
  const accounts = await api(page, "/api/billing/admin/commercial-accounts")
  expect(accounts.status).toBe(200)
  expect(accounts.body.offers_enabled).toBe(true)
  expect((await api(page, "/api/billing/admin/billing-safety")).status).toBe(200)
  const grant = await api(page, "/api/billing/admin/promotional-offers", { org_id: fixtures.founderTrialCustomer.orgId, offer_type: "trial", trial_days: 30, max_promotion_value_cents: 7000 })
  expect(grant.status).toBe(200)
  await page.screenshot({ path: "test-results/founder-controls.png", fullPage: true })
  evidence.founder = "200 read and grant issuance with genuine Supabase sign-in"
  return { fixtures, grant }
}

test("founder can read controls and issue a capped trial", async ({ page }) => {
  const { grant } = await issueCappedTrial(page)
  expect((await api(page, `/api/billing/admin/promotional-offers/${grant.body.grant_id}/revoke`, { reason: "Completed isolated role acceptance" })).status).toBe(200)
})

test("customer completes real sandbox checkout and signed webhook persists subscription", async ({ page, context }) => {
  const { fixtures } = await issueCappedTrial(page)
  if (!fixtures.founderTrialCustomer) throw new Error("Isolated customer fixture required")
  await context.clearCookies()
  await page.evaluate(() => window.localStorage.clear())
  await page.goto("/login")
  await loginWithPassword(page, fixtures.founderTrialCustomer.email, fixtures.founderTrialCustomer.password)
  await setSelectedOrg(page, fixtures.founderTrialCustomer.orgId)
  const checkout = await api(page, "/api/billing/checkout", { plan_code: "node", billing_interval: "monthly" })
  expect(checkout.status).toBe(200)
  const checkoutUrl = checkout.body.checkout_url || checkout.body.url
  expect(new URL(checkoutUrl).hostname).toBe("checkout.stripe.com")
  const sessionId = checkoutUrl.match(/cs_test_[A-Za-z0-9]+/)?.[0]
  if (!sessionId) throw new Error("Stripe sandbox checkout session required")
  await page.goto(checkoutUrl)
  // Stripe Checkout sometimes renders the contact address as type=text.
  // Identify it by its email-specific attributes in all hosted frames.
  // Never fill an arbitrary textbox or bypass Stripe's customer identity.
  const emailCandidates = async () => {
    const matches = []
    for (const frame of page.frames()) {
      const field = frame.locator(
        'input:is([type="email"],[autocomplete="email"],[name="email"],[id="email"],[placeholder*="example.com"]):visible'
      )
      const count = await field.count()
      if (count === 1) matches.push(field)
      else if (count > 1) throw new Error("Ambiguous Stripe Checkout email fields")
    }
    return matches
  }
  await expect.poll(async () => (await emailCandidates()).length, {
    timeout: 30_000,
    message: "Stripe Checkout must expose exactly one email-identified input across frames",
  }).toBe(1)
  const [email] = await emailCandidates()
  await expect(email).toBeEditable()
  await email.fill(fixtures.founderTrialCustomer.email)
  await expect(email).toHaveValue(fixtures.founderTrialCustomer.email)
  // The actual Stripe Checkout failure screenshot shows card number, MM / YY,
  // and security code, but the page-level accessible textbox query sees none.
  // Stripe hosts card inputs in PCI-isolated frames. Discover a *unique visible*
  // field by its payment-specific input attributes across all frames, and fail
  // closed if it is missing or ambiguous; never simulate payment or skip fields.
  const stripeField = async (label: string, selector: string) => {
    let found: ReturnType<typeof page.locator> | undefined
    await expect.poll(async () => {
      const matches: ReturnType<typeof page.locator>[] = []
      for (const frame of page.frames()) {
        const candidate = frame.locator(selector)
        const count = await candidate.count()
        if (count > 1) throw new Error(`Ambiguous Stripe ${label} inputs within a frame`)
        if (count === 1) matches.push(candidate)
      }
      found = matches.length === 1 ? matches[0] : undefined
      return matches.length
    }, { timeout: 30_000, message: `Stripe Checkout must expose one visible ${label} input across frames` }).toBe(1)
    if (!found) throw new Error(`Missing Stripe ${label} input`)
    await expect(found).toBeEditable()
    return found
  }
  const card = await stripeField("card number",
    'input:is([autocomplete="cc-number"],[name="cardnumber"],[placeholder*="Card number" i],[aria-label*="Card number" i]):visible')
  await card.fill("4242424242424242")
  const expiry = await stripeField("expiry",
    'input:is([autocomplete="cc-exp"],[name="exp-date"],[placeholder*="MM / YY" i],[placeholder*="MM/YY" i],[aria-label*="expiration" i],[aria-label*="expiry" i]):visible')
  await expiry.fill("1230")
  const security = await stripeField("security code",
    'input:is([autocomplete="cc-csc"],[name="cvc"],[placeholder*="Security code" i],[placeholder*="CVC" i],[aria-label*="Security code" i]):visible')
  await security.fill("123")
  const name = await stripeField("cardholder name",
    'input:is([autocomplete="cc-name"],[name="billingName"],[placeholder*="First and last name" i],[placeholder*="Name on card" i],[aria-label*="Name on card" i]):visible')
  await name.fill("Sandbox Acceptance")
  const postal = await stripeField("postal code",
    'input:is([autocomplete="postal-code"],[name="postalCode"],[placeholder*="ZIP code" i],[placeholder*="Postal code" i],[aria-label*="ZIP code" i]):visible')
  await postal.fill("94107")
  // The post-submit failure screenshot shows an enabled Link opt-in and
  // "Your phone number is incomplete." Stripe keeps this checkbox in its
  // hosted form; the top-page role lookup silently missed it. Discover the
  // unique visible opt-in across Checkout frames, explicitly uncheck it, and
  // require the unchecked state before payment. Never fill a fabricated phone
  // number or bypass Stripe's real payment and webhook processing.
  const linkOptIns = async () => {
    const matches: ReturnType<typeof page.locator>[] = []
    for (const frame of page.frames()) {
      const named = frame.getByRole("checkbox", {
        name: /Save my information|Save my payment/i,
      })
      const field = await named.count() ? named : frame.locator('input[type="checkbox"]:visible')
      const count = await field.count()
      if (count > 1) throw new Error("Ambiguous Stripe Link opt-in fields")
      if (count === 1 && await field.isVisible()) matches.push(field)
    }
    return matches
  }
  await expect.poll(async () => (await linkOptIns()).length, {
    timeout: 30_000,
    message: "Exactly one visible Stripe Link opt-in must be available",
  }).toBe(1)
  const [saveWithLink] = await linkOptIns()
  await expect(saveWithLink).toBeEnabled()
  await saveWithLink.uncheck()
  await expect(saveWithLink).not.toBeChecked()
  // The previous failure artifact did not include the button in the 720px
  // viewport and its error-context.md contained no DOM snapshot. Inspect
  // rendered button metadata across Checkout frames, without copying inputs,
  // payment values, identity, cookies, tokens, or arbitrary page content.
  const submitCandidates = async () => {
    const matches: ReturnType<typeof page.locator>[] = []
    const diagnostics: Array<{ frame: number; buttons: Array<{ type: string; label: string; testid: string }> }> = []
    for (const [index, frame] of page.frames().entries()) {
      const buttons = await frame.locator('button:visible, input[type="submit"]:visible')
        .evaluateAll((els) => els.slice(0, 32).map((el) => ({
          type: el.getAttribute("type") || "",
          label: (el.getAttribute("aria-label") || el.textContent || "")
            .replace(/[^a-zA-Z0-9 $-]/g, " ").trim().slice(0, 80),
          testid: (el.getAttribute("data-testid") || "").slice(0, 80),
        })))
        .catch(() => [])
      diagnostics.push({ frame: index, buttons })
      // Stripe's card Checkout submit is part of a form. The semantic submit
      // attribute is stable across marketing-label changes and secure frames.
      const candidate = frame.locator(
        'button[type="submit"]:visible, input[type="submit"]:visible, button[data-testid="hosted-payment-submit-button"]:visible'
      )
      const count = await candidate.count()
      if (count > 1) throw new Error("Ambiguous Stripe checkout submit controls in one frame")
      if (count === 1) matches.push(candidate)
    }
    return { matches, diagnostics }
  }
  let checkoutSubmit: ReturnType<typeof page.locator> | undefined
  await expect.poll(async () => {
    const { matches, diagnostics } = await submitCandidates()
    if (matches.length !== 1) {
      fs.writeFileSync("test-results/stripe-submit-dom.json",
        JSON.stringify({ provenance: "hosted-checkout-button-only", candidates: diagnostics }, null, 2))
    }
    checkoutSubmit = matches.length === 1 ? matches[0] : undefined
    return matches.length
  }, {
    timeout: 30_000,
    message: "Stripe Checkout must expose exactly one visible form-submit control across frames",
  }).toBe(1)
  if (!checkoutSubmit) throw new Error("No unique Stripe Checkout submit control")
  await expect(checkoutSubmit).toBeEnabled()
  await checkoutSubmit.click()
  await expect(page).toHaveURL(/localhost:3000\/settings\/billing/, { timeout: 90_000 })
  await expect.poll(() => stripeProof(sessionId).checkout_status, { timeout: 45_000 }).toBe("complete")
  const proof = stripeProof(sessionId)
  expect(proof.livemode).toBe(false)
  expect(proof.subscription_status).toBe("trialing")
  expect(proof.invoice_status).toBe("paid")
  expect(proof.invoice_amount_paid).toBe(0)
  await expect.poll(() => stripeProof(sessionId).grant_status, { timeout: 45_000 }).toBe("redeemed")
  const persisted = stripeProof(sessionId)
  expect(persisted.subscription_persisted).toBe(true)
  expect(persisted.trial_has_only_licensed_items).toBe(true)
  evidence.checkout = persisted
  await expect.poll(async () => (await api(page, "/api/billing/status")).body.billingStatus, { timeout: 45_000 }).toBe("trialing")
  await page.reload()
  // The helper is installed again by the reloaded document; calling before it
  // hydrates races the reload.
  await page.waitForFunction(() => Boolean(window.__gravitreApiFetch))
  const invoices = await api(page, "/api/billing/invoices")
  expect(invoices.status).toBe(200)
  expect(invoices.body.invoices).toEqual(expect.arrayContaining([expect.objectContaining({ id: persisted.invoice_id, status: "paid", amount_cents: 0 })]))
  expect(persisted.invoice_number).toBeTruthy()
  await expect(page.getByRole("region", { name: "Invoices", exact: true }).getByText(persisted.invoice_number, { exact: true })).toBeVisible()
  await page.screenshot({ path: "test-results/customer-billing-invoice.png", fullPage: true })
  const pdfStatus = () => page.evaluate(async (invoiceId) => {
    if (!window.__gravitreApiFetch) throw new Error("Authenticated E2E helper required")
    const response = await window.__gravitreApiFetch(`/api/billing/invoices/${invoiceId}/pdf`)
    return response.status
  }, persisted.invoice_id)
  expect(await pdfStatus()).toBe(200)
  await context.clearCookies()
  await page.evaluate(() => window.localStorage.clear())
  await loginWithPassword(page, fixtures.activeTrial.email, fixtures.activeTrial.password)
  await setSelectedOrg(page, fixtures.activeTrial.orgId)
  await page.waitForFunction(() => Boolean(window.__gravitreApiFetch))
  expect(await pdfStatus()).toBe(404)
  evidence.invoice = { rendered: true, ownerPdfStatus: 200, otherOrganizationPdfStatus: 404 }
})

test("sandbox recurring invoice is genuinely paid and subscription cleaned up", async () => {
  const proof = stripeProof()
  expect(proof.livemode).toBe(false)
  expect(proof.invoice_status).toBe("paid")
  expect(proof.amount_paid).toBe(5900)
  evidence.paidInvoice = proof
})
