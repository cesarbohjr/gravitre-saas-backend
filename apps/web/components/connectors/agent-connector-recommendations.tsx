"use client"

import Link from "next/link"
import useSWR from "swr"
import { agentKnowledgeApi } from "@/lib/api"
import type { AgentConnectorProfile } from "@/types/api"

const GROUPS = { first: "Recommended first", next: "Recommended next", optional: "Optional" } as const

/** One presentation contract for catalog, installation and installed agents. */
export function AgentConnectorRecommendations({ profile }: { profile: AgentConnectorProfile }) {
  return (
    <section aria-label="Agent connector guidance" className="space-y-3 text-sm">
      <div>
        <h3 className="font-semibold">No connectors needed</h3>
        <ul className="list-inside list-disc text-muted-foreground">
          {profile.offlineCapabilities.map((capability) => <li key={capability}>{capability}</li>)}
        </ul>
        {profile.noIntegrationRationale ? <p className="text-muted-foreground">{profile.noIntegrationRationale}</p> : null}
      </div>
      {(["first", "next", "optional"] as const).map((group) => {
        const items = profile.recommendations.filter((item) => item.group === group)
        return items.length ? (
          <div key={group}>
            <h4 className="font-medium">{GROUPS[group]}</h4>
            <ul className="space-y-3">
              {items.map((item) => (
                <li key={item.connectorType}>
                  <p><strong>{item.label}</strong> · {item.stateLabel}</p>
                  <p className="text-muted-foreground">{item.purpose}</p>
                  {item.supported && item.state !== "connected" && item.connectPath?.startsWith("/connectors?") ? (
                    <Link className="inline-flex min-h-11 items-center underline" href={item.connectPath}>
                      {item.state === "needs_attention" ? "Review" : "Connect"} {item.label}
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null
      })}
      <p className="text-xs text-muted-foreground">{profile.authorityNote}</p>
    </section>
  )
}

/** Fresh tenant-scoped capabilities; reconnect/revocation needs no reinstall. */
export function InstalledAgentConnectorRecommendations({ agentId }: { agentId: string }) {
  const { data, error } = useSWR(`agent/${agentId}/capabilities`, () => agentKnowledgeApi.getCapabilities(agentId), { refreshInterval: 30_000 })
  if (error) return <p role="status">Connector readiness could not be loaded. Live actions still require current access.</p>
  return data?.connectorProfile ? <AgentConnectorRecommendations profile={data.connectorProfile} /> : null
}
