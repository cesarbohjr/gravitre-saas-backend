"use client"

import useSWR from "swr"
import {
  buildMemoryLearningClaim,
  buildQueryClusterClaim,
  buildRetrievalRankerClaim,
  EMPTY_LIVE_INTEL,
  type LiveIntelSnapshot,
  type MarketingIntelClaim,
} from "@/lib/marketing-intelligence-truth"
import { cn } from "@/lib/utils"

type HonestyPayload = {
  live: LiveIntelSnapshot
  claims: {
    retrievalRanker: MarketingIntelClaim
    queryClusters: MarketingIntelClaim
    memoryLearning: MarketingIntelClaim
  }
}

const fetcher = (url: string) => fetch(url).then((r) => r.json() as Promise<HonestyPayload>)

function ClaimCard({ claim, className }: { claim: MarketingIntelClaim; className?: string }) {
  return (
    <div className={cn("rounded-lg border border-border bg-card/70 p-3", className)}>
      <p className="text-muted-foreground text-xs">{claim.eyebrow}</p>
      <p className="text-foreground mt-1 text-sm leading-snug">{claim.primary}</p>
      {claim.provenance !== "computed" && claim.provenance !== "operational" ? (
        <p className="mt-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
          {claim.provenance === "data_gate" ? "Data gate" : "Honest status"}
        </p>
      ) : null}
    </div>
  )
}

/** How-it-works GIBE visual — wired to Module C honesty formatters (+ optional live feed). */
export function GibeHonestyCards({ className }: { className?: string }) {
  const { data } = useSWR("/api/marketing/gibe-honesty", fetcher, {
    revalidateOnFocus: false,
    fallbackData: {
      live: EMPTY_LIVE_INTEL,
      claims: {
        retrievalRanker: buildRetrievalRankerClaim(EMPTY_LIVE_INTEL),
        queryClusters: buildQueryClusterClaim(EMPTY_LIVE_INTEL),
        memoryLearning: buildMemoryLearningClaim(EMPTY_LIVE_INTEL),
      },
    },
  })

  const clusters = data?.claims.queryClusters ?? buildQueryClusterClaim(EMPTY_LIVE_INTEL)
  const ranker = data?.claims.retrievalRanker ?? buildRetrievalRankerClaim(EMPTY_LIVE_INTEL)

  return (
    <div className={cn("space-y-3 text-sm", className)}>
      <ClaimCard claim={clusters} />
      <ClaimCard claim={ranker} />
    </div>
  )
}
