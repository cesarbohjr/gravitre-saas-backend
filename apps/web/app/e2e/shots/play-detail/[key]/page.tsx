import { Suspense } from "react"

import PlayDetailPage from "@/app/plays/[key]/page"

import { ShotAuthProvider } from "../../shot-auth"

/** Open /e2e/shots/play-detail/pipeline_recovery. */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <PlayDetailPage />
      </Suspense>
    </ShotAuthProvider>
  )
}
