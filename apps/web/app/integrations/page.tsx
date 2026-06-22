import { redirect } from "next/navigation"

/** Legacy route — connectors hub is the customer-facing integration surface. */
export default function IntegrationsPage() {
  redirect("/connectors")
}
