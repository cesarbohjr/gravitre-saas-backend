type ActivitySummaryRow = {
  status?: string
  lifecycleState?: string
  sections?: { verification?: { verified?: boolean; confidence?: string }; approval?: { status?: string } }
}

/** Counts only rows currently loaded, and never equates successful execution with verification. */
export function summarizeActivityView(rows: ActivitySummaryRow[]) {
  let running = 0
  let approval = 0
  let completed = 0
  let verified = 0
  for (const row of rows) {
    const status = (row.status ?? "").toLowerCase()
    const lifecycle = (row.lifecycleState ?? "").toLowerCase()
    if (["running", "processing", "executing"].includes(status)) running++
    if (["awaiting_approval", "waiting_approval", "pending_approval", "needs_approval"].includes(status) || row.sections?.approval?.status === "pending") approval++
    if (["completed", "succeeded", "success"].includes(status)) completed++
    if (status === "verified" || lifecycle === "verified" || row.sections?.verification?.verified === true || (row.sections?.verification?.verified == null && row.sections?.verification?.confidence === "verified")) verified++
  }
  return { running, approval, completed, verified }
}
