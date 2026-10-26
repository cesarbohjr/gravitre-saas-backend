"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { playsApi } from "@/lib/api"
import { intelligenceEvidenceApi } from "@/lib/intelligence-evidence-api"

/** Intelligence recommendations are review-only until a tenant admin selects
 * an installed Play. Approval and external writes remain server-controlled. */
export function EvidencePlayRecommendations({ enabled, orgId }: { enabled: boolean; orgId: string | null }) {
  const { data: sweepQuota, error: sweepQuotaError } = useSWR(
    enabled && orgId ? ["intelligence/sweep-usage", orgId] : null,
    () => intelligenceEvidenceApi.sweepUsage(),
    { revalidateOnFocus: false },
  )
  const { data, error, isLoading, mutate } = useSWR(
    enabled && orgId ? ["intelligence/evidence-recommendations", orgId] : null,
    () => intelligenceEvidenceApi.evidenceRecommendations(),
    { revalidateOnFocus: false },
  )
  const { data: playCatalog } = useSWR(
    enabled && orgId ? ["intelligence/evidence-play-catalog", orgId] : null,
    () => playsApi.list(),
    { revalidateOnFocus: false },
  )
  const [pending, setPending] = useState<string | null>(null)
  const [selectedRecommendation, setSelectedRecommendation] = useState<string | null>(null)
  const { data: lifecycle, mutate: refreshLifecycle } = useSWR(
    enabled && orgId && selectedRecommendation ? ["intelligence/evidence-handoffs", orgId, selectedRecommendation] : null,
    () => intelligenceEvidenceApi.evidenceRecommendationHandoffs(selectedRecommendation ?? ""),
    { revalidateOnFocus: false },
  )
  const [notice, setNotice] = useState<string | null>(null)

  async function submit(id: string, playKey: string) {
    const selected = playCatalog?.plays.find((entry) => entry.play.key === playKey)
    const installationId = selected?.installation?.id
    if (!installationId || selected?.installation?.operatingMode !== "ACT WITH APPROVAL" || !selected.readiness.act_with_approval_ready) {
      setNotice("Configure an approval-governed, ready Play before requesting execution.")
      return
    }
    setPending(id)
    setNotice(null)
    try {
      const result = await intelligenceEvidenceApi.runEvidenceRecommendation(id, installationId)
      setSelectedRecommendation(id)
      void refreshLifecycle()
      setNotice(`Play request submitted to the governed runtime. Review its approvals and tracked outcomes under Plays → ${result.playKey}. No business outcome has been verified yet.`)
      await mutate()
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : "The governed Play request was not accepted.")
    } finally {
      setPending(null)
    }
  }

  return (
    <section aria-labelledby="evidence-recommendations-title" className="mt-6 rounded-xl border border-border p-5">
      <h2 id="evidence-recommendations-title" className="text-lg font-semibold">Evidence-backed recommendations</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        {sweepQuota
          ? `Intelligence sweeps: ${sweepQuota.used} of ${sweepQuota.limit} used this period (${sweepQuota.remaining} remaining).`
          : sweepQuotaError
            ? "Sweep entitlement unavailable. Review your subscription before requesting analysis."
            : "Checking your intelligence sweep allowance…"}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Cross-provider identity findings are advisory. Starting a Play requires an existing installation and canonical workflow approvals. Execution is not proof of business impact.
      </p>
      {isLoading && <p role="status" className="mt-3 text-sm">Checking verified source evidence…</p>}
      {error && <p role="alert" className="mt-3 text-sm">Recommendations are unavailable. {error instanceof Error ? error.message : ""}</p>}
      {data?.recommendations.length === 0 && <p className="mt-3 text-sm text-muted-foreground">No supported cross-provider recommendations yet.</p>}
      {notice && <p role="status" className="mt-3 text-sm">{notice}</p>}
      <div className="mt-3 space-y-4">
        {(data?.recommendations ?? []).map((item) => (
          <article key={item.id} className="rounded-lg border border-border p-4">
            <h3 className="font-medium">{item.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
            <p className="mt-1 text-xs text-muted-foreground">{item.sources.length} persisted source records · No verified financial impact</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button type="button" disabled={
                pending !== null || !playCatalog?.plays.some((entry) =>
                  entry.play.key === item.recommended_play_key &&
                  entry.installation?.operatingMode === "ACT WITH APPROVAL" &&
                  entry.readiness.act_with_approval_ready
                )
              }
                className="rounded border border-border px-3 py-1 text-sm disabled:opacity-50"
                onClick={() => void submit(item.id, item.recommended_play_key)}>
                {pending === item.id ? "Submitting…" : "Request approval-governed Play"}
              </button>
              <button type="button" className="text-sm underline" onClick={() => { setSelectedRecommendation(item.id); void refreshLifecycle() }}>View outcome lifecycle</button>
              <Link href="/plays" className="text-sm underline">Configure or review Play approvals</Link>
            </div>
            {selectedRecommendation === item.id && (
              <div role="status" className="mt-3 text-sm">
                <p>{lifecycle?.count ?? 0} recorded Play handoffs. A Play finishing does not prove a business outcome.</p>
                {(lifecycle?.handoffs ?? []).map((run) => (
                  <p key={run.handoffId}>
                    Play: {run.playKey} · {run.status} · {run.verifiedBusinessOutcome
                      ? "Source-verified outcome recorded"
                      : "No source-verified business outcome yet"}
                  </p>
                ))}
                <button type="button" className="mt-2 text-sm underline" onClick={() => void refreshLifecycle()}>
                  Refresh outcome verification
                </button>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
