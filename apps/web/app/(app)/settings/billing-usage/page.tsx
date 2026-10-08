import { permanentRedirect } from "next/navigation"

/** Billing Usage folded into Billing & Plan (IA consolidation). */
export default function BillingUsageRedirectPage() {
  permanentRedirect("/settings/billing")
}
