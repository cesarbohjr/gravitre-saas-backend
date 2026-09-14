"use client"

import { useMemo, useRef } from "react"
import useSWR from "swr"
import { intelligenceApi, type IntelligencePageContextResponse } from "@/lib/api"
import {
  deriveSnapshotLoadState,
  type SnapshotLoadState,
} from "@/lib/intelligence/snapshot-state"

export type UseIntelligenceSnapshotOptions = {
  enabled?: boolean
  activeLens?: string
  windowHours?: number
  swrKeySuffix?: string
}

export type IntelligenceSnapshotResult = {
  data: IntelligencePageContextResponse | undefined
  lastKnown: IntelligencePageContextResponse | undefined
  loadState: SnapshotLoadState
  error: unknown
  isValidating: boolean
  mutate: () => void
  generatedAt: string | null
  qualityFlags: string[]
}

/**
 * G1/I1 — canonical page-context fetch with explicit lifecycle states.
 * Commits headline metrics only when loadState is READY+; never surfaces false zero.
 */
export function useIntelligenceSnapshot({
  enabled = true,
  activeLens,
  windowHours = 24,
  swrKeySuffix,
}: UseIntelligenceSnapshotOptions = {}): IntelligenceSnapshotResult {
  const hadDataRef = useRef(false)

  const swrKey =
    enabled
      ? [
          "intelligence/page-context",
          activeLens ?? "default",
          windowHours,
          swrKeySuffix,
        ]
      : null

  const { data, error, isLoading, isValidating, mutate } = useSWR(
    swrKey,
    () => intelligenceApi.pageContext({ windowHours, activeLens }),
    {
      revalidateOnFocus: false,
      keepPreviousData: true,
    },
  )

  if (data) hadDataRef.current = true

  const qualityFlags = data?.qualityFlags ?? data?.snapshot?.qualityFlags ?? []

  const loadState = deriveSnapshotLoadState({
    enabled,
    isLoading,
    isValidating,
    error,
    data,
    hadData: hadDataRef.current,
    qualityFlags,
  })

  const lastKnown = useMemo(() => data, [data])

  const generatedAt =
    data?.snapshot?.generatedAt ??
    (typeof data?.snapshot === "object" &&
    data?.snapshot &&
    "generatedAt" in data.snapshot
      ? String((data.snapshot as { generatedAt?: string }).generatedAt ?? "")
      : null) ||
    null

  return {
    data,
    lastKnown,
    loadState,
    error,
    isValidating,
    mutate,
    generatedAt,
    qualityFlags,
  }
}
