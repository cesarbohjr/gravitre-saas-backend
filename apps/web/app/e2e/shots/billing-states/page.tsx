"use client"

/**
 * Design-review capture surface for the consolidated Billing & Plan page.
 *
 * This renders the REAL BillingPage component rather than a copy of its markup.
 * Duplicating the card JSX here would let the comp drift from what ships and
 * turn the screenshots into decoration, so the page is imported as-is and fed
 * by the shots-layout fetch fixtures.
 *
 * Reachable only through the /e2e/shots harness, which 404s in production.
 */

import BillingPage from "@/app/settings/billing/page"

import { ShotAuthProvider } from "../shot-auth"

export default function BillingStatesShot() {
  return (
    <ShotAuthProvider>
      <BillingPage />
    </ShotAuthProvider>
  )
}
