"use client"

import { useEffect, useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
  const [maxChunks, setMaxChunks] = useState("8")
  const [connectorTimeoutSeconds, setConnectorTimeoutSeconds] = useState("30")
  const [standingInvestigatorsEnabled, setStandingInvestigatorsEnabled] =
    useState<boolean | null>(null)
  const lock = useRef(false)
  const dirty = useRef(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!data || dirty.current || lock.current) return
    setValidationEnabled(data.validationEnabled)
    setRerankingEnabled(data.rerankingEnabled)
    setConfidenceThreshold(data.confidenceThreshold)
    setMaxChunks(String(data.maxChunks))
    setConnectorTimeoutSeconds(String(data.connectorTimeoutSeconds))
    setStandingInvestigatorsEnabled(data.standingInvestigatorsEnabled ?? null)
  }, [data])

  if (error && !data) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Failed to load engine settings."
    return (
      <ErrorState
        title="Unable to load engine settings"
        description={message}
        onRetry={() => mutate()}
      />
    )
  }

  if ((isLoading && !data) || !data) {
    return (
      <p className="text-sm text-muted-foreground">Loading engine settings…</p>
    )
  }

  const handleSave = async () => {
    if (lock.current) return
    if (
      !Number.isInteger(Number(maxChunks)) ||
      Number(maxChunks) < 1 ||
      Number(maxChunks) > 50 ||
      !Number.isInteger(Number(connectorTimeoutSeconds)) ||
      Number(connectorTimeoutSeconds) < 5 ||
      Number(connectorTimeoutSeconds) > 300 ||
      !Number.isFinite(confidenceThreshold) ||
      confidenceThreshold < 0.1 ||
      confidenceThreshold > 0.9
    ) {
      setFailure(
        "Use 1–50 passages, a 5–300 second timeout and confidence between 0.10 and 0.90.",
      )
      return
    }
    lock.current = true
    setFailure(null)
    setSaving(true)
    try {
      await intelligenceApi.updateEngineSettings({
        validation_enabled: validationEnabled,
        reranking_enabled: rerankingEnabled,
        confidence_threshold: confidenceThreshold,
        max_chunks: Number(maxChunks),
        connector_timeout_seconds: Number(connectorTimeoutSeconds),
        ...(standingInvestigatorsEnabled === null
          ? {}
          : { standing_investigators_enabled: standingInvestigatorsEnabled }),
      })
      toast.success("Search & grounding settings saved")
      dirty.current = false
      await Promise.allSettled([mutate()])
    } catch (saveError) {
      setFailure(
        saveError instanceof Error
          ? saveError.message
          : "Could not save settings. Your edits are retained.",
      )
    } finally {
      lock.current = false
      setSaving(false)
    }
  }

  return (
    <Card className="border-0 border-t border-border rounded-none shadow-none [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11">
      <CardHeader>
        <div className="flex items-center gap-2">
          <GearSix
            className="h-5 w-5 text-[color:var(--g-emerald-deep)]"
            weight="duotone"
            aria-hidden
          />
          <CardTitle>Search & grounding</CardTitle>
        </div>
        <CardDescription>
          Control how carefully answers are checked against sources, and how
          much context search can pull in.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <fieldset
          disabled={saving}
          className="min-w-0 space-y-6"
          onChangeCapture={() => {
            dirty.current = true
          }}
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label
                className="flex min-h-11 items-center"
                htmlFor="validation-enabled"
              >
                Check answers against sources
              </Label>
              <p className="text-xs text-muted-foreground">
                After answering, verify claims against retrieved material in
                standard and reasoning modes.
              </p>
            </div>
            <Switch
              id="validation-enabled"
              checked={validationEnabled}
              disabled={saving}
              onCheckedChange={(value) => {
                dirty.current = true
                setValidationEnabled(value)
              }}
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <Label
                className="flex min-h-11 items-center"
                htmlFor="reranking-enabled"
              >
                Smart result reordering
              </Label>
              <p className="text-xs text-muted-foreground">
                Re-score search passages so the most relevant ones reach the
                answer first.
              </p>
            </div>
            <Switch
              id="reranking-enabled"
              checked={rerankingEnabled}
              disabled={saving}
              onCheckedChange={(value) => {
                dirty.current = true
                setRerankingEnabled(value)
              }}
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              <Label
                className="flex min-h-11 items-center"
                htmlFor="standing-investigators-enabled"
              >
                Standing investigators
              </Label>
              <p className="text-xs text-muted-foreground">
                Run read-scoped advisory scans on a schedule and notify admins.
                Findings never auto-execute writes.{" "}
                {standingInvestigatorsEnabled === null
                  ? "Current policy not reported."
                  : "Choose whether advisory scans are enabled."}
              </p>
            </div>
            <Switch
              id="standing-investigators-enabled"
              checked={standingInvestigatorsEnabled === true}
              disabled={saving}
              onCheckedChange={(value) => {
                dirty.current = true
                setStandingInvestigatorsEnabled(value)
              }}
            />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="source-confidence">
                Minimum source confidence
              </Label>
              <span className="text-xs tabular-nums text-muted-foreground">
                {confidenceThreshold.toFixed(2)}
              </span>
            </div>
            <Slider
              id="source-confidence"
              aria-label="Minimum source confidence"
              disabled={saving}
              min={0.1}
              max={0.9}
              step={0.05}
              value={[confidenceThreshold]}
              onValueChange={(values) => {
                dirty.current = true
                setConfidenceThreshold(values[0] ?? confidenceThreshold)
              }}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="max-chunks">Max passages per answer</Label>
              <Input
                id="max-chunks"
                type="number"
                min={1}
                max={50}
                value={maxChunks}
                onChange={(event) => setMaxChunks(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="connector-timeout">
                Tool call timeout (seconds)
              </Label>
              <Input
                id="connector-timeout"
                type="number"
                min={5}
                max={300}
                value={connectorTimeoutSeconds}
                onChange={(event) =>
                  setConnectorTimeoutSeconds(event.target.value)
                }
              />
            </div>
          </div>
        </fieldset>
        {error ? (
          <ErrorState
            title="Could not refresh settings"
            description="Your draft is retained."
            onRetry={() => mutate()}
          />
        ) : null}
        {failure ? (
          <p role="alert" className="text-sm text-destructive">
            {failure}
          </p>
        ) : null}
        <Button onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </Button>
      </CardContent>
    </Card>
  )
}
