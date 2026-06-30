"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { ErrorState } from "@/components/gravitre/empty-state"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { toast } from "sonner"
import { GearSix } from "@phosphor-icons/react"

export function EngineSettingsTab({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? "admin/intelligence/engine-settings" : null,
    () => intelligenceApi.engineSettings(),
    { revalidateOnFocus: false },
  )

  const [validationEnabled, setValidationEnabled] = useState(true)
  const [rerankingEnabled, setRerankingEnabled] = useState(true)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.4)
  const [maxChunks, setMaxChunks] = useState(8)
  const [connectorTimeoutSeconds, setConnectorTimeoutSeconds] = useState(30)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!data) return
    setValidationEnabled(data.validationEnabled)
    setRerankingEnabled(data.rerankingEnabled)
    setConfidenceThreshold(data.confidenceThreshold)
    setMaxChunks(data.maxChunks)
    setConnectorTimeoutSeconds(data.connectorTimeoutSeconds)
  }, [data])

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load engine settings."
    return <ErrorState title="Unable to load engine settings" description={message} onRetry={() => mutate()} />
  }

  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">Loading engine settings…</p>
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await intelligenceApi.updateEngineSettings({
        validation_enabled: validationEnabled,
        reranking_enabled: rerankingEnabled,
        confidence_threshold: confidenceThreshold,
        max_chunks: maxChunks,
        connector_timeout_seconds: connectorTimeoutSeconds,
      })
      toast.success("Intelligence engine settings saved")
      await mutate()
    } catch (saveError) {
      toast.error(saveError instanceof ApiError ? saveError.message : "Could not save settings")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <GearSix className="h-5 w-5 text-violet-500" weight="duotone" aria-hidden />
          <CardTitle>Intelligence engine</CardTitle>
        </div>
        <CardDescription>
          Tune grounding validation, reranking, confidence gating, and retrieval limits for this organization.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <Label htmlFor="validation-enabled">Post-answer validation</Label>
            <p className="text-xs text-muted-foreground">Run a grounding check in standard and reasoning modes.</p>
          </div>
          <Switch id="validation-enabled" checked={validationEnabled} onCheckedChange={setValidationEnabled} />
        </div>

        <div className="flex items-center justify-between gap-4">
          <div>
            <Label htmlFor="reranking-enabled">Hybrid reranking</Label>
            <p className="text-xs text-muted-foreground">Enable cross-encoder reranking on retrieved chunks.</p>
          </div>
          <Switch id="reranking-enabled" checked={rerankingEnabled} onCheckedChange={setRerankingEnabled} />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Label>Confidence threshold</Label>
            <span className="text-xs tabular-nums text-muted-foreground">{confidenceThreshold.toFixed(2)}</span>
          </div>
          <Slider
            min={0.1}
            max={0.9}
            step={0.05}
            value={[confidenceThreshold]}
            onValueChange={(values) => setConfidenceThreshold(values[0] ?? 0.4)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="max-chunks">Max retrieval chunks</Label>
            <Input
              id="max-chunks"
              type="number"
              min={1}
              max={50}
              value={maxChunks}
              onChange={(event) => setMaxChunks(Number(event.target.value) || 8)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="connector-timeout">Connector timeout (seconds)</Label>
            <Input
              id="connector-timeout"
              type="number"
              min={5}
              max={300}
              value={connectorTimeoutSeconds}
              onChange={(event) => setConnectorTimeoutSeconds(Number(event.target.value) || 30)}
            />
          </div>
        </div>

        <Button onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </Button>
      </CardContent>
    </Card>
  )
}
