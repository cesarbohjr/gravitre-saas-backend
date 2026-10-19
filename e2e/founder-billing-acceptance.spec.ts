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
  fs.writeFileSync("test-results/billing-acceptance-summary.json", JSON.stringify(evidence, null, 2))
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
  // Stripe renders this required field asynchronously. Counting immediately
  // after navigation skipped it and left checkout blocked on REQUIRED.
  const email = page.getByRole("textbox", { name: "Email", exact: true })
  await expect(email).toBeVisible()
  await email.fill(fixtures.founderTrialCustomer.email)
  await page.getByRole("textbox", { name: /Card number/i }).fill("4242424242424242")
  await page.getByRole("textbox", { name: /Expiration|Expiry/i }).fill("1230")
  await page.getByRole("textbox", { name: /Security code|CVC/i }).fill("123")
  const name = page.getByLabel(/Cardholder name|Name on card|Full name/i)
  if (await name.count()) await name.fill("Sandbox Acceptance")
  const postal = page.getByLabel(/ZIP|Postal code/i)
  if (await postal.count()) await postal.fill("94107")
  // Exercise card checkout without enrolling in optional Link/SMS signup.
  const saveWithLink = page.getByRole("checkbox", { name: /Save my information|Save my payment/i })
  if (await saveWithLink.isVisible()) await saveWithLink.uncheck()
  await page.getByRole("button", { name: /Start trial|Subscribe|Start free trial/i }).click()
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
