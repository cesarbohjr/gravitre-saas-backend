import { Suspense } from "react"

import RunDetailPage from "@/app/runs/[id]/page"

import { ShotAuthProvider } from "../shot-auth"

/**
 * Run detail for capture. The page reads `params` via `use()`, so it needs its
 * own route instead of a `SHOT_SURFACES` entry. The run is a failed fixture
 * with an approval pause and a retryable connector step.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <Suspense fallback={null}>
        <RunDetailPage params={Promise.resolve({ id: "run_support_4821" })} />
      </Suspense>
    </ShotAuthProvider>
  )
}
