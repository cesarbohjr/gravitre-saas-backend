"use client"

import { useEffect, useId, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2 } from "lucide-react"

export type MarketplaceAssetPricingType = "free" | "paid" | "subscription"

const PRICING_OPTIONS: MarketplaceAssetPricingType[] = [
  "free",
  "paid",
  "subscription",
]

const PRICING_LABELS: Record<MarketplaceAssetPricingType, string> = {
  free: "Free",
  paid: "One-time",
  subscription: "Subscription",
}

export function formatAssetPriceLabel(
  pricingType: string,
  priceCents?: number,
) {
  if (pricingType === "free") return "Free"
  if (
    !["paid", "subscription"].includes(pricingType) ||
    priceCents == null ||
    !Number.isSafeInteger(priceCents) ||
    priceCents <= 0
  )
    return "Price not reported"
  const model = normalizePricingType(pricingType)
  const amount = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(priceCents / 100)
  return model === "subscription" ? `${amount}/mo` : amount
}

function normalizePricingType(value: string): MarketplaceAssetPricingType {
  if (value === "paid" || value === "subscription") return value
  return "free"
}

export function AssetPricingEditor({
  pricingType,
  priceCents,
  onSave,
  disabled,
}: {
  pricingType: string
  priceCents?: number
  onSave: (payload: {
    pricingType: MarketplaceAssetPricingType
    priceCents: number
  }) => Promise<void>
  disabled?: boolean
}) {
  const [model, setModel] = useState<MarketplaceAssetPricingType>(
    normalizePricingType(pricingType),
  )
  const [priceDollars, setPriceDollars] = useState(
    priceCents == null ? "" : String(priceCents / 100),
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const dirty = useRef(false)
  const lock = useRef(false)
  const inputId = useId()

  useEffect(() => {
    if (dirty.current || lock.current) return
    setModel(normalizePricingType(pricingType))
    setPriceDollars(priceCents == null ? "" : String(priceCents / 100))
  }, [pricingType, priceCents])

  const handleSave = async () => {
    if (disabled || lock.current) return
    const amount = priceDollars.trim()
    const nextPriceCents =
      model === "free" ? 0 : Math.round(Number(amount) * 100)
    if (
      model !== "free" &&
      (!/^\d+(\.\d{1,2})?$/.test(amount) ||
        !Number.isSafeInteger(nextPriceCents) ||
        nextPriceCents < 1)
    ) {
      setError("Enter a positive USD amount with at most two decimal places.")
      return
    }
    lock.current = true
    setError(null)
    setSaving(true)
    try {
      await onSave({ pricingType: model, priceCents: nextPriceCents })
      dirty.current = false
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Pricing could not be saved. Your edits are retained.",
      )
    } finally {
      lock.current = false
      setSaving(false)
    }
  }

  return (
    <details className="border-t border-[color:var(--g-border-subtle)] py-2 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11">
      <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">
        Pricing · {formatAssetPriceLabel(pricingType, priceCents)}
      </summary>
      <div className="space-y-3 py-2">
        <div className="flex flex-wrap gap-2">
          {PRICING_OPTIONS.map((option) => (
            <Button
              key={option}
              type="button"
              size="sm"
              variant={model === option ? "default" : "outline"}
              disabled={disabled || saving}
              aria-pressed={model === option}
              onClick={() => {
                dirty.current = true
                setModel(option)
              }}
            >
              {PRICING_LABELS[option]}
            </Button>
          ))}
        </div>
        {model !== "free" ? (
          <div className="flex max-w-xs items-center gap-2">
            <span className="text-sm text-muted-foreground">$</span>
            <label className="sr-only" htmlFor={inputId}>
              Price in USD
            </label>
            <Input
              id={inputId}
              type="number"
              min="0.01"
              step="0.01"
              value={priceDollars}
              disabled={disabled || saving}
              onChange={(event) => {
                dirty.current = true
                setPriceDollars(event.target.value)
              }}
            />
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {model === "subscription" ? "/ month" : "once"}
            </span>
          </div>
        ) : null}
        <Button
          size="sm"
          disabled={disabled || saving}
          onClick={() => void handleSave()}
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            "Save pricing"
          )}
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
