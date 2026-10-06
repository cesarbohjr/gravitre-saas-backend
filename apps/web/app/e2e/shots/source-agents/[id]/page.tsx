import { Suspense } from "react"

import SourceAgentAssignmentsPage from "@/app/sources/[id]/agents/page"

import { ShotAuthProvider } from "../../shot-auth"

/** Open /e2e/shots/source-agents/src_warehouse. */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <SourceAgentAssignmentsPage />
      </Suspense>
    </ShotAuthProvider>
  )
}
