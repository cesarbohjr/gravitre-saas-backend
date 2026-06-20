"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2 } from "lucide-react"

export type MarketplaceAssetPricingType = "free" | "paid" | "subscription"

const PRICING_OPTIONS: MarketplaceAssetPricingType[] = ["free", "paid", "subscription"]

const PRICING_LABELS: Record<MarketplaceAssetPricingType, string> = {
  free: "Free",
  paid: "One-time",
  subscription: "Subscription",
}

export function formatAssetPriceLabel(pricingType: string, priceCents = 0) {
  const model = normalizePricingType(pricingType)
  if (model === "free" || priceCents <= 0) return "Free"
  const amount = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(priceCents / 100)
  return model === "subscription" ? `${amount}/mo` : amount
}

function normalizePricingType(value: string): MarketplaceAssetPricingType {
  if (value === "paid" || value === "subscription") return value
  return "free"
}

export function AssetPricingEditor({
  pricingType,
  priceCents = 0,
  onSave,
  disabled,
}: {
  pricingType: string
  priceCents?: number
  onSave: (payload: { pricingType: MarketplaceAssetPricingType; priceCents: number }) => Promise<void>
  disabled?: boolean
}) {
  const [model, setModel] = useState<MarketplaceAssetPricingType>(normalizePricingType(pricingType))
  const [priceDollars, setPriceDollars] = useState(String((priceCents || 0) / 100))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setModel(normalizePricingType(pricingType))
    setPriceDollars(String((priceCents || 0) / 100))
  }, [pricingType, priceCents])

  const handleSave = async () => {
    setSaving(true)
    try {
      const nextPriceCents =
        model === "free" ? 0 : Math.max(0, Math.round(parseFloat(priceDollars || "0") * 100))
      await onSave({ pricingType: model, priceCents: nextPriceCents })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-2 rounded-md border border-border/80 bg-muted/20 p-3">
      <p className="text-xs font-medium text-muted-foreground">Pricing</p>
      <div className="flex flex-wrap gap-2">
        {PRICING_OPTIONS.map((option) => (
          <Button
            key={option}
            type="button"
            size="sm"
            variant={model === option ? "default" : "outline"}
            disabled={disabled || saving}
            onClick={() => setModel(option)}
          >
            {PRICING_LABELS[option]}
          </Button>
        ))}
      </div>
      {model !== "free" ? (
        <div className="flex max-w-xs items-center gap-2">
          <span className="text-sm text-muted-foreground">$</span>
          <Input
            type="number"
            min="0"
            step="0.01"
            value={priceDollars}
            disabled={disabled || saving}
            onChange={(event) => setPriceDollars(event.target.value)}
          />
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {model === "subscription" ? "/ month" : "once"}
          </span>
        </div>
      ) : null}
      <Button size="sm" disabled={disabled || saving} onClick={() => void handleSave()}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : "Save pricing"}
      </Button>
    </div>
  )
}
