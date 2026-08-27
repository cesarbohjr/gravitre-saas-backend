import { notFound } from "next/navigation"

import { VoiceDuplexHarness } from "./harness"

export default function VoiceDuplexE2EPage() {
  const allowed =
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E === "1" ||
    process.env.PLAYWRIGHT_E2E === "1"

  if (!allowed) notFound()

  return <VoiceDuplexHarness />
}
