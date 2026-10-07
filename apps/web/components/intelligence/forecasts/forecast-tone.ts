import type { Forecast, ForecastKind } from "@/components/intelligence/forecasts/forecast-model"

/** Dot / bar colour: confident risks read as danger, softer risks as warning. */
export function forecastDotColor(forecast: Pick<Forecast, "kind" | "confidence">): string {
  if (forecast.kind === "opportunity") return "var(--g-emerald)"
  if (forecast.kind === "signal") return "var(--g-text-muted)"
  return (forecast.confidence ?? 0) >= 0.65 ? "var(--g-danger)" : "var(--g-warning)"
}

export const KIND_LABEL: Record<ForecastKind, string> = {
  risk: "Risk",
  opportunity: "Opportunity",
  signal: "Signal",
}

export const KIND_CHIP_CLASS: Record<ForecastKind, string> = {
  risk: "bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]",
  opportunity: "bg-[color:var(--g-emerald-soft)] text-[color:var(--g-emerald)]",
  signal: "bg-[color:var(--g-surface-2)] text-muted-foreground",
}
