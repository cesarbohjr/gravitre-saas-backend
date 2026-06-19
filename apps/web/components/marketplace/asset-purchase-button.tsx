"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { Loader2, ShoppingCart } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceAssetInstallCheck, MarketplaceAssetSummary } from "@/types/api"

function formatPrice(cents?: number, currency = "usd") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format((cents ?? 0) / 100)
}

export function AssetPurchaseButton({
  asset,
  check,
  onPurchased,
  className,
}: {
  asset: MarketplaceAssetSummary
  check: MarketplaceAssetInstallCheck
  onPurchased: () => void
  className?: string
}) {
  const [busy, setBusy] = useState(false)
  const runCheckout = async () => {
    setBusy(true)
    try {
      const origin = window.location.origin
      const result = await marketplaceApi.assetCheckout(asset.slug, {
        successUrl: `${origin}/marketplace/assets/${encodeURIComponent(asset.slug)}?purchase=success`,
        cancelUrl: `${origin}/marketplace/assets/${encodeURIComponent(asset.slug)}?purchase=cancelled`,
      })
      if (result.checkoutUrl) {
        window.location.href = result.checkoutUrl
        return
      }
      onPurchased()
    } catch (err) {
      toast.error("Checkout failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button className={className ?? "w-full"} disabled={busy} onClick={() => void runCheckout()}>
      {busy ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <ShoppingCart className="mr-2 h-4 w-4" aria-hidden />
      )}
      Purchase {formatPrice(check.priceCents, check.currency)} to unlock install
    </Button>
  )
}
