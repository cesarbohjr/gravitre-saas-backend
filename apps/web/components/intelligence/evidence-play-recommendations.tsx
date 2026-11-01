"use client"

/**
 * Evidence-backed recommendations on the Overview. Each one appears in
 * "Recent insights and activity" as a Recommendation; Review opens this side
 * panel, where an admin can hand it to an installed, approval-governed Play.
 *
 * Recommendations are review-only until a tenant admin selects an installed
 * Play. Approval and external writes remain server-controlled, and a Play
 * finishing is never counted as a business outcome.
 */
import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { ArrowRight, Play } from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import type { FeedItem } from "@/components/intelligence/overview/overview-model"
import { playsApi, type PlayListItem } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { intelligenceEvidenceApi, type EvidenceRecommendation } from "@/lib/intelligence-evidence-api"
import { cn } from "@/lib/utils"

export const EVIDENCE_FEED_PREFIX = "evidence:"

export function useEvidenceRecommendations(enabled: boolean, orgId: string | null) {
  const on = enabled && Boolean(orgId)
  const recs = useSWR(
    on ? ["intelligence/evidence-recommendations", orgId] : null,
    () => intelligenceEvidenceApi.evidenceRecommendations(),
    { revalidateOnFocus: false },
  )
  const catalog = useSWR(on ? ["intelligence/evidence-play-catalog", orgId] : null, () => playsApi.list(), {
    revalidateOnFocus: false,
  })
  return {
    recommendations: recs.data?.recommendations ?? [],
    plays: catalog.data?.plays ?? [],
    error: recs.error as unknown,
    refresh: () => recs.mutate(),
  }
}

