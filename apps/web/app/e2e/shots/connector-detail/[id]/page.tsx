import { Suspense } from "react"

import ConnectorDetailPage from "@/app/(app)/connectors/[id]/page"

import { ShotAuthProvider } from "../../shot-auth"

/** Open /e2e/shots/connector-detail/con_hubspot. */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <ConnectorDetailPage />
      </Suspense>
    </ShotAuthProvider>
  )
}
