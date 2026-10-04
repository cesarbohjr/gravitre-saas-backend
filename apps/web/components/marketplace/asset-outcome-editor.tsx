"use client"

import { useId, useRef, useState } from "react"
import { ESTIMATED_HOURS_SAVED_MONTHLY } from "@/lib/outcome-labels"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
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
  const [error, setError] = useState<string | null>(null)
  const lock = useRef(false)
  const fieldId = useId()

  const handleSave = async () => {
    if (disabled || lock.current) return
    const parsedHours = hours.trim() ? Number(hours) : undefined
    if (
      parsedHours != null &&
      (!Number.isFinite(parsedHours) || parsedHours < 0)
    ) {
      setError("Estimated hours must be a finite number of zero or more.")
      return
    }
    lock.current = true
    setError(null)
    setBusy(true)
    try {
      await onSave({
        businessOutcome: outcome.trim() || undefined,
        useCase: useCaseValue.trim() || undefined,
        estimatedHoursSaved:
          parsedHours != null && !Number.isNaN(parsedHours)
            ? parsedHours
            : undefined,
      })
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Outcome could not be saved. Your edits are retained.",
      )
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  return (
    <details className="border-t border-[color:var(--g-border-subtle)] py-2 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11">
      <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">
        Outcome metadata
      </summary>
      <div className="space-y-3 py-2">
        <p className="text-[11px] text-muted-foreground">
          Publisher-provided estimates — not measured time-on-task.
        </p>
        <div className="space-y-2">
          <label className="text-xs font-medium" htmlFor={`${fieldId}-outcome`}>
            Business outcome
          </label>
          <Textarea
            id={`${fieldId}-outcome`}
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
            placeholder="What measurable result does this asset deliver?"
            rows={2}
            disabled={disabled || busy}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <label
              htmlFor={`${fieldId}-use-case`}
              className="text-xs font-medium"
            >
              Use case
            </label>
            <Input
              id={`${fieldId}-use-case`}
              value={useCaseValue}
              onChange={(event) => setUseCaseValue(event.target.value)}
              placeholder="Weekly pipeline review"
              disabled={disabled || busy}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor={`${fieldId}-hours`} className="text-xs font-medium">
              {ESTIMATED_HOURS_SAVED_MONTHLY}
            </label>
            <Input
              id={`${fieldId}-hours`}
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
        <Button
          size="sm"
          variant="secondary"
          disabled={disabled || busy}
          onClick={handleSave}
        >
          {busy ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : null}
          Save outcome
        </Button>
        {error ? (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    </details>
  )
}
