import { Suspense } from "react"

import { AiTurnShot } from "./ai-turn-shot"

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AiTurnShot />
    </Suspense>
  )
}
