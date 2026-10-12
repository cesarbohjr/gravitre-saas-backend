"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { accountIntelligenceApi, isFeatureOff, type RecommendationFeedItem } from "@/lib/api"

const KIND_LABEL: Record<string, string> = {
  business_signal: "Signal",
  suggestion: "Suggestion",
  proposed_work: "Proposed work",
  account_change: "Account",
}

function FeedItem({ item, onDecided }: { item: RecommendationFeedItem; onDecided: () => void }) {
  const [busy, setBusy] = useState<"accept" | "dismiss" | null>(null)
  const canDecide = Boolean(item.workObjectId) && item.actions.includes("accept")

  const decide = async (accept: boolean) => {
    if (!item.workObjectId) return
    setBusy(accept ? "accept" : "dismiss")
    try {
      if (accept) {
        const { playRunRequest: run } = await accountIntelligenceApi.acceptProposal(item.workObjectId)
        if (run && !run.blockedReason && run.body.installationId) {
          toast.success("Added to planned work. Nothing runs until someone starts it.", {
            action: {
              label: "Start Play",
              onClick: () => {
                accountIntelligenceApi
                  .startPlayRun(run)
                  .then((res) =>
                    toast.success(res.status === "awaiting_approval" ? "Play started and is awaiting approval." : "Play started."),
                  )
                  .catch((error: unknown) =>
                    toast.error(error instanceof Error ? error.message : "Couldn't start the Play."),
                  )
              },
            },
          })
        } else {
          toast.success(
            run?.blockedReason
              ? `Added to planned work. ${run.blockedReason}`
              : "Added to planned work. Nothing runs until someone starts it.",
          )
        }
      } else {
        await accountIntelligenceApi.dismissProposal(item.workObjectId)
        toast.success("Dismissed.")
      }
      onDecided()
    } catch {
      toast.error("Couldn't save that decision. Try again.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <li className="space-y-1 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-foreground">{item.title}</span>
        <span className="text-xs text-muted-foreground">{KIND_LABEL[item.kind] ?? "Recommendation"}</span>
      </div>
      {item.why ? <p className="text-sm text-muted-foreground">{item.why}</p> : null}
      {item.evidence.length ? (
        <ul className="space-y-0.5">
          {item.evidence.map((e) => (
            <li key={e} className="text-xs text-muted-foreground [overflow-wrap:anywhere]">
              {e}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex flex-wrap gap-2 pt-1">
        {canDecide ? (
          <>
            <Button size="sm" className="min-h-11" disabled={busy !== null} onClick={() => void decide(true)}>
              {busy === "accept" ? "Accepting…" : "Accept"}
            </Button>
            <Button size="sm" variant="outline" className="min-h-11" disabled={busy !== null} onClick={() => void decide(false)}>
              {busy === "dismiss" ? "Dismissing…" : "Dismiss"}
            </Button>
          </>
        ) : null}
        {item.href && !canDecide ? (
          <Button size="sm" variant="ghost" className="min-h-11" asChild>
            <Link href={item.href}>Open</Link>
          </Button>
        ) : null}
      </div>
    </li>
  )
}

/** One ranked list of what needs attention. Renders nothing while switched off. */
export function RecommendationFeedPanel() {
  const { data, error, isLoading, mutate } = useSWR("recommendation-feed", () => accountIntelligenceApi.feed(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
  if (isFeatureOff(error)) return null
  const unavailable = data ? Object.entries(data.sources).filter(([, state]) => state === "error").length : 0
  return (
    <section aria-labelledby="recommendation-feed-heading" className="space-y-2">
      <div>
        <h2 id="recommendation-feed-heading" className="font-sans text-xl font-medium">Needs attention</h2>
        <p className="text-sm text-muted-foreground">Recommendations only. Nothing here runs by itself.</p>
      </div>
      {isLoading && !data ? <p role="status" className="text-sm text-muted-foreground">Loading recommendations…</p> : null}
      {error && !data ? (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          Recommendations couldn&apos;t load.
          <Button variant="outline" size="sm" className="min-h-11" onClick={() => void mutate()}>
            Retry
          </Button>
        </div>
      ) : null}
      {unavailable ? (
        <p role="status" className="text-xs text-muted-foreground">
          {unavailable === 1 ? "One source" : `${unavailable} sources`} couldn&apos;t be read, so this list may be incomplete.
        </p>
      ) : null}
      {data && data.items.length === 0 ? <p className="text-sm text-muted-foreground">Nothing needs attention right now.</p> : null}
      <ul className="divide-y divide-divide">
        {data?.items.map((item) => <FeedItem key={item.id} item={item} onDecided={() => void mutate()} />)}
      </ul>
    </section>
  )
}
