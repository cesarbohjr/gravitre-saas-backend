import { Suspense } from "react"

import SourceDetailPage from "@/app/(app)/sources/[id]/page"

import { ShotAuthProvider } from "../../shot-auth"

/**
 * Source detail for capture. The page reads its id with `useParams()`, so this
 * route carries a real `[id]` segment. Open /e2e/shots/source-detail/src_warehouse.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <SourceDetailPage />
      </Suspense>
    </ShotAuthProvider>
  )
}
