/**
 * Module C / STA-331 — model runtime honesty for GIBE surfaces.
 *
 * Prefer `runtime_status` + `artifact_loaded` over catalog TRAINED.
 * Never present catalog TRAINED as live intelligence.
 */

import { readString } from "@/lib/intelligence/helpers"
import type { MlAdminOrgModelStatus } from "@/lib/api"

export type RuntimeHonestyKind =
  | "model_loaded"
  | "heuristic"
  | "data_gate"
  | "unknown"

export type RuntimeHonestyPresentation = {
  kind: RuntimeHonestyKind
  /** Chip label — never bare "TRAINED". */
  label: string
  /** Short detail for tooltips. */
  detail: string
  badgeVariant: "success" | "warning" | "info" | "muted" | "error"
}

export function presentModelRuntime(
  row: Pick<MlAdminOrgModelStatus, "runtime_status" | "artifact_loaded" | "catalog_status"> | null | undefined,
): RuntimeHonestyPresentation {
  const runtime = readString(row?.runtime_status, "").toLowerCase()
  const catalog = readString(row?.catalog_status, "").toLowerCase()
  const artifactLoaded = Boolean(row?.artifact_loaded)

  if (runtime === "data_gate" || runtime === "insufficient_data" || catalog === "data_gate") {
    return {
      kind: "data_gate",
      label: "Insufficient data",
      detail: "Not enough org data for a loaded model path — data gate, not a live TRAINED claim.",
      badgeVariant: "muted",
    }
  }

  if (runtime === "heuristic" || (runtime === "trained" && !artifactLoaded)) {
    return {
      kind: "heuristic",
      label: "Estimate (heuristic)",
      detail:
        runtime === "trained" && !artifactLoaded
          ? "Catalog may say trained, but no artifact is loaded — heuristic path only."
          : "Heuristic / estimate path — not a loaded trained artifact.",
      badgeVariant: "warning",
    }
  }

  if (artifactLoaded || runtime === "trained") {
    return {
      kind: "model_loaded",
      label: "Model (artifact loaded)",
      detail: "Trained artifact is loaded at runtime — not a catalog TRAINED badge alone.",
      badgeVariant: "success",
    }
  }

  if (!runtime) {
    // Catalog TRAINED without runtime must not look live.
    if (catalog === "trained" || catalog === "ready") {
      return {
        kind: "unknown",
        label: "Catalog only",
        detail: "Catalog status present; runtime path unknown — do not treat as live TRAINED.",
        badgeVariant: "muted",
      }
    }
    return {
      kind: "unknown",
      label: "Unknown",
      detail: "No runtime_status from the API yet.",
      badgeVariant: "muted",
    }
  }

  return {
    kind: "unknown",
    label: runtime.replace(/_/g, " "),
    detail: `Runtime status: ${runtime}`,
    badgeVariant: "info",
  }
}

export function summarizeOrgTraining(
  orgTraining: Record<string, MlAdminOrgModelStatus> | null | undefined,
): {
  entries: Array<{ name: string; row: MlAdminOrgModelStatus; presentation: RuntimeHonestyPresentation }>
  counts: Record<RuntimeHonestyKind, number>
} {
  const entries = Object.entries(orgTraining ?? {}).map(([name, row]) => ({
    name,
    row,
    presentation: presentModelRuntime(row),
  }))
  const counts: Record<RuntimeHonestyKind, number> = {
    model_loaded: 0,
    heuristic: 0,
    data_gate: 0,
    unknown: 0,
  }
  for (const entry of entries) {
    counts[entry.presentation.kind] += 1
  }
  return { entries, counts }
}
