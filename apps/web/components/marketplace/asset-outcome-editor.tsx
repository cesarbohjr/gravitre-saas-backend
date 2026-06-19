"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Loader2 } from "lucide-react"

export function AssetOutcomeEditor({
  businessOutcome,
  useCase,
  estimatedHoursSaved,
  disabled,
  onSave,
}: {
  businessOutcome?: string | null
  useCase?: string | null
  estimatedHoursSaved?: number | null
  disabled?: boolean
  onSave: (payload: {
    businessOutcome?: string
    useCase?: string
    estimatedHoursSaved?: number
  }) => Promise<void>
}) {
  const [outcome, setOutcome] = useState(businessOutcome ?? "")
  const [useCaseValue, setUseCaseValue] = useState(useCase ?? "")
  const [hours, setHours] = useState(
    estimatedHoursSaved != null ? String(estimatedHoursSaved) : "",
  )
  const [busy, setBusy] = useState(false)

  const handleSave = async () => {
    setBusy(true)
    try {
      const parsedHours = hours.trim() ? Number(hours) : undefined
      await onSave({
        businessOutcome: outcome.trim() || undefined,
        useCase: useCaseValue.trim() || undefined,
        estimatedHoursSaved:
          parsedHours != null && !Number.isNaN(parsedHours) ? parsedHours : undefined,
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-dashed border-border/80 bg-muted/20 p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Outcome metadata
      </p>
      <div className="space-y-2">
        <label className="text-xs font-medium" htmlFor="asset-outcome-field">
          Business outcome
        </label>
        <Textarea
          id="asset-outcome-field"
          value={outcome}
          onChange={(event) => setOutcome(event.target.value)}
          placeholder="What measurable result does this asset deliver?"
          rows={2}
          disabled={disabled || busy}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-xs font-medium">Use case</label>
          <Input
            value={useCaseValue}
            onChange={(event) => setUseCaseValue(event.target.value)}
            placeholder="Weekly pipeline review"
            disabled={disabled || busy}
          />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium">Est. hours saved / month</label>
          <Input
            type="number"
            min={0}
            step={0.5}
            value={hours}
            onChange={(event) => setHours(event.target.value)}
            placeholder="4"
            disabled={disabled || busy}
          />
        </div>
      </div>
      <Button size="sm" variant="secondary" disabled={disabled || busy} onClick={handleSave}>
        {busy ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden /> : null}
        Save outcome
      </Button>
    </div>
  )
}
