"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "@/components/intelligence/overlays/toast"
import { intelligenceApi, mlAdminApi, type ModelCapabilityInventory } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function LearningCapabilitiesPanel({ enabled, technicalInventory = false }: {
  enabled: boolean; technicalInventory?: boolean
}) {
  const { isAdmin } = useOrgAdmin()
  const [expanded, setExpanded] = useState(technicalInventory)
  const adminInventory = technicalInventory && isAdmin
  const { data, error, isLoading, mutate } = useSWR(
    enabled && (technicalInventory ? isAdmin : expanded)
      ? (adminInventory ? "admin/ml/models" : "intelligence/models/catalog") : null,
    () => adminInventory ? mlAdminApi.listCatalog() : intelligenceApi.modelCatalog(),
    { revalidateOnFocus: false },
  )
  const [pending, setPending] = useState<string | null>(null)
  const capabilities = data?.learningCapabilities ?? []
  const advanced = adminInventory
    ? Object.values(data?.inventory ?? {}).filter((row) => row.visibility === "admin_technical") : []

  async function train(model: ModelCapabilityInventory) {
    if (!isAdmin || !model.manual_training_supported || pending) return
    setPending(model.id)
    try {
      const result = await mlAdminApi.trainModel(model.id)
      toast.message(result.temporal ? "Training queued" : result.trained ? "Artifact saved; promotion is checked separately" : "No new artifact", {
        description: result.reason?.replace(/_/g, " "),
      })
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Training request failed")
    } finally { setPending(null) }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organizational learning capabilities</CardTitle>
        <CardDescription>
          Adaptive learning enabled: {data?.learningActivity?.enabled === true ? "Yes" : data?.learningActivity?.enabled === false ? "No" : "Not verified"}.
          {" "}Active learning and independently verified improvement: not verified.
          {" "}Enabling learning, saving an artifact, and measuring an improvement are separate steps.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <p role="alert">Unable to load learning capabilities.</p> : isLoading ? <p>Loading capabilities…</p> : (
          <details open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
            <summary className="cursor-pointer font-medium">Capabilities and data requirements{data ? ` (${capabilities.length})` : " — open to load"}</summary>
            <div className="mt-3 space-y-3">
              {capabilities.map((model) => (
                <div key={model.id} className="rounded-lg border p-4 space-y-2">
                  <Link className="font-medium underline" href={`/intelligence/models/${encodeURIComponent(model.id)}`}>{model.label}</Link>
                  <p className="text-sm text-muted-foreground">{model.capabilities.join(", ").replace(/_/g, " ") || "Internal learning support"}</p>
                  <p className="text-sm">Data required: {model.data_requirement || "Not reported"}.</p>
                  <p className="text-sm">Eligibility: {model.data_eligibility.status.replace(/_/g, " ")}. {model.data_eligibility.note}</p>
                  <p className="text-sm">Observed data: {Object.entries(model.data_eligibility.observed_counts).map(([key, count]) => `${count} ${key.replace(/_/g, " ")}`).join("; ") || "Not reported"}</p>
                  <p className="text-sm">Verified outcomes: {model.verified_outcomes_count ?? "Not verified"}.</p>
                  {isAdmin && model.manual_training_supported ? (
                    <Button size="sm" variant="outline" disabled={pending !== null} onClick={() => void train(model)}>
                      {pending === model.id ? "Submitting…" : "Request training"}
                    </Button>
                  ) : model.training_unavailable_reason ? <p className="text-sm text-muted-foreground">Manual training unavailable: {model.training_unavailable_reason.replace(/_/g, " ")}.</p> : null}
                </div>
              ))}
              {!capabilities.length ? <p>No capability inventory was reported.</p> : null}
            </div>
          </details>
        )}
        {adminInventory && advanced.length > 0 ? (
          <details>
            <summary className="cursor-pointer font-medium">Administrator technical inventory ({advanced.length})</summary>
            <p className="mt-2 text-sm text-muted-foreground">Planned, scaffolded and disabled implementations. These have no customer training controls.</p>
            <ul className="mt-3 space-y-2">{advanced.map((model) => (
              <li key={model.id} className="rounded border p-3 text-sm">
                <strong>{model.label}</strong> · {String(data?.catalog[model.id]?.status ?? "Not reported")}
                <p>{model.data_requirement || "No activation requirement reported"}</p>
                <p>Fallback: {model.fallback || "Not reported"}. Inference health: {model.inference_health.replace(/_/g, " ")}.</p>
              </li>
            ))}</ul>
          </details>
        ) : null}
      </CardContent>
    </Card>
  )
}
