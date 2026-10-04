/** Unknown values must not become healthy states or measured zeros. */
export function reportedNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null
}

export function formatReportedCount(value: unknown): string {
  const number = reportedNumber(value)
  if (number == null) return "Not reported"
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`
  if (number >= 1_000) return `${(number / 1_000).toFixed(1)}K`
  return String(number)
}

export function sourceSyncFeedback(result: { success?: boolean; status?: string; error?: string | null }) {
  const status = result.status?.toLowerCase()
  if (result.success === false || status === "error" || status === "failed") {
    return { kind: "error" as const, message: result.error || "Source sync failed" }
  }
  if (status === "queued" || status === "syncing" || status === "running") {
    return { kind: "pending" as const, message: "Source sync queued or in progress" }
  }
  if (result.success === true || ["connected", "completed", "success"].includes(status ?? "")) {
    return { kind: "success" as const, message: "Source sync completed" }
  }
  return { kind: "unknown" as const, message: "Sync status not reported" }
}
