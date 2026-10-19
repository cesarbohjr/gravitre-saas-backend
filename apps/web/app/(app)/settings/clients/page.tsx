"use client"

import { useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { MspClientsContent } from "@/components/settings/msp-clients"
import { SettingsShell } from "@/components/settings/settings-shell"
import { useOrgAdmin } from "@/lib/use-org-admin"

/** Settings › Clients: the MSP partner program (wholesale billing and rebilling). */
export default function ClientsSettingsPage() {
  const { showAdmin } = useOrgAdmin()
  return (
    <AppShell title="Settings">
      <SettingsShell activeSection="clients" isAdmin={showAdmin}>
        <Suspense fallback={null}>
          <CheckoutReturnNotice />
        </Suspense>
        <MspClientsContent />
      </SettingsShell>
    </AppShell>
  )
}

/** Stripe Checkout sends the partner back with ?billing=started|cancelled. */
function CheckoutReturnNotice() {
  const params = useSearchParams()
  const billing = params.get("billing")
  useEffect(() => {
    if (billing === "started") toast.success("Wholesale billing started. Your clients are covered.")
    else if (billing === "cancelled") toast.message("Checkout was cancelled. Nothing was charged.")
  }, [billing])
  return null
}
