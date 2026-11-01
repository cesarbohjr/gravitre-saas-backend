import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { expect, it, vi } from "vitest"
import type { AgentConnectorProfile } from "@/types/api"
import { AgentConnectorRecommendations } from "@/components/connectors/agent-connector-recommendations"
vi.mock("next/link", () => ({default: ({children,href,...props}: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={href} {...props}>{children}</a>}))
const profile: AgentConnectorProfile = {
  schemaVersion:1, offlineCapabilities:["Draft a campaign plan"], authorityNote:"Writes require approval",
  recommendations:[
    {connectorType:"google_ads",label:"Google Ads",priority:1,group:"first",purpose:"Review campaign performance",capabilities:["Campaign reports"],supported:true,required:false,requiredForExecution:true,connectPath:"/connectors?type=google_ads",state:"available",stateLabel:"Available to connect",connected:false,ready:false,canExecute:false},
    {connectorType:"meta_ads",label:"Meta Ads",priority:2,group:"optional",purpose:"Not supported yet",capabilities:[],supported:false,required:false,requiredForExecution:true,connectPath:null,state:"not_supported",stateLabel:"Not supported yet",connected:false,ready:false,canExecute:false},
  ],
}
it("explains offline value, prioritizes useful apps and does not link unsupported integrations", () => {
  const html=renderToStaticMarkup(<AgentConnectorRecommendations profile={profile} />)
  expect(html).toContain("No connectors needed")
  expect(html).toContain("Draft a campaign plan")
  expect(html.indexOf("Recommended first")).toBeLessThan(html.indexOf("Optional"))
  expect(html).toContain('href="/connectors?type=google_ads"')
  expect(html).toContain("Review campaign performance")
  expect(html).not.toContain("Connect Meta Ads")
  expect(html).toContain("Writes require approval")
})
