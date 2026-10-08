import { Suspense } from "react"

import PlayResultEvidencePage from "@/app/(app)/plays/[key]/results/[outcomeId]/page"

import { ShotAuthProvider } from "../../../shot-auth"

/** Open /e2e/shots/play-evidence/pipeline_recovery/out_recovered. */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <PlayResultEvidencePage />
      </Suspense>
    </ShotAuthProvider>
  )
}
