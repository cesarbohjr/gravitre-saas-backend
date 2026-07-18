/** API returns predictions as a model→payload dict; normalize to card rows. */
export function normalizeDomainPredictions(raw: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(raw)) {
    return raw.filter((row): row is Record<string, unknown> => !!row && typeof row === "object")
  }
  if (raw && typeof raw === "object") {
    return Object.entries(raw as Record<string, unknown>).map(([model, payload]) => {
      const row = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {}
      return { model: row.model ?? model, ...row }
    })
  }
  return []
}
