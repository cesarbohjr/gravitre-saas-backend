import { Suspense } from "react"

import AgentProfilePage from "@/app/(app)/agents/[id]/page"

import { ShotAuthProvider } from "../shot-auth"

/**
 * Agent detail for capture. Like the builder, the page reads `params` via
 * `use()`, so it needs its own route instead of a `SHOT_SURFACES` entry.
 * Agent, identity policy and capability profile are fixtures.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <AgentProfilePage params={Promise.resolve({ id: "agt_lead_triage" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
