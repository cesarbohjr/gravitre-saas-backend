"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Mail, ShieldCheck, PlugZap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { connectorsApi } from "@/lib/api"
import { managedProviderAvailable, openManagedConnector } from "@/lib/managed-connector-auth"
import { ProviderLogo } from "@/components/gravitre/provider-logo"

const SOURCES = [
  { key:"smartlead", name:"Smartlead",  description:"Campaigns, mailboxes and reply tracking", kind:"Cold email", phase:"Read-only integration", href:"https://www.smartlead.ai/" },
  { key:"instantly", name:"Instantly",  description:"Cold outreach sequences and inbox workflows", kind:"Cold email", phase:"Nango setup pending", href:"https://instantly.ai/" },
  { key:"quickmail", name:"QuickMail",  description:"Multichannel email sequencing for teams", kind:"Cold email", phase:"Nango setup pending", href:"https://quickmail.io/" },
  { key:"hunter", name:"Hunter",  description:"Find and verify emails; email sequences", kind:"Prospecting", phase:"Nango setup pending", href:"https://hunter.io/" },
  { key:"snov", name:"Snov.io",  description:"Lead discovery and email campaigns", kind:"Prospecting", phase:"Nango setup pending", href:"https://snov.io/" },
] as const

export function OutboundProviderCards() {
  const { data: managed, mutate } = useSWR("outreach-managed-connectors", () => connectorsApi.managedCatalog())
  const [connecting, setConnecting] = useState<string | null>(null)
  async function connect(key: string, name: string) {
    if (!managedProviderAvailable(managed, key)) return
    setConnecting(key)
    try {
      const connected = await openManagedConnector(key, { name })
      if (connected) { toast.success(`${name} connected`); await mutate() }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not connect provider")
    } finally { setConnecting(null) }
  }
  return (
    <section aria-labelledby="outbound-provider-heading" className="mt-7 space-y-3" data-testid="outbound-provider-cards">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Mail className="size-4 text-muted-foreground" aria-hidden />
            <h2 id="outbound-provider-heading" className="text-[15px] font-semibold">Outbound & prospecting</h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Connect your outreach provider through Gravitre-managed Nango connections. Campaign sending requires separate approval.
          </p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-divide px-2.5 py-1 text-[11px] text-muted-foreground">
          <ShieldCheck className="size-3.5" aria-hidden /> Sending gated
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {SOURCES.map((provider) => (
          <article key={provider.key} className="flex min-w-0 flex-col gap-3 rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-3" data-provider={provider.key}>
            <div className="flex items-start gap-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-divide bg-[color:var(--g-surface-2)] text-sm font-semibold" aria-label={provider.name + " icon"}>
                <ProviderLogo provider={provider.key} label={provider.name} size="lg" />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="text-[13px] font-semibold">{provider.name}</h3>
                <p className="text-[11px] text-muted-foreground">{provider.kind}</p>
              </div>
              <PlugZap className="size-4 text-muted-foreground" aria-hidden />
            </div>
            <p className="min-h-9 text-xs leading-5 text-muted-foreground">{provider.description}</p>
            <div className="mt-auto flex items-center justify-between gap-2 border-t border-divide pt-3">
              <span className="text-[11px] text-muted-foreground">{managedProviderAvailable(managed, provider.key) ? "Ready to connect" : provider.phase}</span>
              <a href={provider.href} target="_blank" rel="noopener noreferrer" className="text-xs font-medium text-foreground underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label={"Visit " + provider.name + " provider website"}>Provider details</a>
            </div>
          <Button size="sm" variant="outline" disabled={!managedProviderAvailable(managed, provider.key) || connecting !== null} onClick={() => void connect(provider.key, provider.name)}>{connecting === provider.key ? "Connecting…" : managedProviderAvailable(managed, provider.key) ? "Connect with Gravitre" : "Admin setup required"}</Button>
          </article>
        ))}
      </div>
      <p className="text-[11px] text-muted-foreground">
        Provider cards show integration development status, not a verified active connection. Nango configuration and account permissions determine actual availability.
      </p>
    </section>
  )
}
