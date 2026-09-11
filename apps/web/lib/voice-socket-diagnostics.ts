/**
 * Capture for the one remaining unexplained "Voice connection interrupted" report.
 *
 * That report could not be diagnosed from code alone. Each candidate cause was
 * eliminated by reading configuration -- the deployed bundle resolves to
 * wss://api.gravitre.app, API_PUBLIC_URL is correct, the access token travels as a
 * query param, auth and billing refusals carry a terminal class -- which left
 * `service_failure` as a hypothesis with no way to confirm it. The two facts that
 * separate the remaining possibilities, the actual socket URL and the actual close
 * code, exist only in the browser at the moment of failure.
 *
 * So this records them. The point is not general logging; it is that the next
 * occurrence should explain itself rather than requiring someone to have DevTools
 * already open on the right tab.
 */

export type VoiceSocketDiagnostic = {
  event: "error" | "close"
  code?: number
  reason?: string
  wasClean?: boolean
}

export type VoiceSocketFailureRecord = VoiceSocketDiagnostic & {
  url: string
  everOpened: boolean
  attempt: number
  intentional: boolean
  sessionWanted: boolean
  lastServerError: string | null
  at: string
}

/** Kept small and bounded: this is a diagnostic, not a telemetry buffer. */
const MAX_RECORDS = 20
const records: VoiceSocketFailureRecord[] = []

/**
 * The access token rides in the query string, so the raw URL is a live credential.
 * Keep the origin and path (the parts that actually distinguish the candidate
 * causes) and drop every value.
 */
export function redactVoiceWsUrl(raw: string | null | undefined): string {
  const value = (raw ?? "").trim()
  if (!value) return "(none)"
  try {
    const url = new URL(value)
    const params = [...url.searchParams.keys()]
    const shown = params.length ? `?${params.map((k) => `${k}=<redacted>`).join("&")}` : ""
    return `${url.protocol}//${url.host}${url.pathname}${shown}`
  } catch {
    // Not parseable, so it cannot be safely trimmed to origin + path.
    return "(unparseable)"
  }
}

export function recordVoiceSocketFailure(record: Omit<VoiceSocketFailureRecord, "at">): void {
  const entry: VoiceSocketFailureRecord = { ...record, at: new Date().toISOString() }
  records.push(entry)
  if (records.length > MAX_RECORDS) records.shift()

  if (typeof window !== "undefined") {
    // Reachable from the console without a debugger or a source map.
    ;(window as unknown as { __gravitreVoiceSocketFailures?: VoiceSocketFailureRecord[] }).__gravitreVoiceSocketFailures =
      records
  }

  // One line, greppable, and complete enough to settle the diagnosis: an unclean
  // 1006 on an origin that refused the upgrade is a different bug from a clean
  // close after a service_failure frame.
  console.warn(
    `[gravitre:voice] socket ${entry.event} url=${entry.url} code=${entry.code ?? "n/a"} ` +
      `clean=${entry.wasClean ?? "n/a"} reason=${JSON.stringify(entry.reason ?? "")} ` +
      `everOpened=${entry.everOpened} attempt=${entry.attempt} intentional=${entry.intentional} ` +
      `sessionWanted=${entry.sessionWanted} lastServerError=${JSON.stringify(entry.lastServerError)}`,
  )
}

export function readVoiceSocketFailures(): VoiceSocketFailureRecord[] {
  return [...records]
}

export function clearVoiceSocketFailures(): void {
  records.length = 0
}
