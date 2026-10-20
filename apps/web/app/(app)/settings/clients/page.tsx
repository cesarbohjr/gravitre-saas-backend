"use client"

import { useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { MspClientsContent } from "@/components/settings/msp-clients"
import { SettingsShell } from "@/components/settings/settings-shell"
import { SetNote } from "@/components/settings/settings-kit"
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
        <SetNote tone="white">
          Clients is for MSPs and resellers: you pay Gravitre and bill each client yourself. To work with another
          company as an equal partner, with each side keeping its own billing, use{" "}
          <Link href="/settings/federation">Federation</Link> instead.
        </SetNote>
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
