"use client"

import type { IntelligenceSnapshot } from "@/lib/api"
import { RelationshipsWorkspace } from "@/components/intelligence/relationships/relationships-workspace"

export function RelationshipsTab({
  data,
  isLoading,
  enabled,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
  enabled: boolean
}) {
  return <RelationshipsWorkspace data={data} isLoading={isLoading} enabled={enabled} />
}
