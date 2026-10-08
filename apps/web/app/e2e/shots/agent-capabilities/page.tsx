import { Suspense } from "react"

import AgentCapabilitiesPage from "@/app/(app)/agents/[id]/capabilities/page"

import { ShotAuthProvider } from "../shot-auth"

export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <AgentCapabilitiesPage params={Promise.resolve({ id: "agt_lead_triage" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
