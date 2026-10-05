import { Suspense } from "react"

import AgentMemoryPage from "@/app/agents/[id]/memory/page"

import { ShotAuthProvider } from "../shot-auth"

export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <AgentMemoryPage params={Promise.resolve({ id: "agt_lead_triage" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