function playName(key: string, plays: PlayListItem[]): string {
  const name = plays.find((entry) => entry.play.key === key)?.play.name
  if (name) return name
  const words = key.replace(/[-_]+/g, " ").trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function readyPlay(key: string, plays: PlayListItem[]) {
  const entry = plays.find((item) => item.play.key === key)
  const installationId = entry?.installation?.id
  const ready =
    Boolean(installationId) &&
    entry?.installation?.operatingMode === "ACT WITH APPROVAL" &&
    Boolean(entry?.readiness.act_with_approval_ready)
  return { entry, installationId: ready ? installationId : undefined }
}

/** Feed rows for the Overview's "Recent insights and activity". */
export function evidenceFeedItems(recommendations: EvidenceRecommendation[], plays: PlayListItem[]): FeedItem[] {
  return recommendations.map((item) => ({
    id: `${EVIDENCE_FEED_PREFIX}${item.id}`,
    kind: "recommendation",
    title: item.title,
    detail: item.description,
    suggestion: item.recommended_play_key ? playName(item.recommended_play_key, plays) : null,
    suggestionLabel: "Suggested play",
    meta: [`${item.sources.length} source ${item.sources.length === 1 ? "record" : "records"}`],
    at: null,
    actionLabel: "Review",
    href: APP_ROUTES.plays,
  }))
}

export function EvidenceRecommendationSheet({
  recommendation,
  plays,
  onOpenChange,
  onChanged,
}: {
  recommendation: EvidenceRecommendation | null
  plays: PlayListItem[]
  onOpenChange: (open: boolean) => void
  onChanged: () => void
}) {
  const open = recommendation != null
  const id = recommendation?.id ?? null
  const { data: sweepQuota, error: sweepQuotaError } = useSWR(
    open ? "intelligence/sweep-usage" : null,
    () => intelligenceEvidenceApi.sweepUsage(),
    { revalidateOnFocus: false },
  )
  const { data: lifecycle, mutate: refreshLifecycle } = useSWR(
    id ? ["intelligence/evidence-handoffs", id] : null,
    () => intelligenceEvidenceApi.evidenceRecommendationHandoffs(id ?? ""),
    { revalidateOnFocus: false },
  )
  const [pending, setPending] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const key = recommendation?.recommended_play_key ?? ""
  const { entry, installationId } = readyPlay(key, plays)

  async function submit() {
    if (!recommendation) return
    if (!installationId) {
      setNotice("Configure an approval-governed, ready Play before requesting execution.")
      return
    }
    setPending(true)
    setNotice(null)
    try {
      const result = await intelligenceEvidenceApi.runEvidenceRecommendation(recommendation.id, installationId)
      void refreshLifecycle()
      setNotice(
        `Play request submitted to the governed runtime. Review its approvals and tracked outcomes under Plays → ${result.playKey}. No business outcome has been verified yet.`,
      )
      onChanged()
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "The governed Play request was not accepted.")
    } finally {
      setPending(false)
    }
  }

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) setNotice(null)
        onOpenChange(next)
      }}
    >
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-md">
        <SheetHeader className="border-b border-divide">
          <SheetTitle>{recommendation?.title ?? "Recommendation"}</SheetTitle>
          <SheetDescription>{recommendation?.description}</SheetDescription>
        </SheetHeader>
        {recommendation ? (
          <div className="space-y-5 p-4">
            {key ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--g-brand-surface)] px-2.5 py-1 text-[12px] font-medium text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]">
                <Play className="h-3 w-3" weight="fill" aria-hidden />
                Suggested play: {playName(key, plays)}
              </span>
            ) : null}
            <div className="space-y-1.5">
              <p className={cn(TYPE.meta, "font-semibold")}>Evidence</p>
              <p className={TYPE.bodyMuted}>
                {recommendation.sources.length} persisted source{" "}
                {recommendation.sources.length === 1 ? "record" : "records"} across your connected apps. No verified
                financial impact.
              </p>
              <p className={TYPE.bodyMuted}>
                Cross-provider identity findings are advisory. Starting a Play requires an existing installation and
                its workflow approvals. Execution is not proof of business impact.
              </p>
            </div>

            <div className="space-y-2 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-3 py-3">
              <p className="text-sm font-medium text-[color:var(--g-text-primary)]">
                {installationId
                  ? `${playName(key, plays)} is installed and asks for approval before it acts.`
                  : entry?.installation
                    ? `${playName(key, plays)} is installed but not set to act with approval yet.`
                    : `${playName(key, plays)} isn't installed yet.`}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="brand" disabled={pending || !installationId} onClick={() => void submit()}>
                  {pending ? "Submitting…" : "Request approval-governed Play"}
                </Button>
                <Link
                  href={APP_ROUTES.plays}
                  className="inline-flex items-center gap-1 text-[13px] font-medium text-[color:var(--g-brand-active)] underline underline-offset-2 dark:text-[color:var(--g-brand)]"
                >
                  Configure or review Play approvals
                  <ArrowRight className="h-3 w-3" aria-hidden />
                </Link>
              </div>
            </div>

            {notice ? (
              <p role="status" className="text-sm text-[color:var(--g-text-primary)]">
                {notice}
              </p>
            ) : null}

            <div className="space-y-1.5 border-t border-[color:var(--g-border-subtle)] pt-4">
              <p className={cn(TYPE.meta, "font-semibold")}>Outcome lifecycle</p>
              <p className={TYPE.bodyMuted}>
                {lifecycle?.count ?? 0} recorded Play {lifecycle?.count === 1 ? "handoff" : "handoffs"}. A Play finishing
                does not prove a business outcome.
              </p>
              {(lifecycle?.handoffs ?? []).map((run) => (
                <p key={run.handoffId} className="text-[13px] text-[color:var(--g-text-primary)]">
                  {run.playKey} · {run.status} ·{" "}
                  {run.verifiedBusinessOutcome ? "Source-verified outcome recorded" : "No source-verified business outcome yet"}
                </p>
              ))}
              <Button size="sm" variant="outline" onClick={() => void refreshLifecycle()}>
                Refresh outcome verification
              </Button>
            </div>

            <p className={TYPE.meta}>
              {sweepQuota
                ? `Intelligence sweeps: ${sweepQuota.used} of ${sweepQuota.limit} used this period (${sweepQuota.remaining} remaining).`
                : sweepQuotaError
                  ? "Sweep entitlement unavailable. Review your subscription before requesting analysis."
                  : "Checking your intelligence sweep allowance…"}
            </p>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
