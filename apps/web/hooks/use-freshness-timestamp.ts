"use client"

import { useCallback, useState } from "react"

/** Tracks last successful SWR fetch time for DataFreshness without Date.now() in render. */
export function useFreshnessTimestamp() {
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const markFresh = useCallback(() => setUpdatedAt(Date.now()), [])
  return { updatedAt, markFresh }
}
